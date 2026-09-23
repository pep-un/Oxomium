from datetime import date
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase

from conformity.models import Conformity, Control, ControlPoint, Framework, Organization, Requirement
from conformity.services.conformities import propagate_applicable_and_comment
from conformity.services.controls import calendar_periods, generate_controlpoints


class ModelSafetyTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Issue 103 Org')
        self.fw = Framework.objects.create(name='Issue 103 Framework')
        self.root = Requirement.objects.create(framework=self.fw, code='A')
        self.child = Requirement.objects.create(framework=self.fw, parent=self.root, code='B')
        self.leaf = Requirement.objects.create(framework=self.fw, parent=self.child, code='C')
        self.root_conf = Conformity.objects.create(organization=self.org, requirement=self.root)
        self.child_conf = Conformity.objects.create(organization=self.org, requirement=self.child)
        self.leaf_conf = Conformity.objects.create(organization=self.org, requirement=self.leaf)

    def test_deleting_responsible_keeps_assessment(self):
        user = get_user_model().objects.create_user(username='issue103owner')
        self.leaf_conf.responsible = user
        self.leaf_conf.save(update_fields=['responsible'])
        user.delete()
        self.leaf_conf.refresh_from_db()
        self.assertIsNone(self.leaf_conf.responsible)

    def test_database_guards_status_and_duplicate_assessment(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Conformity.objects.create(
                organization=self.org, requirement=self.root, status=120
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Conformity.objects.create(
                organization=self.org, requirement=self.root
            )

    def test_parent_aggregation_and_explicit_comment_propagation(self):
        Conformity.objects.filter(pk=self.leaf_conf.pk).update(status=60)
        self.child_conf.update_status()
        self.child_conf.refresh_from_db()
        self.root_conf.refresh_from_db()
        self.assertEqual(self.child_conf.status, 60)
        self.assertEqual(self.root_conf.status, 60)
        propagate_applicable_and_comment(self.root_conf, False, 'Not applicable')
        self.leaf_conf.refresh_from_db()
        self.assertFalse(self.leaf_conf.applicable)
        self.assertEqual(self.leaf_conf.comment, 'Not applicable')
        propagate_applicable_and_comment(self.root_conf, True, 'Applicable again')
        self.leaf_conf.refresh_from_db()
        self.assertTrue(self.leaf_conf.applicable)
        self.assertEqual(self.leaf_conf.comment, 'Applicable again')

    def test_code_audit_reports_sibling_collisions_but_allows_other_parents(self):
        other_parent = Requirement.objects.create(framework=self.fw, code='D')
        Requirement.objects.create(framework=self.fw, parent=other_parent, code='B')
        output = StringIO()
        call_command('audit_requirement_codes', stdout=output)
        self.assertIn('Duplicate sibling codes: 0', output.getvalue())
        sibling = Requirement.objects.create(framework=self.fw, parent=self.root, code='E')
        Requirement.objects.filter(pk=sibling.pk).update(code='B')
        with self.assertRaises(CommandError):
            call_command('audit_requirement_codes', stdout=output)
        self.assertIn('Duplicate sibling codes: 1', output.getvalue())

    def test_display_path_ignores_legacy_hierarchical_name(self):
        Requirement.objects.filter(pk=self.child.pk).update(name='legacy-child')
        Requirement.objects.filter(pk=self.leaf.pk).update(name='legacy-leaf')
        self.leaf.refresh_from_db()
        self.assertEqual(self.leaf.full_path, 'A-B-C')
        self.assertEqual(self.leaf.natural_key(), 'legacy-leaf')

    def test_navigation_and_queryset(self):
        self.assertEqual(self.leaf.full_path, 'A-B-C')
        self.assertTrue(self.root.has_children)
        self.assertEqual(self.org.conformities.count(), 3)
        self.assertEqual(self.fw.requirements.count(), 3)
        self.assertEqual(Conformity.objects.applicable().count(), 3)


class CalendarControlTests(TestCase):
    def test_leap_year_months_are_exact(self):
        periods = list(calendar_periods(2024, Control.Frequency.BIMONTHLY))
        self.assertEqual(len(periods), 6)
        self.assertEqual(periods[0], (date(2024, 1, 1), date(2024, 2, 29)))
        self.assertEqual(periods[-1][1], date(2024, 12, 31))

    def test_repeated_generation_preserves_evaluated_points(self):
        control = Control.objects.create(title='Issue 103 control')
        generate_controlpoints(control, 2024)
        point = ControlPoint.objects.get(control=control, period_start_date=date(2024, 1, 1))
        point.status = ControlPoint.Status.COMPLIANT
        point.save(update_fields=['status'])
        control.frequency = Control.Frequency.QUARTERLY
        control.save()
        generate_controlpoints(control, 2024)
        generate_controlpoints(control, 2024)
        point.refresh_from_db()
        self.assertEqual(point.status, ControlPoint.Status.COMPLIANT)
        self.assertEqual(ControlPoint.objects.filter(
            control=control, period_start_date=date(2024, 1, 1),
            period_end_date=date(2024, 3, 31)
        ).count(), 1)
