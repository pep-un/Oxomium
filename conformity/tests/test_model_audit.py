from datetime import date, timedelta
from tempfile import TemporaryDirectory

from auditlog.context import set_actor
from auditlog.models import LogEntry
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from conformity.models import (
    Action, Attachment, Audit, Conformity, Control, ControlPoint, Finding,
    Framework, Indicator, IndicatorPoint, Organization, Requirement,
)


class ModelAuditTests(TestCase):
    """Creation, real changes, unchanged saves and deletion of every business model."""

    def setUp(self):
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        settings = override_settings(MEDIA_ROOT=media.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.actor = get_user_model().objects.create_user(username='auditor', email='audit@example.com')
        self.org = Organization.objects.create(name='Dependencies')
        self.fw = Framework.objects.create(name='Dependency framework')
        self.req = Requirement.objects.create(framework=self.fw, code='ROOT')
        self.audit = Audit.objects.create(organization=self.org, auditor='Auditor')
        self.control = Control.objects.create(title='Dependency control', organization=self.org)
        self.indicator = Indicator.objects.create(name='Dependency indicator', responsible=self.actor)
        LogEntry.objects.all().delete()

    def assert_event(self, entry, obj, pk, action):
        self.assertEqual(entry.content_type, ContentType.objects.get_for_model(obj))
        self.assertEqual(entry.object_pk, str(pk))
        self.assertEqual(entry.object_id, pk)
        self.assertEqual(entry.object_repr, str(obj))
        self.assertEqual(entry.action, action)
        self.assertEqual(entry.actor, self.actor)
        self.assertEqual(entry.actor_email, self.actor.email)
        self.assertEqual(entry.remote_addr, '192.0.2.10')
        self.assertIsNotNone(entry.timestamp)
        self.assertTrue(entry.changes)
        for field in ('id', 'create_date', 'update_date'):
            self.assertNotIn(field, entry.changes)

    def exercise_crud(self, model, fields, changed_field, before, after, foreign_keys=None):
        with set_actor(self.actor, remote_addr='192.0.2.10'):
            obj = model.objects.create(**fields)
            pk = obj.pk
            entries = LogEntry.objects.get_for_object(obj)
            self.assertEqual(entries.count(), 1)
            created = entries.get()
            self.assert_event(created, obj, pk, LogEntry.Action.CREATE)
            self.assertEqual(created.changes[changed_field], ['None', str(before)])
            for field, value in (foreign_keys or {}).items():
                self.assertEqual(created.changes[field], ['None', str(value)])
            setattr(obj, changed_field, after)
            obj.save(update_fields=[changed_field])
            updated = entries.get(action=LogEntry.Action.UPDATE)
            self.assert_event(updated, obj, pk, LogEntry.Action.UPDATE)
            self.assertEqual(updated.changes, {changed_field: [str(before), str(after)]})
            obj.save(update_fields=[changed_field])
            self.assertEqual(entries.count(), 2)
            obj.delete()
            # Deletion clears the in-memory PK, but must preserve the event identity.
            obj.pk = pk
            deleted = entries.get(action=LogEntry.Action.DELETE)
            self.assert_event(deleted, obj, pk, LogEntry.Action.DELETE)
            self.assertEqual(deleted.changes[changed_field], [str(after), 'None'])
            self.assertEqual(entries.count(), 3)

    def test_framework_crud(self):
        self.exercise_crud(Framework, {'name': 'New framework', 'publish_by': 'Before'}, 'publish_by', 'Before', 'After')

    def test_organization_crud(self):
        self.exercise_crud(Organization, {'name': 'New organization', 'description': 'Before'}, 'description', 'Before', 'After')

    def test_requirement_crud(self):
        self.exercise_crud(Requirement, {'framework': self.fw, 'code': 'NEW', 'title': 'Before'}, 'title', 'Before', 'After', {'framework': self.fw.pk})

    def test_conformity_crud(self):
        self.exercise_crud(Conformity, {'organization': self.org, 'requirement': self.req, 'status': 20}, 'status', 20, 80, {'organization': self.org.pk, 'requirement': self.req.pk})

    def test_audit_crud(self):
        self.exercise_crud(Audit, {'organization': self.org, 'auditor': 'Before'}, 'auditor', 'Before', 'After', {'organization': self.org.pk})

    def test_finding_crud(self):
        self.exercise_crud(Finding, {'audit': self.audit, 'short_description': 'Before'}, 'short_description', 'Before', 'After', {'audit': self.audit.pk})

    def test_action_crud(self):
        self.exercise_crud(Action, {'organization': self.org, 'title': 'Before'}, 'title', 'Before', 'After', {'organization': self.org.pk})

    def test_control_crud(self):
        self.exercise_crud(Control, {'organization': self.org, 'title': 'Before'}, 'title', 'Before', 'After', {'organization': self.org.pk})

    def test_controlpoint_crud(self):
        self.exercise_crud(ControlPoint, {'control': self.control, 'period_start_date': date.today(), 'period_end_date': date.today() + timedelta(days=5), 'comment': 'Before'}, 'comment', 'Before', 'After', {'control': self.control.pk})

    def test_attachment_crud(self):
        self.exercise_crud(Attachment, {'file': SimpleUploadedFile('audit.txt', b'audit content'), 'comment': 'Before'}, 'comment', 'Before', 'After')

    def test_indicator_crud(self):
        self.exercise_crud(Indicator, {'name': 'Before', 'responsible': self.actor}, 'name', 'Before', 'After', {'responsible': self.actor.pk})

    def test_indicatorpoint_crud(self):
        self.exercise_crud(IndicatorPoint, {'indicator': self.indicator, 'period_start_date': date.today(), 'period_end_date': date.today() + timedelta(days=5), 'comment': 'Before'}, 'comment', 'Before', 'After', {'indicator': self.indicator.pk})

    def test_every_business_model_has_a_crud_contract(self):
        models = {model._meta.model_name for model in apps.get_app_config('conformity').get_models()}
        covered = {name[len('test_'):-len('_crud')] for name in dir(self) if name.startswith('test_') and name.endswith('_crud')}
        self.assertEqual(models, covered)
