from auditlog.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from conformity.models import Organization


class AuditHistoryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='history_reader')
        self.client.force_login(self.user)
        self.org = Organization.objects.create(name='Historical organization')
        LogEntry.objects.all().delete()

    def test_renamed_scalar_field_remains_readable(self):
        LogEntry.objects.create(
            content_type=ContentType.objects.get_for_model(Organization),
            object_pk=str(self.org.pk), object_repr=str(self.org),
            action=LogEntry.Action.UPDATE,
            changes={'applicable_policies': ['Old policy', 'New policy']},
        )
        response = self.client.get(reverse('conformity:auditlog_index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'applicable_policies')
        self.assertContains(response, 'Old policy')
        self.assertContains(response, 'New policy')

    def test_renamed_m2m_field_and_deleted_object_remain_readable(self):
        pk, label = self.org.pk, str(self.org)
        self.org.delete()
        LogEntry.objects.all().delete()
        LogEntry.objects.create(
            content_type=ContentType.objects.get_for_model(Organization),
            object_pk=str(pk), object_repr=label, action=LogEntry.Action.UPDATE,
            changes={'applicable_policies': {
                'type': 'm2m', 'operation': 'add', 'objects': ['Historical policy'],
            }},
        )
        response = self.client.get(reverse('conformity:auditlog_index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, label)
        self.assertContains(response, 'applicable_policies')
        self.assertContains(response, 'Historical policy')
