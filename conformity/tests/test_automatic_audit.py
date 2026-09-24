from datetime import date, timedelta
from unittest.mock import patch

from auditlog.context import set_actor
from auditlog.models import LogEntry, LogEntryManager
from django.contrib.auth import get_user_model
from django.test import TestCase

from conformity.middleware import SanityCheckMiddleware
from conformity.models import Conformity, Control, ControlPoint, Framework, Indicator, IndicatorPoint, Organization, Requirement
from conformity.services.audit import update_with_audit
from conformity.services.conformities import propagate_applicable_and_comment


class AutomaticAuditTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='automatic_audit')
        self.org = Organization.objects.create(name='Organization')
        self.fw = Framework.objects.create(name='Framework')
        self.root = Requirement.objects.create(framework=self.fw, code='ROOT')
        self.leaf = Requirement.objects.create(framework=self.fw, parent=self.root, code='LEAF')
        self.parent = Conformity.objects.create(organization=self.org, requirement=self.root)
        self.child = Conformity.objects.create(organization=self.org, requirement=self.leaf)
        LogEntry.objects.all().delete()

    def test_propagation_records_real_values_and_user(self):
        with set_actor(self.user):
            propagate_applicable_and_comment(self.parent, False, 'Excluded')
        entry = LogEntry.objects.get_for_object(self.child).get()
        self.assertEqual(entry.actor, self.user)
        self.assertEqual(entry.changes, {'applicable': ['True', 'False'], 'comment': ['', 'Excluded']})
        with set_actor(self.user):
            propagate_applicable_and_comment(self.parent, False, 'Excluded')
        self.assertEqual(LogEntry.objects.get_for_object(self.child).count(), 1)
        self.parent.responsible = self.user
        with set_actor(self.user):
            self.parent.update_responsible()
        entry = LogEntry.objects.get_for_object(self.child).latest('timestamp')
        self.assertEqual(entry.actor, self.user)
        self.assertEqual(entry.changes, {'responsible': ['None', str(self.user.pk)]})

    def test_reenabling_child_audits_ancestor(self):
        Conformity.objects.filter(pk=self.parent.pk).update(applicable=False)
        with set_actor(self.user):
            propagate_applicable_and_comment(self.child, True)
        entry = LogEntry.objects.get_for_object(self.parent).get()
        self.assertEqual(entry.actor, self.user)
        self.assertEqual(entry.changes, {'applicable': ['False', 'True']})

    def test_parent_recomputation_keeps_actor(self):
        self.child.status = 80
        self.child.save()
        LogEntry.objects.all().delete()
        with set_actor(self.user):
            self.parent.update_status()
        entry = LogEntry.objects.get_for_object(self.parent).get()
        self.assertEqual(entry.actor, self.user)
        self.assertEqual(entry.changes['status'], ['None', '80.0'])

    def test_daily_checks_log_each_transition_once(self):
        today = date.today()
        control = Control.objects.create(title='Daily control')
        indicator = Indicator.objects.create(name='Daily indicator', responsible=self.user)
        for model, parent_field, parent in ((ControlPoint, 'control', control), (IndicatorPoint, 'indicator', indicator)):
            model.objects.all().delete()
            current = model.objects.create(**{parent_field: parent}, period_start_date=today, period_end_date=today + timedelta(days=5))
            expired = model.objects.create(**{parent_field: parent}, period_start_date=today - timedelta(days=10), period_end_date=today - timedelta(days=1))
            model.objects.filter(pk=current.pk).update(status='SCHD')
            model.objects.filter(pk=expired.pk).update(status='TOBE')
            LogEntry.objects.all().delete()
            checker = SanityCheckMiddleware.check_control_points if model is ControlPoint else SanityCheckMiddleware.check_indicator_points
            with set_actor(None):
                checker(today)
                checker(today)
            for point, before, after in ((current, 'SCHD', 'TOBE'), (expired, 'TOBE', 'MISS')):
                entry = LogEntry.objects.get_for_object(point).get()
                self.assertEqual(entry.action, LogEntry.Action.UPDATE)
                self.assertIsNone(entry.actor)
                self.assertEqual(entry.changes, {'status': [before, after]})
                point.refresh_from_db()
                self.assertEqual(point.status, after)

    def test_failed_log_rolls_back_bulk_update(self):
        with patch.object(LogEntryManager, 'log_create', side_effect=RuntimeError('audit failure')):
            with self.assertRaises(RuntimeError):
                update_with_audit(Conformity.objects.filter(pk=self.child.pk), comment='Uncommitted')
        self.child.refresh_from_db()
        self.assertEqual(self.child.comment, '')
        self.assertFalse(LogEntry.objects.exists())
