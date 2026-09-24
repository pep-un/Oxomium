from unittest.mock import patch

from auditlog.context import set_actor
from auditlog.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from conformity.models import Conformity, Framework, Organization, Requirement
from conformity.services.conformities import apply_framework, set_frameworks, unapply_framework


class FrameworkAuditTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(username='framework_audit', email='editor@example.com')
        self.client.force_login(self.user)
        self.org = Organization.objects.create(name='Existing organization')
        self.first = Framework.objects.create(name='First framework')
        self.root = Requirement.objects.create(framework=self.first, code='ROOT')
        self.child = Requirement.objects.create(framework=self.first, parent=self.root, code='CHILD')
        LogEntry.objects.all().delete()

    def assert_actor(self, entry):
        self.assertEqual(entry.actor, self.user)
        self.assertEqual(entry.actor_email, self.user.email)
        self.assertIsNotNone(entry.timestamp)

    def assert_framework_event(self, operation):
        entry = LogEntry.objects.get_for_object(self.org).get()
        self.assertEqual(entry.action, LogEntry.Action.UPDATE)
        self.assertEqual(entry.object_pk, str(self.org.pk))
        self.assertEqual(entry.object_repr, str(self.org))
        self.assertEqual(entry.changes, {'applicable_frameworks': {
            'type': 'm2m', 'operation': operation, 'objects': [str(self.first)],
        }})
        self.assert_actor(entry)

    def assert_assessment_events(self, action, count):
        entries = LogEntry.objects.filter(content_type=ContentType.objects.get_for_model(Conformity), action=action)
        self.assertEqual(entries.count(), count)
        for entry in entries:
            self.assert_actor(entry)
            side = 1 if action == LogEntry.Action.CREATE else 0
            self.assertEqual(entry.changes['organization'][side], str(self.org.pk))
            self.assertIn(entry.changes['requirement'][side], [str(self.root.pk), str(self.child.pk)])

    def exercise_form(self, admin):
        url = reverse('admin:conformity_organization_change', args=[self.org.pk]) if admin else reverse('conformity:organization_form', args=[self.org.pk])
        fields = {'name': self.org.name, 'description': '', 'administrative_id': '', '_save': 'Save'}
        self.assertEqual(self.client.post(url, {**fields, 'applicable_frameworks': [self.first.pk]}).status_code, 302)
        self.assert_framework_event('add')
        self.assert_assessment_events(LogEntry.Action.CREATE, 2)
        assessment = Conformity.objects.get(organization=self.org, requirement=self.child)
        assessment.status = 70
        assessment.save(update_fields=['status'])
        LogEntry.objects.all().delete()
        self.assertEqual(self.client.post(url, {**fields, 'applicable_frameworks': [self.first.pk]}).status_code, 302)
        self.assertFalse(LogEntry.objects.exists())
        assessment.refresh_from_db()
        self.assertEqual(assessment.status, 70)
        self.assertEqual(self.client.post(url, {**fields, 'applicable_frameworks': []}).status_code, 302)
        self.assert_framework_event('delete')
        self.assert_assessment_events(LogEntry.Action.DELETE, 2)

    def test_frontend_add_noop_and_remove(self):
        self.exercise_form(False)

    def test_admin_add_noop_and_remove(self):
        self.exercise_form(True)

    def test_service_idempotency_and_repair(self):
        with set_actor(self.user):
            apply_framework(self.org, self.first)
            apply_framework(self.org, self.first.pk)
        self.assert_framework_event('add')
        self.assert_assessment_events(LogEntry.Action.CREATE, 2)
        Conformity.objects.get(organization=self.org, requirement=self.child).delete()
        LogEntry.objects.all().delete()
        with set_actor(self.user):
            set_frameworks(self.org, [self.first])
        self.assertFalse(LogEntry.objects.get_for_object(self.org).exists())
        self.assert_assessment_events(LogEntry.Action.CREATE, 1)
        LogEntry.objects.all().delete()
        with set_actor(self.user):
            unapply_framework(self.org, self.first)
            unapply_framework(self.org, self.first)
        self.assert_framework_event('delete')
        self.assert_assessment_events(LogEntry.Action.DELETE, 2)

    def test_direct_m2m_requires_an_explicit_framework_operation(self):
        with set_actor(self.user):
            self.org.applicable_frameworks.add(self.first)
        self.assertFalse(Conformity.objects.filter(organization=self.org).exists())
        with set_actor(self.user):
            apply_framework(self.org, self.first)
        self.assertEqual(Conformity.objects.filter(organization=self.org).count(), 2)

    def test_audit_failure_rolls_back_data_and_logs(self):
        with patch.object(LogEntry.objects, 'log_m2m_changes', side_effect=RuntimeError('audit failure')):
            with self.assertRaises(RuntimeError):
                apply_framework(self.org, self.first)
        self.assertFalse(self.org.applicable_frameworks.exists())
        self.assertFalse(self.org.conformities.exists())
        self.assertFalse(LogEntry.objects.exists())

    def test_later_form_changes_keep_actor(self):
        url = reverse('conformity:organization_form', args=[self.org.pk])
        self.client.post(url, {'name': self.org.name, 'applicable_frameworks': [self.first.pk]})
        LogEntry.objects.all().delete()
        self.client.post(url, {'name': self.org.name, 'description': 'Changed', 'applicable_frameworks': [self.first.pk]})
        entry = LogEntry.objects.get_for_object(self.org).get()
        self.assertEqual(entry.changes, {'description': ['', 'Changed']})
        self.assert_actor(entry)
