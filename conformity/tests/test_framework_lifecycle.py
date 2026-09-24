from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from conformity.models import Conformity, Framework, Organization, Requirement
from conformity.services.conformities import apply_framework, set_frameworks, unapply_framework


class FrameworkLifecycleTests(TestCase):
    def setUp(self):
        self.first = Framework.objects.create(name='Framework lifecycle one')
        self.second = Framework.objects.create(name='Framework lifecycle two')
        self.first_requirement = Requirement.objects.create(framework=self.first, code='F1')
        self.second_requirement = Requirement.objects.create(framework=self.second, code='F2')
        self.organization = Organization.objects.create(name='Lifecycle organization')

    def test_explicit_service_preserves_answers_and_removes_only_selected_framework(self):
        apply_framework(self.organization, self.first)
        assessment = Conformity.objects.get(
            organization=self.organization, requirement=self.first_requirement
        )
        assessment.status = 75
        assessment.save(update_fields=['status'])
        apply_framework(self.organization, self.first)
        set_frameworks(self.organization, [self.first, self.second])
        assessment.refresh_from_db()
        self.assertEqual(assessment.status, 75)
        unapply_framework(self.organization, self.second)
        self.assertEqual(
            set(self.organization.applicable_frameworks.values_list('pk', flat=True)),
            {self.first.pk},
        )
        self.assertEqual(Conformity.objects.filter(organization=self.organization).count(), 1)

    def test_direct_m2m_writes_do_not_manage_assessments(self):
        self.organization.applicable_frameworks.add(self.first, self.second)
        self.assertFalse(Conformity.objects.filter(organization=self.organization).exists())
        self.organization.applicable_frameworks.clear()
        self.assertFalse(Conformity.objects.filter(organization=self.organization).exists())

    def test_reverse_direct_m2m_writes_do_not_manage_assessments(self):
        another = Organization.objects.create(name='Another lifecycle organization')
        self.first.organization_set.add(self.organization, another)
        self.assertFalse(Conformity.objects.filter(requirement=self.first_requirement).exists())
        self.first.organization_set.remove(self.organization)
        self.assertFalse(Conformity.objects.filter(organization=self.organization).exists())
        self.first.organization_set.clear()
        self.assertFalse(Conformity.objects.filter(requirement=self.first_requirement).exists())

    def test_organization_form_reconciles_frameworks_and_preserves_answers(self):
        user = get_user_model().objects.create_user(username='framework_editor')
        self.client.force_login(user)
        url = reverse('conformity:organization_form', kwargs={'pk': self.organization.pk})
        fields = {'name': self.organization.name, 'administrative_id': '',
                  'description': '', 'applicable_frameworks': [self.first.pk]}
        response = self.client.post(url, fields)
        self.assertEqual(response.status_code, 302)
        assessment = Conformity.objects.get(
            organization=self.organization, requirement=self.first_requirement
        )
        assessment.status = 80
        assessment.save(update_fields=['status'])
        response = self.client.post(url, fields)
        self.assertEqual(response.status_code, 302)
        assessment.refresh_from_db()
        self.assertEqual(assessment.status, 80)
        response = self.client.post(url, {**fields, 'applicable_frameworks': [self.second.pk]})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            set(Conformity.objects.filter(organization=self.organization)
                .values_list('requirement_id', flat=True)),
            {self.second_requirement.pk},
        )
