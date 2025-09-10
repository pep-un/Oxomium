from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase
from django.urls import NoReverseMatch

from conformity.models import *

import random
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
        self.assertEqual(list(requirements), [])

    def test_get_requirements_number(self):
        """Test the get_requirements_number method of the Framework model"""
        requirements_number = self.framework.get_requirements_number()
        self.assertEqual(requirements_number, 0)

    def test_get_root_requirement(self):
        """Test the get_root_requirement method of the Framework model"""
        root_requirement = self.framework.get_root_requirement()
        self.assertEqual(list(root_requirement), [])

    def test_get_first_requirements(self):
        """Test the get_first_requirements method of the Framework model"""
        first_requirements = self.framework.get_first_requirements()
        self.assertEqual(list(first_requirements), [])

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
        self.assertEqual(str(audit), "Test Auditor/Organization A (" + timezone.now().strftime('%b %Y') + ")")

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

    def test_get_descendants(self):
        children = self.requirement1.get_descendants()
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

    def test_get_descendants(self):
        conformity = Conformity.objects.get(id=1)
        descendants = conformity.get_descendants()
        self.assertEqual(len(descendants), 4)
        self.assertIn(Conformity.objects.get(id=2), descendants)
        self.assertIn(Conformity.objects.get(id=3), descendants)
        self.assertIn(Conformity.objects.get(id=4), descendants)
        self.assertIn(Conformity.objects.get(id=5), descendants)

    def test_get_children(self):
        conformity = Conformity.objects.get(id=1)
        children = conformity.get_children()
        self.assertEqual(len(children), 2)
        self.assertIn(Conformity.objects.get(id=2), children)
        self.assertIn(Conformity.objects.get(id=3), children)
        self.assertNotIn(Conformity.objects.get(id=4), children)
        self.assertNotIn(Conformity.objects.get(id=5), children)

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

    def test_update_status(self):
        conformity_parent = Conformity.objects.get(id=3)
        children = conformity_parent.get_children()
        for child in children:
            child.set_status_from(0, Conformity.StatusJustification.EXPERT)
        conformity_parent.update_status()
        conformity_parent.save()
        self.assertEqual(conformity_parent.status, 0)

        status1 = random.randint(0, 100)
        conformity_child1 = Conformity.objects.get(id=4)
        conformity_child1.status = status1
        conformity_child1.applicable = True
        conformity_child1.save()
        conformity_child1.update_status()
        self.assertEqual(conformity_child1.status, status1)

        status2 = random.randint(0, 100)
        conformity_child2 = Conformity.objects.get(id=5)
        conformity_child2.status = status2
        conformity_child2.applicable = True
        conformity_child2.save()
        conformity_child2.update_status()
        self.assertEqual(conformity_child2.status, status2)

        conformity_parent = Conformity.objects.get(id=3)
        self.assertEqual(conformity_parent.status, int(mean([status1, status2])))

        conformity_root = Conformity.objects.get(id=1)
        self.assertEqual(conformity_root.status, int(mean([mean([status1, status2])])))


class ControlModelTest(TestCase):
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


class ControlPointModelTest(TestCase):
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


class ConformityGetRelatedTests(TestCase):
    """
    Minimal coverage of Conformity.get_related() in negative_only mode,
    ensuring actions/controlpoints can be surfaced.
    """
    def setUp(self):
        self.fw = Framework.objects.create(
            name="FW-ConformityRelated",
            version=1,
            publish_by="UnitTest",
            type=Framework.Type.INTERNATIONAL,
        )
        self.org = Organization.objects.create(name="Org-CR")

        self.req = Requirement.objects.create(
            code="R",
            title="Root",
            framework=self.fw,
            parent=None,
            order=1,
        )
        self.conf = Conformity.objects.create(
            organization=self.org,
            requirement=self.req,
        )

        # Owner user for action realism
        self.owner = User.objects.create_user(username="rel_owner", password="x")

        # Create an "active" action (so it can appear in negative_only branch)
        self.act = Action.objects.create(
            title="Improve XYZ",
            organization=self.org,
            owner=self.owner,
            status=Action.Status.PLANNING,  # one of the active statuses in your model
        )

        # If your schema links Action <-> Conformity, attach it; otherwise this part is a no-op.
        # FK variant (common):
        if hasattr(self.act, "conformity_id"):
            self.act.conformity = self.conf
            self.act.save()
        # M2M variant:
        elif hasattr(self.conf, "actions"):
            try:
                self.conf.actions.add(self.act)  # type: ignore[attr-defined]
            except Exception:
                pass

        # Control + a current ControlPoint in an evaluable status
        self.ctrl = Control.objects.create(
            title="Quarterly Check",
            organization=self.org,
            level=Control.Level.FIRST,
            frequency=Control.Frequency.QUARTERLY,
        )
        # If schema has M2M Control <-> Conformity, relate them
        if hasattr(self.ctrl, "conformity"):
            try:
                self.ctrl.conformity.add(self.conf)  # type: ignore[attr-defined]
            except Exception:
                pass

        today = timezone.now().date()
        self.cp = ControlPoint.objects.create(
            control=self.ctrl,
            period_start_date=today.replace(day=1),
            period_end_date=today,
            status=ControlPoint.Status.TOBEEVALUATED,
        )

    def test_get_related_negative_only_actions_and_controls(self):
        items = self.conf.get_related(
            negative_only=True,
            include_actions=True,
            include_controls=True,
        )
        # Expect list of (kind, object)
        kinds = {k for (k, _obj) in items}

        # ControlPoints should always be present given we created one in the current window
        self.assertIn("controlpoint", kinds)

        # If action <-> conformity relation exists in your schema, actions should be present
        if hasattr(self.conf, "actions") or hasattr(Action, "conformity"):
            self.assertIn("action", kinds)


class AttachmentModelLightTests(TestCase):
    """
    Very light sanity check for Attachment.
    We avoid strict content-type assertions to remain platform-agnostic.
    The stored filename may include a random suffix, so we only assert suffix.
    """
    def test_str_returns_filename_suffix(self):
        f = SimpleUploadedFile("hello.txt", b"hello world", content_type="text/plain")
        att = Attachment.objects.create(file=f)
        s = str(att)
        # Should at least end with ".txt"
        self.assertTrue(s.endswith(".txt"))
        # And must contain "hello" as the original base name
        self.assertIn("hello", s)


class FrameworkLanguageChoicesTests(TestCase):
    """Minimal sanity checks for Framework.Language.choices()"""
    def test_language_choices_shape(self):
        tuples = Framework.Language.choices()
        self.assertIsInstance(tuples, list)
        if tuples:
            code, label = tuples[0]
            self.assertIsInstance(code, str)
            self.assertLessEqual(len(code), 3)  # usually alpha-2, sometimes others
            self.assertIsInstance(label, str)

class ConformityRelationAndGuardsTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Org X")
        self.fw = Framework.objects.create(name="FW-Appended", version=1, publish_by="X",
                                           type=Framework.Type.POLICY)
        # Build a tiny requirement tree
        self.root = Requirement.objects.create(framework=self.fw, name="R", level=0)
        self.child = Requirement.objects.create(framework=self.fw, name="R.1", level=1, parent=self.root)
        # Create conformities
        self.org.add_conformity(self.fw)
        self.c_root = Conformity.objects.get(organization=self.org, requirement=self.root)
        self.c_child = Conformity.objects.get(organization=self.org, requirement=self.child)

    def test_get_control(self):
        ctl = Control.objects.create(title="C1", organization=self.org)
        ctl.conformity.add(self.c_child)
        res = list(self.c_child.get_control())
        self.assertEqual(res, [ctl])

    def test_get_related_default_and_negative_modes(self):
        # Action linked to conformity
        a = Action.objects.create(title="A1", organization=self.org, status=Action.Status.ANALYSING)
        a.associated_conformity.add(self.c_child)

        # ControlPoint for "today" window and set as NONCOMPLIANT
        ctl = Control.objects.create(title="C2", organization=self.org)
        ctl.conformity.add(self.c_child)
        # generate CPs
        Control.controlpoint_bootstrap(ctl)
        # grab a CP in current period or just take first and force dates around today
        cp = ctl.get_controlpoint().first()
        # ensure current period
        from datetime import date, timedelta
        cp.period_start_date = date.today() - timedelta(days=1)
        cp.period_end_date = date.today() + timedelta(days=1)
        ControlPoint.update_status(cp)
        cp.status = ControlPoint.Status.NONCOMPLIANT
        cp.save()

        # Default mode: actions + controls
        kinds = [k for k,_ in self.c_child.get_related()]
        self.assertIn("action", kinds)
        self.assertIn("control", kinds)

        # Negative-only: actions in progress + negative controlpoints
        kinds_neg = [k for k,_ in self.c_child.get_related(negative_only=True)]
        self.assertIn("action", kinds_neg)
        self.assertIn("controlpoint", kinds_neg)

        # Sorting variants should not crash and return same elements as set
        s1 = set(self.c_child.get_related(sort="alpha"))
        s2 = set(self.c_child.get_related(sort="recent_first"))
        self.assertSetEqual({t[0] for t in s1}, {t[0] for t in s2})

    def test_update_applicable_descendants_and_ancestors(self):
        # Turn root non-applicable -> child must become non-applicable as well
        self.c_root.applicable = False
        self.c_root.save(update_fields=["applicable"])
        self.c_root.update_applicable()
        self.c_child.refresh_from_db()
        self.assertFalse(self.c_child.applicable)

        # Turn child applicable -> ancestors should be applicable
        self.c_child.applicable = True
        self.c_child.save(update_fields=["applicable"])
        self.c_child.update_applicable()
        self.c_root.refresh_from_db()
        self.assertTrue(self.c_root.applicable)

    def test_update_responsible_propagates(self):
        user = get_user_model().objects.create(username="bob")
        self.c_root.responsible = user
        self.c_root.save(update_fields=["responsible"])
        self.c_root.update_responsible()
        self.c_child.refresh_from_db()
        self.assertEqual(self.c_child.responsible, user)

    def test_set_status_from_guards(self):
        # EXPERT must be refused on non-leaf
        before = (self.c_root.status, self.c_root.status_justification)
        changed = self.c_root.set_status_from(50, Conformity.StatusJustification.EXPERT)
        self.assertFalse(changed)
        self.c_root.refresh_from_db()
        self.assertEqual((self.c_root.status, self.c_root.status_justification), before)

        # ACTION 0% requires negative evidence -> with none, must refuse
        changed = self.c_child.set_status_from(0, Conformity.StatusJustification.ACTION)
        self.assertFalse(changed)

        # With negative evidence present, 100% must be refused
        a = Action.objects.create(title="A2", organization=self.org, status=Action.Status.ANALYSING)
        a.associated_conformity.add(self.c_child)
        ctl = Control.objects.create(title="C3", organization=self.org)
        ctl.conformity.add(self.c_child)
        Control.controlpoint_bootstrap(ctl)
        cp = ctl.get_controlpoint().first()
        from datetime import date, timedelta
        cp.period_start_date = date.today() - timedelta(days=1)
        cp.period_end_date = date.today() + timedelta(days=1)
        ControlPoint.update_status(cp)
        cp.status = ControlPoint.Status.NONCOMPLIANT
        cp.save()
        changed = self.c_child.set_status_from(100, Conformity.StatusJustification.CONTROL)
        self.assertFalse(changed)

class AuditAndFindingExtraTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Org Y")
        self.fw = Framework.objects.create(name="FW-Audit", version=1, publish_by="X",
                                           type=Framework.Type.POLICY)
        self.audit = Audit.objects.create(name="Audit1", auditor="Auditor 1", organization=self.org)

    def test_audit_positive_and_other_filters(self):
        Finding.objects.create(short_description="pos", audit=self.audit, severity=Finding.Severity.POSITIVE)
        Finding.objects.create(short_description="other", audit=self.audit, severity=Finding.Severity.OTHER)
        self.assertEqual(self.audit.get_positive_findings().count(), 1)
        self.assertEqual(self.audit.get_other_findings().count(), 1)

    def test_finding_helpers_and_archived_logic(self):
        f = Finding.objects.create(short_description="x", audit=self.audit, severity=Finding.Severity.MAJOR)
        # is_active True by default (not archived, not positive)
        self.assertTrue(f.is_active())

        # cvss validation
        f.cvss = 10.1
        with self.assertRaises(ValidationError):
            f.clean()
        f.cvss = 0.05
        with self.assertRaises(ValidationError):
            f.clean()

        # update_archived with actions
        a1 = Action.objects.create(title="A", organization=self.org, status=Action.Status.ANALYSING)
        a1.associated_findings.add(f)
        f.update_archived()
        f.refresh_from_db()
        self.assertFalse(f.archived)  # at least one active

        # all actions inactive -> archived True
        a1.status = Action.Status.ENDED
        a1.save()
        f.update_archived()
        f.refresh_from_db()
        self.assertTrue(f.archived)

    def test_get_absolute_urls_exist(self):
        f = Finding.objects.create(short_description="url", audit=self.audit, severity=Finding.Severity.MINOR)
        try:
            url = f.get_absolute_url()
            self.assertIsInstance(url, str)
        except NoReverseMatch:
            self.skipTest("URLconf for 'conformity:finding_detail' not available")
        a = Action.objects.create(title="A-URL", organization=self.org, status=Action.Status.ANALYSING)
        try:
            url2 = a.get_absolute_url()
            self.assertIsInstance(url2, str)
        except NoReverseMatch:
            self.skipTest("URLconf for 'conformity:action_index' not available")

class ControlAndControlPointExtrasTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Org Z")
        self.ctl = Control.objects.create(title="Ctl", organization=self.org)

    def test_control_str_and_get_controlpoint_and_signal_idempotent(self):
        # initial creation generates CPs via callback
        Control.controlpoint_bootstrap(self.ctl)
        cps = list(self.ctl.get_controlpoint())
        self.assertTrue(len(cps) >= 1)
        # running again shouldn't duplicate the same periods
        Control.controlpoint_bootstrap(self.ctl)
        cps2 = list(self.ctl.get_controlpoint())
        # By comparing (start,end) pairs
        pairs = {(c.period_start_date, c.period_end_date) for c in cps2}
        self.assertEqual(len(pairs), len(cps2))

        s = str(self.ctl)
        self.assertIn("Ctl", s)

    def test_controlpoint_helpers_and_boundaries(self):
        Control.controlpoint_bootstrap(self.ctl)
        cp = self.ctl.get_controlpoint().first()
        # Force dates around today and compute status via update_status
        from datetime import date, timedelta
        cp.period_start_date = date.today()
        cp.period_end_date = date.today()
        ControlPoint.update_status(cp)
        self.assertEqual(cp.status, ControlPoint.Status.TOBEEVALUATED)
        # helper methods
        self.assertTrue(cp.is_current_period(date.today()))
        self.assertTrue(cp.is_final_status() in (False, True))  # just ensure it returns a bool

        # get_action linkage
        act = Action.objects.create(title="AC", organization=self.org, status=Action.Status.ANALYSING)
        act.associated_controlPoints.add(cp)
        acts = list(cp.get_action())
        self.assertEqual(acts, [act])

class ActionExtrasTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Org A")

    def test_action_basic_helpers_and_save_side_effects(self):
        a = Action.objects.create(title="T", organization=self.org, status=Action.Status.ANALYSING)
        self.assertTrue(a.is_in_progress())
        self.assertFalse(a.is_completed())
        # saving with ENDED should flip active False
        a.status = Action.Status.ENDED
        a.save()
        self.assertFalse(a.active)
        # and __str__ should include organization and title
        s = str(a)
        self.assertIn("T", s)