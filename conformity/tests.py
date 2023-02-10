from django.test import TestCase
from conformity.models import Policy, Organization


class ModelsTestCase(TestCase):
    def test_policy_applicable_policy(self):
        policy = Policy.objects.create(name="p_test")
        organization = Organization.objects.create(name='o_test')

        organization.add_conformity(policy)
        organization.save()

        self.assertEqual(str(policy), "p_test")


class ViewsTestCase(TestCase):
    def test_login_loads_properly(self):
        """The login page loads properly"""
        response = self.client.get('127.0.0.1:8000')
        self.assertEqual(response.status_code, 200)