from tempfile import TemporaryDirectory
from unittest.mock import patch

from auditlog.context import set_actor
from auditlog.models import LogEntry, LogEntryManager
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import TestCase, override_settings

from conformity.models import (
    Action, Attachment, Audit, Conformity, Control, ControlPoint, Finding,
    Framework, Indicator, IndicatorPoint, Organization, Requirement,
)


class RelationAuditTests(TestCase):
    def setUp(self):
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        config = override_settings(MEDIA_ROOT=media.name)
        config.enable()
        self.addCleanup(config.disable)
        self.user = get_user_model().objects.create_user(username='relation_audit', email='relations@example.com')
        self.org = Organization.objects.create(name='Organization')
        self.frameworks = [Framework.objects.create(name=f'Framework {i}') for i in range(2)]
        self.attachments = [Attachment.objects.create(file=SimpleUploadedFile(f'audit{i}.txt', b'content')) for i in range(2)]
        self.conformities = [Conformity.objects.create(organization=self.org, requirement=Requirement.objects.create(framework=self.frameworks[i], code=f'ROOT{i}')) for i in range(2)]
        self.audit = Audit.objects.create(organization=self.org, auditor='Auditor')
        self.findings = [Finding.objects.create(audit=self.audit, short_description=f'Finding {i}') for i in range(2)]
        self.controls = [Control.objects.create(title=f'Control {i}') for i in range(3)]
        self.points = [ControlPoint.objects.filter(control=control).first() for control in self.controls[:2]]
        self.action = Action.objects.create(title='Action')
        self.indicator = Indicator.objects.create(name='Indicator', responsible=self.user)
        self.indicator_point = IndicatorPoint.objects.filter(indicator=self.indicator).first()
        self.cases = [
            (self.frameworks[0], 'attachment', self.attachments),
            (self.org, 'attachment', self.attachments),
            (self.org, 'applicable_frameworks', self.frameworks),
            (self.audit, 'audited_frameworks', self.frameworks),
            (self.audit, 'attachment', self.attachments),
            (self.controls[0], 'conformity', self.conformities),
            (self.controls[0], 'control', self.controls[1:]),
            (self.points[0], 'attachment', self.attachments),
            (self.action, 'associated_conformity', self.conformities),
            (self.action, 'associated_findings', self.findings),
            (self.action, 'associated_controlPoints', self.points),
            (self.indicator, 'conformity', self.conformities),
            (self.indicator_point, 'attachment', self.attachments),
        ]

    def assert_event(self, owner, field, operation, targets):
        entry = LogEntry.objects.get_for_object(owner).get()
        self.assertEqual(entry.action, LogEntry.Action.UPDATE)
        self.assertEqual(entry.actor, self.user)
        self.assertEqual(entry.actor_email, self.user.email)
        self.assertEqual(entry.object_repr, str(owner))
        self.assertEqual(entry.object_pk, str(owner.pk))
        self.assertEqual(entry.changes, {field: {'type': 'm2m', 'operation': operation, 'objects': [str(obj) for obj in targets]}})

    def test_all_relations_add_remove_clear_and_noop(self):
        # Framework removal cascades to conformities: test it last so other cases
        # keep their fixture targets intact.
        cases = sorted(self.cases, key=lambda case: case[1] == 'applicable_frameworks')
        for owner, field, targets in cases:
            with self.subTest(model=owner._meta.label, field=field), set_actor(self.user):
                relation = getattr(owner, field)
                LogEntry.objects.all().delete()
                relation.add(targets[0])
                self.assert_event(owner, field, 'add', targets[:1])
                LogEntry.objects.all().delete()
                relation.add(targets[0])
                relation.remove(targets[1])
                self.assertFalse(LogEntry.objects.get_for_object(owner).exists())
                relation.remove(targets[0])
                self.assert_event(owner, field, 'delete', targets[:1])
                relation.add(targets[0])
                LogEntry.objects.all().delete()
                relation.clear()
                self.assert_event(owner, field, 'delete', targets[:1])
                LogEntry.objects.all().delete()
                relation.clear()
                self.assertFalse(LogEntry.objects.get_for_object(owner).exists())

    def test_reverse_framework_events_belong_to_each_organization(self):
        other = Organization.objects.create(name='Other')
        framework = self.frameworks[0]
        with set_actor(self.user):
            LogEntry.objects.all().delete()
            framework.organization_set.add(self.org, other)
            for org in (self.org, other):
                self.assert_event(org, 'applicable_frameworks', 'add', [framework])
            self.assertFalse(LogEntry.objects.get_for_object(framework).exists())
            LogEntry.objects.all().delete()
            framework.organization_set.remove(self.org)
            self.assert_event(self.org, 'applicable_frameworks', 'delete', [framework])
            self.assertFalse(LogEntry.objects.get_for_object(other).exists())
            LogEntry.objects.all().delete()
            framework.organization_set.clear()
            self.assert_event(other, 'applicable_frameworks', 'delete', [framework])
            self.assertFalse(LogEntry.objects.get_for_object(self.org).exists())

    def test_symmetric_control_relation_logs_both_sides(self):
        first, second = self.controls[:2]
        with set_actor(self.user):
            LogEntry.objects.all().delete()
            first.control.add(second)
            self.assert_event(first, 'control', 'add', [second])
            self.assert_event(second, 'control', 'add', [first])
            LogEntry.objects.all().delete()
            second.control.clear()
            self.assert_event(first, 'control', 'delete', [second])
            self.assert_event(second, 'control', 'delete', [first])

    def test_log_failure_rolls_back_relation(self):
        with patch.object(LogEntryManager, 'log_m2m_changes', side_effect=RuntimeError('audit failure')):
            with self.assertRaises(RuntimeError), transaction.atomic():
                self.org.attachment.add(self.attachments[0])
        self.assertFalse(self.org.attachment.exists())

    def test_every_business_m2m_field_is_covered(self):
        fields = {(model, field.name) for model in apps.get_app_config('conformity').get_models() for field in model._meta.local_many_to_many}
        self.assertEqual(fields, {(type(owner), field) for owner, field, _ in self.cases})
