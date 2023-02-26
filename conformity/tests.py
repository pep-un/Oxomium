import glob
import importlib
from calendar import monthrange
from datetime import date, timedelta

from django.conf import settings
from django.db import IntegrityError
from django.test import TestCase, Client
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.utils import timezone, inspect
from django.views import View

from .models import Policy, Organization, Audit, Finding, Measure, Conformity, Action, User, Control, ControlPoint
from .views import *
import random, inspect
from statistics import mean



class PolicyModelTest(TestCase):

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


class OrganizationModelTest(TestCase):
    def setUp(self):
        self.policy1 = Policy.objects.create(name="Policy 1", version=1, publish_by="Publisher 1")
        self.policy2 = Policy.objects.create(name="Policy 2", version=2, publish_by="Publisher 2")
        self.measure1 = Measure.objects.create(code='1', name='Test Measure 1', policy=self.policy1)
        self.measure2 = Measure.objects.create(code='2000', name='Test Measure 2', policy=self.policy2)
        self.measure3 = Measure.objects.create(code='2100', name='Test Measure 2.1',
                                               policy=self.policy2, parent=self.measure2)
        self.measure4 = Measure.objects.create(code='2110', name='Test Measure 2.1.1',
                                               policy=self.policy2, parent=self.measure3)
        self.measure5 = Measure.objects.create(code='2120', name='Test Measure 2.1.2',
                                               policy=self.policy2, parent=self.measure4)
        self.measure6 = Measure.objects.create(code='2200', name='Test Measure 2.2',
                                               policy=self.policy2, parent=self.measure2)
        self.organization = Organization.objects.create(name="Organization 1", administrative_id="Admin ID 1",
                                                        description="Organization 1 description")

    def test_str_representation(self):
        self.assertEqual(str(self.organization), "Organization 1")

    def test_natural_key(self):
        self.assertEqual(self.organization.natural_key(), "Organization 1")

    def test_get_absolute_url(self):
        self.assertEqual(self.organization.get_absolute_url(), '/organization/')

    def test_add_remove_conformity(self):
        # Add the policies to the organization
        self.organization.add_conformity(self.policy1)
        self.organization.add_conformity(self.policy2)

        # Check if the conformity is created for the policies
        conformities = Conformity.objects.filter(organization=self.organization)
        self.assertEqual(conformities.count(), 6)

        # Remove conformity for policy1
        self.organization.remove_conformity(self.policy2)
        conformities = Conformity.objects.filter(organization=self.organization)
        self.assertEqual(conformities.count(), 1)

    def test_get_policies(self):
        self.organization.applicable_policies.add(self.policy1)
        self.organization.applicable_policies.add(self.policy2)
        policies = self.organization.get_policies()
        self.assertIn(self.policy1, policies)
        self.assertIn(self.policy2, policies)


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

    def test_str(self):
        audit = Audit.objects.get(id=1)
        self.assertEqual(str(audit), "[Organization A] Test Auditor (" + timezone.now().strftime('%b %Y') + ")")

    def test_absolute_url(self):
        audit = Audit.objects.get(id=1)
        self.assertEqual(audit.get_absolute_url(), '/audit/')

    def test_policies(self):
        audit = Audit.objects.get(id=1)
        self.assertEqual(audit.get_policies().count(), 1)

    def test_type(self):
        audit = Audit.objects.get(id=1)
        self.assertEqual(audit.get_type(), 'Other')

    def test_findings(self):
        audit = Audit.objects.get(id=1)
        self.assertEqual(audit.get_findings().count(), 1)

    def test_findings_number(self):
        audit = Audit.objects.get(id=1)
        self.assertEqual(audit.get_findings_number(), 1)

    def test_critical_findings(self):
        audit = Audit.objects.get(id=1)
        self.assertEqual(audit.get_critical_findings().count(), 1)

    def test_major_findings(self):
        audit = Audit.objects.get(id=1)
        self.assertEqual(audit.get_major_findings().count(), 0)

    def test_minor_findings(self):
        audit = Audit.objects.get(id=1)
        self.assertEqual(audit.get_minor_findings().count(), 0)

    def test_observation_findings(self):
        audit = Audit.objects.get(id=1)
        self.assertEqual(audit.get_observation_findings().count(), 0)


class FindingModelTest(TestCase):

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

    def test_short_description(self):
        finding = Finding.objects.get(short_description='Test Short Description')
        self.assertEqual(finding.short_description, 'Test Short Description')

    def test_severity(self):
        finding = Finding.objects.get(short_description='Test Short Description')
        self.assertEqual(finding.severity, Finding.Severity.CRITICAL)

    def test_audit(self):
        finding = Finding.objects.get(short_description='Test Short Description')
        audit = Audit.objects.get(auditor='Test Auditor')
        self.assertEqual(finding.audit, audit)

    def test_str(self):
        finding = Finding.objects.get(short_description='Test Short Description')
        self.assertEqual(str(finding), 'Test Short Description')


class MeasureModelTest(TestCase):
    def setUp(self):
        policy = Policy.objects.create(name='test policy')
        self.measure1 = Measure.objects.create(code="m1", name='Measure 1', policy=policy, title='Measure 1 Title',
                                               description='Measure 1 Description')
        self.measure2 = Measure.objects.create(code="m2", name='Measure 2', policy=policy, title='Measure 2 Title',
                                               description='Measure 2 Description', parent=self.measure1)
        self.measure3 = Measure.objects.create(code="m3", name='Measure 3', policy=policy, title='Measure 3 Title',
                                               description='Measure 3 Description', parent=self.measure1)

    def test_str(self):
        self.assertEqual(str(self.measure1), 'm1: Measure 1 Title')

    def test_get_by_natural_key(self):
        self.assertEqual(self.measure1.natural_key(), 'm1')

    def test_get_children(self):
        children = self.measure1.get_children()
        self.assertEqual(len(children), 2)
        self.assertIn(self.measure2, children)
        self.assertIn(self.measure3, children)

    def test_measure_without_policy(self):
        measure = Measure(name="Measure without policy", title="Test measure without policy")
        with self.assertRaises(Exception):
            measure.save()


class ConformityModelTest(TestCase):

    def setUp(self):
        # create a user
        self.organization = Organization.objects.create(name='Test Organization')
        self.policy = Policy.objects.create(name='test policy')
        self.measure0 = Measure.objects.create(policy=self.policy, code='TEST-00', name='Test Measure Root')
        self.measure1 = Measure.objects.create(policy=self.policy, code='TEST-01',
                                               name='Test Measure 01', parent=self.measure0)
        self.measure2 = Measure.objects.create(policy=self.policy, code='TEST-02',
                                               name='Test Measure 02', parent=self.measure0)
        self.measure3 = Measure.objects.create(policy=self.policy, code='TEST-03',
                                               name='Test Measure 03', parent=self.measure2)
        self.measure4 = Measure.objects.create(policy=self.policy, code='TEST-04',
                                               name='Test Measure 04', parent=self.measure2)

        self.organization.add_conformity(self.policy)

    def test_str(self):
        conformity = Conformity.objects.get(id=1)
        self.assertEqual(str(conformity), "[Test Organization] TEST-00: ")

    def test_get_absolute_url(self):
        conformity = Conformity.objects.get(id=1)
        self.assertEqual(conformity.get_absolute_url(), '/conformity/org/1/pol/1/')

    def test_get_children(self):
        conformity = Conformity.objects.get(id=1)
        children = conformity.get_children()
        self.assertEqual(len(children), 2)
        self.assertIn(Conformity.objects.get(id=2), children)
        self.assertIn(Conformity.objects.get(id=3), children)

    def test_get_parent(self):
        conformity = Conformity.objects.get(id=1)
        parent = conformity.get_parent()
        self.assertEqual(None, parent)

        conformity = Conformity.objects.get(id=2)
        parent = conformity.get_parent()
        self.assertEqual(Conformity.objects.get(id=1), parent)

    def test_get_action(self):
        conformity = Conformity.objects.filter(organization=self.organization)[1]
        action1 = Action.objects.create(title="Test Conformity #1")
        action2 = Action.objects.create(title="Test Conformity #1")
        action1.associated_conformity.set([conformity])
        action2.associated_conformity.set([conformity])

        actions = conformity.get_action()

        self.assertEqual(len(actions), 2)
        self.assertIn(action2, actions)
        self.assertIn(action2, actions)

    def test_set_status(self):
        conformity_parent = Conformity.objects.get(id=3)
        conformity_parent.set_status(99)
        self.assertEqual(conformity_parent.status, 0)

        status1 = random.randint(0, 100)
        conformity_child1 = Conformity.objects.get(id=4)
        conformity_child1.set_status(status1)
        self.assertEqual(conformity_child1.status, status1)

        status2 = random.randint(0, 100)
        conformity_child2 = Conformity.objects.get(id=5)
        conformity_child2.set_status(status2)
        self.assertEqual(conformity_child2.status, status2)

        conformity_parent = Conformity.objects.get(id=3)
        self.assertEqual(conformity_parent.status, int(mean([status1, status2])))

        conformity_root = Conformity.objects.get(id=1)
        self.assertEqual(conformity_root.status, int(mean([mean([status1, status2]), 0])))

    def test_set_responsible(self):
        user = User.objects.create_user(username='test user')
        conformity = Conformity.objects.filter(organization=self.organization)[2]
        conformity.set_responsible(user)
        self.assertEqual(conformity.responsible, user)


class AuthenticationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.views = [
            # View
            HomeView,
            AuditIndexView,
            AuditDetailView,
            AuditUpdateView,
            AuditCreateView,
            FindingCreateView,
            FindingDetailView,
            FindingUpdateView,
            OrganizationIndexView,
            OrganizationDetailView,
            OrganizationUpdateView,
            OrganizationCreateView,
            PolicyIndexView,
            PolicyDetailView,
            ConformityIndexView,
            ConformityOrgPolIndexView,
            ConformityUpdateView,
            ActionCreateView,
            ActionIndexView,
            ActionIndexForConformityView,
            ActionUpdateView,
            AuditLogDetailView,
            # Form
            #ConformityForm, #TODO issue with the references at the Form instanciation. Exclude from test.
            OrganizationForm,
            AuditForm,
            FindingForm,
            ActionForm,
        ]

    def test_auth_view(self):
        for view in self.views:
            view_instance = view()
            mixins = view_instance.__class__.__bases__
            self.assertTrue(LoginRequiredMixin in mixins, f"{view.__name__} does not have LoginRequiredMixin")


class ControlTest(TestCase):
    def setUp(self):
        self.yearly_control = Control.objects.create(title='Yearly control', frequency=Control.Frequency.YEARLY)
        self.halfyearly_control = Control.objects.create(title='Half-yearly control', frequency=Control.Frequency.HALFYEARLY)
        self.quarterly_control = Control.objects.create(title='Quarterly control', frequency=Control.Frequency.QUARTERLY)
        self.bimonthly_control = Control.objects.create(title='Bimonthly control', frequency=Control.Frequency.BIMONTHLY)
        self.monthly_control = Control.objects.create(title='Monthly control', frequency=Control.Frequency.MONTHLY)

    def test_get_absolute_url(self):
        self.assertEqual(ControlPoint.objects.first().get_absolute_url(), '/control/')

    def test_control_point_number(self):
        yearly_cp_count = ControlPoint.objects.filter(control=self.yearly_control).count()
        halfyearly_cp_count = ControlPoint.objects.filter(control=self.halfyearly_control).count()
        quarterly_cp_count = ControlPoint.objects.filter(control=self.quarterly_control).count()
        bimonthly_cp_count = ControlPoint.objects.filter(control=self.bimonthly_control).count()
        monthly_cp_count = ControlPoint.objects.filter(control=self.monthly_control).count()

        self.assertEqual(yearly_cp_count, 1)
        self.assertEqual(halfyearly_cp_count, 2)
        self.assertEqual(quarterly_cp_count, 4)
        self.assertEqual(bimonthly_cp_count, 6)
        self.assertEqual(monthly_cp_count, 12)

    def test_control_point_date(self):
        yearly_cp = ControlPoint.objects.filter(control=self.yearly_control)
        halfyearly_cp_list = ControlPoint.objects.filter(control=self.halfyearly_control)
        quarterly_cp_list = ControlPoint.objects.filter(control=self.quarterly_control)
        bimonthly_cp_list = ControlPoint.objects.filter(control=self.bimonthly_control)
        monthly_cp_list = ControlPoint.objects.filter(control=self.monthly_control)
        year = date.today().year

        # Year test
        self.assertEqual(yearly_cp[0].period_start_date, date(year, 1, 1))
        self.assertEqual(yearly_cp[0].period_end_date, date(year, 12, 31))

        # Biannual test
        self.assertEqual(halfyearly_cp_list[0].period_start_date, date(year, 1, 1))
        self.assertEqual(halfyearly_cp_list[0].period_end_date, date(year, 6, 30))
        self.assertEqual(halfyearly_cp_list[1].period_start_date, date(year, 7, 1))
        self.assertEqual(halfyearly_cp_list[1].period_end_date, date(year, 12, 31))

        # Quaterly test
        self.assertEqual(quarterly_cp_list[0].period_start_date, date(year, 1, 1))
        self.assertEqual(quarterly_cp_list[0].period_end_date, date(year, 3, 31))
        self.assertEqual(quarterly_cp_list[1].period_start_date, date(year, 4, 1))
        self.assertEqual(quarterly_cp_list[1].period_end_date, date(year, 6, 30))
        self.assertEqual(quarterly_cp_list[2].period_start_date, date(year, 7, 1))
        self.assertEqual(quarterly_cp_list[2].period_end_date, date(year, 9, 30))
        self.assertEqual(quarterly_cp_list[3].period_start_date, date(year, 10, 1))
        self.assertEqual(quarterly_cp_list[3].period_end_date, date(year, 12, 31))

        # Bimonthly test
        self.assertEqual(bimonthly_cp_list[0].period_start_date, date(year, 1, 1))
        self.assertEqual(bimonthly_cp_list[0].period_end_date, date(year, 2, monthrange(year, 2)[1]))
        self.assertEqual(bimonthly_cp_list[1].period_start_date, date(year, 3, 1))
        self.assertEqual(bimonthly_cp_list[1].period_end_date, date(year, 4, 30))
        self.assertEqual(bimonthly_cp_list[2].period_start_date, date(year, 5, 1))
        self.assertEqual(bimonthly_cp_list[2].period_end_date, date(year, 6, 30))
        self.assertEqual(bimonthly_cp_list[3].period_start_date, date(year, 7, 1))
        self.assertEqual(bimonthly_cp_list[3].period_end_date, date(year, 8, 31))
        self.assertEqual(bimonthly_cp_list[4].period_start_date, date(year, 9, 1))
        self.assertEqual(bimonthly_cp_list[4].period_end_date, date(year, 10, 31))
        self.assertEqual(bimonthly_cp_list[5].period_start_date, date(year, 11, 1))
        self.assertEqual(bimonthly_cp_list[5].period_end_date, date(year, 12, 31))

        # Month test
        for i in range(1,13,1):
            end_day = monthrange(year, i)[1]
            self.assertEqual(monthly_cp_list[i-1].period_start_date, date(year, i, 1))
            self.assertEqual(monthly_cp_list[i-1].period_end_date, date(year, i, end_day))


class ControlPointTest(TestCase):
    def setUp(self):
        today = date.today()
        self.ctrl = Control.objects.create(title='Yearly', frequency=Control.Frequency.YEARLY)
        ControlPoint.objects.create(control=self.ctrl, period_start_date=today - timedelta(days=3),
                                    period_end_date=today - timedelta(days=1) )
        ControlPoint.objects.create(control=self.ctrl, period_start_date=today, period_end_date= today)
        ControlPoint.objects.create(control=self.ctrl, period_start_date=today + timedelta(days=1),
                                    period_end_date=today + timedelta(days=3))

    def test_control_point_status(self):
        miss = ControlPoint.objects.filter(control=self.ctrl, status=ControlPoint.Status.MISSED).count()
        tobe = ControlPoint.objects.filter(control=self.ctrl, status=ControlPoint.Status.TOBEEVALUATED).count()
        sche = ControlPoint.objects.filter(control=self.ctrl, status=ControlPoint.Status.SCHEDULED).count()

        self.assertEqual(miss, 1)
        self.assertEqual(tobe, 2)
        self.assertEqual(sche, 1)

    def test_get_absolute_url(self):
        self.assertEqual(ControlPoint.objects.first().get_absolute_url(), '/control/')
