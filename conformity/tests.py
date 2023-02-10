from django.db import IntegrityError
from django.test import TestCase
from .models import *


class PolicyModelTests(TestCase):

    def setUp(self):
        self.policy = Policy.objects.create(name='Test Policy', version=1, publish_by='Test Publisher',
                                            type=Policy.Type.INTERNATIONAL)

    def test_str_representation(self):
        """Test the string representation of the Policy model"""
        self.assertEqual(str(self.policy), 'Test Policy')

    def test_natural_key(self):
        """Test the natural key of the Policy model"""
        self.assertEqual(self.policy.natural_key(), 'Test Policy')

    def test_get_by_natural_key_does_not_exist(self):
        with self.assertRaises(Policy.DoesNotExist):
            Policy.objects.get_by_natural_key("Non Existing Policy")

    def test_get_type(self):
        """Test the get_type method of the Policy model"""
        self.assertEqual(self.policy.get_type(), 'International Standard')

    def test_get_measures(self):
        """Test the get_measures method of the Policy model"""
        measures = self.policy.get_measures()
        self.assertQuerysetEqual(measures, [])

    def test_get_measures_number(self):
        """Test the get_measures_number method of the Policy model"""
        measures_number = self.policy.get_measures_number()
        self.assertEqual(measures_number, 0)

    def test_get_root_measure(self):
        """Test the get_root_measure method of the Policy model"""
        root_measure = self.policy.get_root_measure()
        self.assertQuerysetEqual(root_measure, [])

    def test_get_first_measures(self):
        """Test the get_first_measures method of the Policy model"""
        first_measures = self.policy.get_first_measures()
        self.assertQuerysetEqual(first_measures, [])

    def test_unique_name(self):
        """Test if the name field is unique"""
        policy = Policy(name='Test Policy', version=1, publish_by='Test Publisher', type=Policy.Type.INTERNATIONAL)
        with self.assertRaises(IntegrityError):
            policy.save()

    def test_default_version(self):
        """Test if the version field has a default value of 0"""
        policy = Policy.objects.create(
            name='Test Policy 2',
            publish_by='Test Publisher 2',
            type=Policy.Type.NATIONAL
        )
        self.assertEqual(policy.version, 0)

    def test_default_type(self):
        """Test if the type field has a default value of 'OTHER'"""
        policy = Policy.objects.create(
            name='Test Policy 3',
            version=1,
            publish_by='Test Publisher 3',
        )
        self.assertEqual(policy.type, Policy.Type.OTHER)


class OrganizationModelTestCase(TestCase):
    def setUp(self):
        self.policy1 = Policy.objects.create(name="Policy 1", version=1, publish_by="Publisher 1")
        self.policy2 = Policy.objects.create(name="Policy 2", version=2, publish_by="Publisher 2")
        self.measure1 = Measure.objects.create(code='1', name='Test Measure 1', level=0, policy=self.policy1)
        self.measure1 = Measure.objects.create(code='2', name='Test Measure 2', level=0, policy=self.policy2)
        self.organization = Organization.objects.create(name="Organization 1", administrative_id="Admin ID 1",
                                                        description="Organization 1 description")

    def test_str_representation(self):
        self.assertEqual(str(self.organization), "Organization 1")

    def test_natural_key(self):
        self.assertEqual(self.organization.natural_key(), "Organization 1")

    def test_get_absolute_url(self):
        self.assertEqual(self.organization.get_absolute_url(), reverse('conformity:organization_index'))

    def test_add_remove_conformity(self):
        # Add the policies to the organization
        self.organization.add_conformity(self.policy1)
        self.organization.add_conformity(self.policy2)

        # Check if the conformity is created for the policies
        conformities = Conformity.objects.filter(organization=self.organization)
        self.assertEqual(conformities.count(), 2)

        # Remove conformity for policy1
        self.organization.remove_conformity(self.policy1.id)
        conformities = Conformity.objects.filter(organization=self.organization)
        self.assertEqual(conformities.count(), 1)


class AuditModelTests(TestCase):
    def setUp(self):
        organization = Organization.objects.create(name='Organization A')
        policy = Policy.objects.create(name='Policy A', organization=organization)
        audit = Audit.objects.create(organization=organization, description='Test Audit', conclusion='Test Conclusion',
                                     auditor='Test Auditor', start_date=timezone.now(), end_date=timezone.now(),
                                     report_date=timezone.now())
        audit.audited_policies.add(policy)
        finding = Finding.objects.create(short_description='Test Finding', description='Test Description',
                                         reference='Test Reference', audit=audit, severity=Finding.Severity.CRITICAL)

    def test_audit_str(self):
        audit = Audit.objects.get(id=1)
        self.assertEqual(str(audit), "[Organization A] Test Auditor (" + timezone.now().strftime('%b %Y') + ")")

    def test_audit_absolute_url(self):
        audit = Audit.objects.get(id=1)
        self.assertEqual(audit.get_absolute_url(), '/audit/')

    def test_audit_policies(self):
        audit = Audit.objects.get(id=1)
        self.assertEqual(audit.get_policies().count(), 1)

    def test_audit_type(self):
        audit = Audit.objects.get(id=1)
        self.assertEqual(audit.get_type(), 'Other')

    def test_audit_findings(self):
        audit = Audit.objects.get(id=1)
        self.assertEqual(audit.get_findings().count(), 1)

    def test_audit_findings_number(self):
        audit = Audit.objects.get(id=1)
        self.assertEqual(audit.get_findings_number(), 1)

    def test_audit_critical_findings(self):
        audit = Audit.objects.get(id=1)
        self.assertEqual(audit.get_critical_findings().count(), 1)

    def test_audit_major_findings(self):
        audit = Audit.objects.get(id=1)
        self.assertEqual(audit.get_major_findings().count(), 0)

    def test_audit_minor_findings(self):
        audit = Audit.objects.get(id=1)
        self.assertEqual(audit.get_minor_findings().count(), 0)

    def test_audit_observation_findings(self):
        audit = Audit.objects.get(id=1)
        self.assertEqual(audit.get_minor_findings().count(), 0)


class FindingModelTestCase(TestCase):

    def setUp(self):
        organization = Organization.objects.create(
            name='Test Organization'
        )
        audit = Audit.objects.create(
            organization=organization,
            auditor='Test Auditor',
            report_date=timezone.now()
        )
        Finding.objects.create(
            short_description='Test Short Description',
            audit=audit,
            severity=Finding.Severity.CRITICAL
        )

    def test_finding_short_description(self):
        finding = Finding.objects.get(short_description='Test Short Description')
        self.assertEqual(finding.short_description, 'Test Short Description')

    def test_finding_severity(self):
        finding = Finding.objects.get(short_description='Test Short Description')
        self.assertEqual(finding.severity, Finding.Severity.CRITICAL)

    def test_finding_audit(self):
        finding = Finding.objects.get(short_description='Test Short Description')
        audit = Audit.objects.get(auditor='Test Auditor')
        self.assertEqual(finding.audit, audit)

    def test_finding_str(self):
        finding = Finding.objects.get(short_description='Test Short Description')
        self.assertEqual(str(finding), 'Test Short Description')


class MeasureTestCase(TestCase):
    def setUp(self):
        policy = Policy.objects.create(name='test policy')
        self.measure1 = Measure.objects.create(code="m1", name='Measure 1', policy=policy, title='Measure 1 Title',
                                               description='Measure 1 Description')
        self.measure2 = Measure.objects.create(code="m2", name='Measure 2', policy=policy, title='Measure 2 Title',
                                               description='Measure 2 Description', parent=self.measure1)
        self.measure3 = Measure.objects.create(code="m3", name='Measure 3', policy=policy, title='Measure 3 Title',
                                               description='Measure 3 Description', parent=self.measure1)

    def test_measure_str_representation(self):
        self.assertEqual(str(self.measure1), 'm1: Measure 1 Title')

    def test_measure_natural_key(self):
        self.assertEqual(self.measure1.natural_key(), 'm1')

    def test_measure_children(self):
        children = self.measure1.get_children()
        self.assertEqual(len(children), 2)
        self.assertIn(self.measure2, children)
        self.assertIn(self.measure3, children)

    def test_measure_without_policy(self):
        measure = Measure(name="Measure without policy", title="Test measure without policy")
        with self.assertRaises(Exception) as context:
            measure.save()


class ConformityTestCase(TestCase):

    def setUp(self):
        # create a user
        user = User.objects.create_user(username='testuser', password='testpassword')
        self.organization = Organization.objects.create(name='Test Organization')
        self.policy = Policy.objects.create(name='test policy')
        self.measure0 = Measure.objects.create(policy=self.policy, code='TEST-00', name='Test Measure Root')
        self.measure1 = Measure.objects.create(policy=self.policy, code='TEST-01', name='Test Measure 01', parent=self.measure0)
        self.measure2 = Measure.objects.create(policy=self.policy, code='TEST-02', name='Test Measure 01', parent=self.measure0)
        self.measure3 = Measure.objects.create(policy=self.policy, code='TEST-03', name='Test Measure 01', parent=self.measure2)
        self.measure4 = Measure.objects.create(policy=self.policy, code='TEST-04', name='Test Measure 01', parent=self.measure2)

        self.organization.add_conformity(self.policy)

    def test_conformity_str_representation(self):
        conformity = Conformity.objects.get(id=1)
        self.assertEqual(str(conformity), "[Test Organization] TEST-00: ")

    def test_conformity_get_absolute_url(self):
        conformity = Conformity.objects.get(id=1)
        self.assertEqual(conformity.get_absolute_url(), '/conformity/org/1/pol/1/')

    def test_conformity_get_children(self):
        conformity = Conformity.objects.get(id=1)
        children = conformity.get_children()
        self.assertEqual(len(children), 2)
        self.assertIn(Conformity.objects.get(id=2), children)
        self.assertIn(Conformity.objects.get(id=3), children)

    def test_conformity_get_parent_empty(self):
        conformity = Conformity.objects.get(id=1)
        parent = conformity.get_parent()
        self.assertEqual(len(parent), 0)

    def test_conformity_get_parent_non_empty(self):
        conformity = Conformity.objects.get(id=2)
        parent = conformity.get_parent()
        self.assertEqual(len(parent), 1)
        self.assertIn(Conformity.objects.get(id=1), parent)

#    def test_conformity_get_action(self):
#        conformity = Conformity.objects.get(id=3)
#        # create an action for the conformity
#        action = Action.objects.create(description='Test Action')
#        action.associated_conformity.set(conformity)
#        actions = list(conformity.get_action())
#        self.assertEqual(len(actions), 1)
#        self.assertIn(action, actions)
