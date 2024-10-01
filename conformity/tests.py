import glob
import importlib
from calendar import monthrange
from datetime import date, timedelta, datetime

from dateutil.utils import today
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db import IntegrityError
from django.test import TestCase, Client
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.utils import timezone, inspect
from django.views import View

from .models import Framework, Organization, Audit, Finding, Requirement, Conformity, Action, User, Control, ControlPoint
from .views import *
from .middleware import SanityCheckMiddleware

import random, inspect
from statistics import mean

# pylint: disable=no-member

class FrameworkModelTest(TestCase):

    def setUp(self):
        self.framework = Framework.objects.create(name='Test Framework', version=1, publish_by='Test Publisher',
                                            type=Framework.Type.INTERNATIONAL)

    def test_str_representation(self):
        """Test the string representation of the Framework model"""
        self.assertEqual(str(self.framework), 'Test Framework')

    def test_natural_key(self):
        """Test the natural key of the Framework model"""
        self.assertEqual(self.framework.natural_key(), 'Test Framework')

    def test_get_by_natural_key_does_not_exist(self):
        with self.assertRaises(Framework.DoesNotExist):
            Framework.objects.get_by_natural_key("Non Existing Framework")

    def test_get_type(self):
        """Test the get_type method of the Framework model"""
        self.assertEqual(self.framework.get_type(), 'International Standard')

    def test_get_requirement(self):
        """Test the get_requirements method of the Framework model"""
        requirements = self.framework.get_requirements()
        self.assertQuerysetEqual(requirements, [])

    def test_get_requirements_number(self):
        """Test the get_requirements_number method of the Framework model"""
        requirements_number = self.framework.get_requirements_number()
        self.assertEqual(requirements_number, 0)

    def test_get_root_requirement(self):
        """Test the get_root_requirement method of the Framework model"""
        root_requirement = self.framework.get_root_requirement()
        self.assertQuerysetEqual(root_requirement, [])

    def test_get_first_requirements(self):
        """Test the get_first_requirements method of the Framework model"""
        first_requirements = self.framework.get_first_requirements()
        self.assertQuerysetEqual(first_requirements, [])

    def test_unique_name(self):
        """Test if the name field is unique"""
        framework = Framework(name='Test Framework', version=1, publish_by='Test Publisher', type=Framework.Type.INTERNATIONAL)
        with self.assertRaises(IntegrityError):
            framework.save()

    def test_default_version(self):
        """Test if the version field has a default value of 0"""
        framework = Framework.objects.create(
            name='Test Framework 2',
            publish_by='Test Publisher 2',
            type=Framework.Type.NATIONAL
        )
        self.assertEqual(framework.version, 0)

    def test_default_type(self):
        """Test if the type field has a default value of 'OTHER'"""
        framework = Framework.objects.create(
            name='Test Framework 3',
            version=1,
            publish_by='Test Publisher 3',
        )
        self.assertEqual(framework.type, Framework.Type.OTHER)


class OrganizationModelTest(TestCase):
    def setUp(self):
        self.framework1 = Framework.objects.create(name="Framework 1", version=1, publish_by="Publisher 1")
        self.framework2 = Framework.objects.create(name="Framework 2", version=2, publish_by="Publisher 2")
        self.requirement1 = Requirement.objects.create(code='1', name='Test Requirement 1', framework=self.framework1)
        self.requirement2 = Requirement.objects.create(code='2000', name='Test Requirement 2', framework=self.framework2)
        self.requirement3 = Requirement.objects.create(code='2100', name='Test Requirement 2.1',
                                               framework=self.framework2, parent=self.requirement2)
        self.requirement4 = Requirement.objects.create(code='2110', name='Test Requirement 2.1.1',
                                               framework=self.framework2, parent=self.requirement3)
        self.requirement5 = Requirement.objects.create(code='2120', name='Test Requirement 2.1.2',
                                               framework=self.framework2, parent=self.requirement4)
        self.requirement6 = Requirement.objects.create(code='2200', name='Test Requirement 2.2',
                                               framework=self.framework2, parent=self.requirement2)
        self.organization = Organization.objects.create(name="Organization 1", administrative_id="Admin ID 1",
                                                        description="Organization 1 description")

    def test_str_representation(self):
        self.assertEqual(str(self.organization), "Organization 1")

    def test_natural_key(self):
        self.assertEqual(self.organization.natural_key(), "Organization 1")

    def test_get_absolute_url(self):
        self.assertEqual(self.organization.get_absolute_url(), '/organization/')

    def test_add_remove_conformity(self):
        # Add the frameworks to the organization
        self.organization.add_conformity(self.framework1)
        self.organization.add_conformity(self.framework2)

        # Check if the conformity is created for the frameworks
        conformities = Conformity.objects.filter(organization=self.organization)
        self.assertEqual(conformities.count(), 6)

        # Remove conformity for framework1
        self.organization.remove_conformity(self.framework2)
        conformities = Conformity.objects.filter(organization=self.organization)
        self.assertEqual(conformities.count(), 1)

    def test_get_framworks(self):
        self.organization.applicable_frameworks.add(self.framework1)
        self.organization.applicable_frameworks.add(self.framework2)
        frameworks = self.organization.get_frameworks()
        self.assertIn(self.framework1, frameworks)
        self.assertIn(self.framework2, frameworks)


class AuditModelTests(TestCase):
    def setUp(self):
        organization = Organization.objects.create(name='Organization A')
        framework = Framework.objects.create(name='Framework A', organization=organization)
        audit = Audit.objects.create(organization=organization, description='Test Audit', conclusion='Test Conclusion',
                                     auditor='Test Auditor', start_date=timezone.now(), end_date=timezone.now(),
                                     report_date=timezone.now())
        audit.audited_frameworks.add(framework)
        finding = Finding.objects.create(short_description='Test Finding', description='Test Description',
                                         reference='Test Reference', audit=audit, severity=Finding.Severity.CRITICAL)

    def test_str(self):
        audit = Audit.objects.get(id=1)
        self.assertEqual(str(audit), "[Organization A] Test Auditor (" + timezone.now().strftime('%b %Y') + ")")

    def test_absolute_url(self):
        audit = Audit.objects.get(id=1)
        self.assertEqual(audit.get_absolute_url(), '/audit/')

    def test_frameworks(self):
        audit = Audit.objects.get(id=1)
        self.assertEqual(audit.get_frameworks().count(), 1)

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


class RequirementModelTest(TestCase):
    def setUp(self):
        framework = Framework.objects.create(name='test framework')
        self.requirement1 = Requirement.objects.create(code="m1", name='Requirement 1', framework=framework, title='Requirement 1 Title',
                                               description='Requirement 1 Description')
        self.requirement2 = Requirement.objects.create(code="m2", name='Requirement 2', framework=framework, title='Requirement 2 Title',
                                               description='Requirement 2 Description', parent=self.requirement1)
        self.requirement3 = Requirement.objects.create(code="m3", name='Requirement 3', framework=framework, title='Requirement 3 Title',
                                               description='Requirement 3 Description', parent=self.requirement1)

    def test_str(self):
        self.assertEqual(str(self.requirement1), 'm1: Requirement 1 Title')

    def test_get_by_natural_key(self):
        self.assertEqual(self.requirement1.natural_key(), 'm1')

    def test_get_children(self):
        children = self.requirement1.get_children()
        self.assertEqual(len(children), 2)
        self.assertIn(self.requirement2, children)
        self.assertIn(self.requirement3, children)

    def test_requirement_without_framework(self):
        requirement = Requirement(name="Requirement without framework", title="Test requirement without framework")
        with self.assertRaises(Exception):
            requirement.save()


class ConformityModelTest(TestCase):

    def setUp(self):
        # create a user
        self.organization = Organization.objects.create(name='Test Organization')
        self.framework = Framework.objects.create(name='test framework')
        self.requirement0 = Requirement.objects.create(framework=self.framework, code='TEST-00', name='Test Requirement Root')
        self.requirement1 = Requirement.objects.create(framework=self.framework, code='TEST-01',
                                               name='Test Requirement 01', parent=self.requirement0)
        self.requirement2 = Requirement.objects.create(framework=self.framework, code='TEST-02',
                                               name='Test Requirement 02', parent=self.requirement0)
        self.requirement3 = Requirement.objects.create(framework=self.framework, code='TEST-03',
                                               name='Test Requirement 03', parent=self.requirement2)
        self.requirement4 = Requirement.objects.create(framework=self.framework, code='TEST-04',
                                               name='Test Requirement 04', parent=self.requirement2)

        self.organization.add_conformity(self.framework)

    def test_str(self):
        conformity = Conformity.objects.get(id=1)
        self.assertEqual(str(conformity), "[Test Organization] TEST-00: ")

    def test_get_absolute_url(self):
        conformity = Conformity.objects.get(id=1)
        self.assertEqual(conformity.get_absolute_url(), '/conformity/organization/1/framework/1/')

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
            FrameworkIndexView,
            FrameworkDetailView,
            ConformityIndexView,
            ConformityDetailIndexView,
            ConformityUpdateView,
            ActionCreateView,
            ActionIndexView,
            ActionUpdateView,
            AuditLogDetailView,
            # Form
            #ConformityForm, #TODO issue with the references at the Form instantiation. Exclude from test.
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
        self.assertEqual(Control.objects.first().get_absolute_url(), '/control/')

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


class SanityCheckMiddlewareTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        """Set up test data for all tests."""
        today = datetime.today().date()

        # Create a user and a control instance as they are foreign keys in ControlPoint
        cls.user = User.objects.create_user(username='testuser', password='password')
        cls.control = Control.objects.create(title="Test Control")

        # Control points that should be marked as 'MISS'
        cls.missed_control_1 = ControlPoint.objects.create(
            control=cls.control,
            control_user=cls.user,
            period_start_date=today - relativedelta(days=10),
            period_end_date=today - relativedelta(days=1),  # missed yesterday
            status="TOBE"
        )
        cls.missed_control_3 = ControlPoint.objects.create(
            control=cls.control,
            control_user=cls.user,
            period_start_date=today - relativedelta(days=10),
            period_end_date=today - relativedelta(days=5),  # missed 5 days ago
            status="TOBE"
        )

        # Control points that should not be updated (not in TOBE status)
        cls.not_missed_control = ControlPoint.objects.create(
            control=cls.control,
            control_user=cls.user,
            period_start_date=today - relativedelta(days=10),
            period_end_date=today - relativedelta(days=5),  # missed but not in TOBE
            status="MISS"
        )
        cls.not_missed_control_2 = ControlPoint.objects.create(
            control=cls.control,
            control_user=cls.user,
            period_start_date=today - relativedelta(days=10),
            period_end_date=today,  # today is not miss
            status="TOBE"
        )

        # Control points that should be marked as 'TOBE'
        cls.scheduled_control_1 = ControlPoint.objects.create(
            control=cls.control,
            control_user=cls.user,
            period_start_date=today.replace(day=1),
            period_end_date=today.replace(day=1) + relativedelta(months=1) - relativedelta(days=1),
            status="SCHD"
        )
        cls.scheduled_control_2 = ControlPoint.objects.create(
            control=cls.control,
            control_user=cls.user,
            period_start_date=today.replace(day=1) - relativedelta(months=3),
            period_end_date=today.replace(day=1) + relativedelta(months=2),
            status="SCHD"
        )

        # Control point that should stay in SCHED
        cls.scheduled_control_3 = ControlPoint.objects.create(
            control=cls.control,
            control_user=cls.user,
            period_start_date=today + relativedelta(days=1),
            period_end_date=today + relativedelta(days=30),
            status="SCHD"
        )

        # Control point that should not be updated (not in SCHD status)
        cls.not_scheduled_control = ControlPoint.objects.create(
            control=cls.control,
            control_user=cls.user,
            period_start_date=today.replace(day=1),
            period_end_date=today.replace(day=1) + relativedelta(months=1) - relativedelta(days=1),
            status="TOBE"
        )

        # Control point that should not be updated (OK ou NOK)
        cls.ok_control = ControlPoint.objects.create(
            control=cls.control,
            control_user=cls.user,
            period_start_date=today.replace(day=1),
            period_end_date=today.replace(day=1) + relativedelta(months=1) - relativedelta(days=1),
            status="OK"
        )
        cls.nok_control = ControlPoint.objects.create(
            control=cls.control,
            control_user=cls.user,
            period_start_date=today.replace(day=1) - relativedelta(months=3),
            period_end_date=today.replace(day=1) - relativedelta(days=1),
            status="NOK"
        )

    def test_missed_controls_update(self):
        """Test that missed controls are updated to 'MISS'."""
        today = datetime.today().date()
        SanityCheckMiddleware.check_control_points(today)

        self.missed_control_1.refresh_from_db()
        self.not_missed_control_2.refresh_from_db()
        self.missed_control_3.refresh_from_db()

        self.assertEqual(self.missed_control_1.status, 'MISS')
        self.assertEqual(self.not_missed_control_2.status, 'TOBE')
        self.assertEqual(self.missed_control_3.status, 'MISS')

    def test_scheduled_controls_update(self):
        """Test that scheduled controls are updated to 'TOBE'."""
        today = datetime.today().date()
        SanityCheckMiddleware.check_control_points(today)

        self.scheduled_control_1.refresh_from_db()
        self.scheduled_control_2.refresh_from_db()
        self.scheduled_control_3.refresh_from_db()

        self.assertEqual(self.scheduled_control_1.status, 'TOBE')
        self.assertEqual(self.scheduled_control_2.status, 'TOBE')
        self.assertEqual(self.scheduled_control_3.status, 'SCHD')

    def test_no_update(self):
        """Test some control that should not be updated"""
        today = datetime.today().date()
        SanityCheckMiddleware.check_control_points(today)

        """Test a SCHD control that should not switch to TOBE"""
        self.scheduled_control_3.refresh_from_db()
        self.assertEqual(self.scheduled_control_3.status, 'SCHD')

        """Test that controls not in 'TOBE' or 'SCHD' are not updated."""
        self.not_missed_control.refresh_from_db()
        self.not_scheduled_control.refresh_from_db()

        self.assertEqual(self.not_missed_control.status, 'MISS')
        self.assertEqual(self.not_scheduled_control.status, 'TOBE')

        """Test that controls not in 'OK' or 'NOK' are not updated."""
        self.ok_control.refresh_from_db()
        self.nok_control.refresh_from_db()

        self.assertEqual(self.ok_control.status, 'OK')
        self.assertEqual(self.nok_control.status, 'NOK')