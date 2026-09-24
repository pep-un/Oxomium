from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from auditlog.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.contrib.sessions.models import Session
from conformity import admin as conformity_admin
from conformity.models import Attachment, Conformity, Framework, Organization, Requirement


class OrganizationAdminFrameworkTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='admin_frameworks', password='admin_frameworks', email='admin@example.com'
        )
        self.client.force_login(self.user)
        self.first = Framework.objects.create(name='Admin framework one')
        self.second = Framework.objects.create(name='Admin framework two')
        self.first_requirement = Requirement.objects.create(framework=self.first, code='AD1')
        self.second_requirement = Requirement.objects.create(framework=self.second, code='AD2')
        self.organization = Organization.objects.create(name='Admin organization')
        self.url = reverse('admin:conformity_organization_change', args=[self.organization.pk])

    def save_frameworks(self, ids):
        return self.client.post(
            self.url,
            {
                'name': self.organization.name,
                'administrative_id': '',
                'description': '',
                'applicable_frameworks': ids,
                '_save': 'Save',
            },
        )

    def test_admin_imports_auditlog_model_from_supported_module(self):
        self.assertIs(conformity_admin.LogEntry, LogEntry)

    def test_admin_reconciles_frameworks_without_erasing_existing_assessments(self):
        response = self.save_frameworks([self.first.pk])
        self.assertEqual(response.status_code, 302, response.content.decode()[:500])
        assessment = Conformity.objects.get(
            organization=self.organization, requirement=self.first_requirement
        )
        assessment.status = 70
        assessment.save(update_fields=['status'])

        response = self.save_frameworks([self.first.pk, self.second.pk])
        self.assertEqual(response.status_code, 302, response.content.decode()[:500])
        assessment.refresh_from_db()
        self.assertEqual(assessment.status, 70)
        self.assertTrue(
            Conformity.objects.filter(
                organization=self.organization, requirement=self.second_requirement
            ).exists()
        )

        response = self.save_frameworks([self.second.pk])
        self.assertEqual(response.status_code, 302, response.content.decode()[:500])
        self.assertEqual(
            set(Conformity.objects.filter(organization=self.organization)
                .values_list('requirement_id', flat=True)),
            {self.second_requirement.pk},
        )

        response = self.save_frameworks([])
        self.assertEqual(response.status_code, 302, response.content.decode()[:500])
        self.assertFalse(Conformity.objects.filter(organization=self.organization).exists())


    def test_admin_framework_changes_are_audited(self):
        LogEntry.objects.all().delete()

        response = self.save_frameworks([self.first.pk])
        self.assertEqual(response.status_code, 302, response.content.decode()[:500])
        addition = LogEntry.objects.get_for_object(self.organization).get()
        self.assertEqual(addition.actor, self.user)
        self.assertEqual(
            addition.changes['applicable_frameworks']['operation'],
            'add',
        )

        LogEntry.objects.all().delete()
        response = self.save_frameworks([])
        self.assertEqual(response.status_code, 302, response.content.decode()[:500])
        removal = LogEntry.objects.get_for_object(self.organization).get()
        self.assertEqual(removal.actor, self.user)
        self.assertEqual(
            removal.changes['applicable_frameworks']['operation'],
            'delete',
        )

    def test_admin_framework_changes_are_audited_when_organization_already_has_framework(self):
        self.organization.applicable_frameworks.add(self.first)
        LogEntry.objects.all().delete()

        response = self.save_frameworks([self.first.pk, self.second.pk])
        self.assertEqual(response.status_code, 302, response.content.decode()[:500])
        addition = LogEntry.objects.get_for_object(self.organization).get()
        self.assertEqual(addition.actor, self.user)
        self.assertEqual(addition.changes['applicable_frameworks']['operation'], 'add')
        self.assertEqual(addition.changes['applicable_frameworks']['objects'], [self.second.name])

        LogEntry.objects.all().delete()
        response = self.save_frameworks([self.first.pk])
        self.assertEqual(response.status_code, 302, response.content.decode()[:500])
        removal = LogEntry.objects.get_for_object(self.organization).get()
        self.assertEqual(removal.actor, self.user)
        self.assertEqual(removal.changes['applicable_frameworks']['operation'], 'delete')
        self.assertEqual(removal.changes['applicable_frameworks']['objects'], [self.second.name])

    def test_admin_framework_audit_events_are_visible_in_audit_log(self):
        LogEntry.objects.all().delete()
        self.save_frameworks([self.first.pk])
        self.save_frameworks([])
        self.save_frameworks([])

        response = self.client.get(reverse('conformity:auditlog_index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.first.name)
        self.assertContains(response, 'add')
        self.assertContains(response, 'delete')

    def test_audit_log_can_filter_by_object_type_action_and_user(self):
        LogEntry.objects.all().delete()
        self.save_frameworks([self.first.pk])
        self.save_frameworks([])

        response = self.client.get(
            reverse('conformity:auditlog_index'),
            {
                'object_repr': self.organization.name,
                'content_type': ContentType.objects.get_for_model(Organization).pk,
                'action': LogEntry.Action.UPDATE,
                'actor': self.user.pk,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['filter'].qs.count(), 2)
        self.assertContains(response, self.organization.name)
        self.assertContains(response, self.first.name)

    def test_audit_log_can_filter_automatic_events_as_oxomium(self):
        LogEntry.objects.all().delete()
        self.save_frameworks([self.first.pk])
        self.save_frameworks([])

        response = self.client.get(
            reverse('conformity:auditlog_index'),
            {'actor': 'system'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['filter'].form.cleaned_data['actor'], 'system')
        self.assertGreater(response.context['filter'].qs.count(), 0)
        self.assertContains(response, 'Oxomium')

    def test_audit_log_displays_events_without_numeric_object_id(self):
        LogEntry.objects.all().delete()
        LogEntry.objects.create(
            content_type=ContentType.objects.get_for_model(Session),
            object_pk='session-key',
            object_repr='session event',
            action=LogEntry.Action.ACCESS,
        )

        response = self.client.get(reverse('conformity:auditlog_index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'session event')
        self.assertContains(response, 'sessions | session')

    def test_admin_related_save_is_atomic(self):
        attachment = Attachment.objects.create(
            file=SimpleUploadedFile(
                'admin-attachment.txt',
                b'attachment content',
                content_type='text/plain',
            )
        )

        with patch('conformity.admin.set_frameworks', side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    self.url,
                    {
                        'name': self.organization.name,
                        'administrative_id': '',
                        'description': '',
                        'applicable_frameworks': [self.first.pk],
                        'attachment': [attachment.pk],
                        '_save': 'Save',
                    },
                )

        self.assertFalse(self.organization.attachment.exists())
        self.assertFalse(self.organization.applicable_frameworks.exists())
