from django.contrib.auth import get_user_model
from datetime import date

from django.test import RequestFactory, TestCase
from django.urls import reverse

from conformity.forms import ActionForm, ControlForm, FindingForm
from conformity.models import (
    Action, Audit, Conformity, Control, ControlPoint, Finding, Framework, Organization,
    Requirement,
)
from conformity.views import ActionCreateView, ControlCreateView, FindingCreateView


class FindingCreateViewTest(TestCase):
    def test_invalid_audit_query_parameter_returns_404(self):
        user = get_user_model().objects.create_user(username="invalid_audit")
        self.client.force_login(user)
        url = reverse('conformity:finding_create')

        for audit_id in ('abc', '1.5', ' ', '999999999999999999999999999999'):
            for method in ('get', 'post'):
                with self.subTest(audit_id=audit_id, method=method):
                    response = getattr(self.client, method)(f"{url}?audit={audit_id}")
                    self.assertEqual(response.status_code, 404)
        self.assertFalse(Finding.objects.exists())

    def test_audit_query_parameter_prefills_and_locks_audit(self):
        organization = Organization.objects.create(name="Test organization")
        audit = Audit.objects.create(organization=organization, auditor="Test auditor")
        request = RequestFactory().get("/finding/create", {"audit": audit.pk})

        view = FindingCreateView()
        view.setup(request)
        initial = view.get_initial()
        form = FindingForm(initial=initial)

        self.assertEqual(initial["audit"], audit)
        self.assertEqual(initial["organization"], organization)
        self.assertTrue(form.fields["audit"].disabled)
        self.assertTrue(form.fields["organization"].disabled)

        different_organization = Organization.objects.create(name="Unselected organization")
        different_audit = Audit.objects.create(
            organization=different_organization, auditor="Unselected auditor"
        )
        submitted = FindingForm(
            data={
                "audit": different_audit.pk,
                "organization": different_organization.pk,
                "short_description": "New finding",
                "severity": Finding.Severity.OBSERVATION,
            },
            initial=initial,
        )
        self.assertTrue(submitted.is_valid(), submitted.errors)
        self.assertEqual(submitted.cleaned_data["audit"], audit)
        self.assertEqual(submitted.cleaned_data["organization"], organization)

    def test_existing_finding_can_change_audit(self):
        organization = Organization.objects.create(name="Editable finding organization")
        original = Audit.objects.create(organization=organization, auditor="Original auditor")
        replacement = Audit.objects.create(organization=organization, auditor="New auditor")
        finding = Finding.objects.create(audit=original, short_description="Finding to move")

        form = FindingForm(instance=finding)
        self.assertFalse(form.fields["audit"].disabled)
        self.assertNotIn("organization", form.fields)

        form = FindingForm(
            data={
                "audit": replacement.pk,
                "short_description": finding.short_description,
                "severity": finding.severity,
            },
            instance=finding,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().audit, replacement)


class ActionCreateViewTest(TestCase):
    def test_invalid_finding_query_parameter_returns_404(self):
        user = get_user_model().objects.create_user(username="invalid_finding")
        self.client.force_login(user)
        url = reverse('conformity:action_create')

        for finding_id in ('abc', '1.5', ' ', '999999999999999999999999999999'):
            for method in ('get', 'post'):
                with self.subTest(finding_id=finding_id, method=method):
                    response = getattr(self.client, method)(f"{url}?finding={finding_id}")
                    self.assertEqual(response.status_code, 404)
        self.assertFalse(Action.objects.exists())

    def test_finding_query_parameter_prefills_and_locks_associated_findings(self):
        organization = Organization.objects.create(name="Action test organization")
        other_organization = Organization.objects.create(name="Other action organization")
        audit = Audit.objects.create(organization=organization, auditor="Action test auditor")
        finding = Finding.objects.create(audit=audit, short_description="Selected finding")
        other_finding = Finding.objects.create(audit=audit, short_description="Other finding")
        request = RequestFactory().get("/action/create", {"finding": finding.pk})

        view = ActionCreateView()
        view.setup(request)
        initial = view.get_initial()
        form = ActionForm(initial=initial)

        self.assertEqual(initial["associated_findings"], [finding])
        self.assertEqual(initial["organization"], organization.pk)
        self.assertTrue(form.fields["associated_findings"].disabled)
        self.assertTrue(form.fields["organization"].disabled)

        submitted = ActionForm(
            data={
                "title": "Corrective action",
                "status": Action.Status.ANALYSING,
                "organization": other_organization.pk,
                "associated_findings": [other_finding.pk],
            },
            initial=initial,
        )
        self.assertTrue(submitted.is_valid(), submitted.errors)
        action = submitted.save()
        self.assertEqual(action.organization, organization)
        self.assertEqual(list(action.associated_findings.all()), [finding])

    def test_existing_action_can_change_associated_findings(self):
        organization = Organization.objects.create(name="Editable action organization")
        audit = Audit.objects.create(organization=organization, auditor="Editable action auditor")
        original = Finding.objects.create(audit=audit, short_description="Original finding")
        replacement = Finding.objects.create(audit=audit, short_description="Replacement finding")
        action = Action.objects.create(title="Editable action")
        action.associated_findings.add(original)

        form = ActionForm(instance=action)
        self.assertFalse(form.fields["associated_findings"].disabled)

        form = ActionForm(
            data={
                "title": action.title,
                "status": action.status,
                "associated_findings": [replacement.pk],
            },
            instance=action,
        )
        self.assertTrue(form.is_valid(), form.errors)
        action = form.save()
        self.assertEqual(list(action.associated_findings.all()), [replacement])

    def test_finding_detail_links_to_prefilled_action_creation(self):
        user = get_user_model().objects.create_user(username="finding_action_link")
        self.client.force_login(user)
        organization = Organization.objects.create(name="Link test organization")
        audit = Audit.objects.create(organization=organization, auditor="Link test auditor")
        finding = Finding.objects.create(audit=audit, short_description="Finding with action link")

        response = self.client.get(reverse('conformity:finding_detail', args=[finding.pk]))

        self.assertEqual(response.status_code, 200)
        action_create_url = reverse('conformity:action_create')
        self.assertContains(response, f'href="{action_create_url}?finding={finding.pk}"')


class ConformityRelatedCreateViewTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="conformity_related")
        self.client.force_login(self.user)
        self.organization = Organization.objects.create(name="Conformity related organization")
        self.other_organization = Organization.objects.create(name="Other conformity organization")
        self.framework = Framework.objects.create(
            name="Conformity related framework", publish_by="Test publisher"
        )
        self.requirement = Requirement.objects.create(
            name="conformity-related-requirement", framework=self.framework, code="R1", title="Requirement"
        )
        self.conformity = Conformity.objects.create(
            organization=self.organization, requirement=self.requirement
        )
        self.other_requirement = Requirement.objects.create(
            name="other-conformity-requirement", framework=self.framework, code="R2", title="Other requirement"
        )
        self.other_conformity = Conformity.objects.create(
            organization=self.organization, requirement=self.other_requirement
        )

    def test_invalid_conformity_query_parameter_returns_404(self):
        for view_name, model in (('conformity:action_create', Action), ('conformity:control_create', Control)):
            url = reverse(view_name)
            for conformity_id in ('abc', '1.5', ' ', '999999999999999999999999999999'):
                for method in ('get', 'post'):
                    with self.subTest(view_name=view_name, conformity_id=conformity_id, method=method):
                        response = getattr(self.client, method)(f"{url}?conformity={conformity_id}")
                        self.assertEqual(response.status_code, 404)
            self.assertFalse(model.objects.exists())

    def test_conformity_prefills_and_locks_action(self):
        request = RequestFactory().get("/action/create", {"conformity": self.conformity.pk})
        view = ActionCreateView()
        view.setup(request)
        initial = view.get_initial()
        form = ActionForm(initial=initial)

        self.assertEqual(initial['associated_conformity'], [self.conformity])
        self.assertEqual(initial['organization'], self.organization.pk)
        self.assertTrue(form.fields['associated_conformity'].disabled)
        self.assertTrue(form.fields['organization'].disabled)

        submitted = ActionForm(
            data={
                'title': 'Corrective action for conformity',
                'status': Action.Status.ANALYSING,
                'organization': self.other_organization.pk,
                'associated_conformity': [self.other_conformity.pk],
            },
            initial=initial,
        )
        self.assertTrue(submitted.is_valid(), submitted.errors)
        action = submitted.save()
        self.assertEqual(action.organization, self.organization)
        self.assertEqual(list(action.associated_conformity.all()), [self.conformity])

    def test_action_form_filters_associations_by_organization(self):
        other_conformity = Conformity.objects.create(
            organization=self.other_organization, requirement=self.other_requirement
        )
        other_audit = Audit.objects.create(
            organization=self.other_organization, auditor="Other auditor"
        )
        other_finding = Finding.objects.create(
            audit=other_audit, short_description="Other finding"
        )
        organization_control = Control.objects.create(
            title="Organization control", organization=self.organization
        )
        other_control = Control.objects.create(
            title="Other control", organization=self.other_organization
        )
        organization_point = ControlPoint.objects.create(
            control=organization_control,
            period_start_date=date.today(),
            period_end_date=date.today(),
        )
        other_point = ControlPoint.objects.create(
            control=other_control,
            period_start_date=date.today(),
            period_end_date=date.today(),
        )

        form = ActionForm(initial={'organization': self.organization.pk})

        self.assertQuerySetEqual(
            form.fields['associated_conformity'].queryset,
            [self.conformity, self.other_conformity],
        )
        self.assertQuerySetEqual(
            form.fields['associated_findings'].queryset,
            [],
        )
        self.assertQuerySetEqual(
            form.fields['associated_controlPoints'].queryset,
            ControlPoint.objects.filter(control=organization_control),
        )
        self.assertNotIn(other_conformity, form.fields['associated_conformity'].queryset)
        self.assertNotIn(other_finding, form.fields['associated_findings'].queryset)
        self.assertNotIn(other_point, form.fields['associated_controlPoints'].queryset)

    def test_existing_action_can_change_associated_conformity(self):
        action = Action.objects.create(
            title="Editable conformity action", organization=self.organization
        )
        action.associated_conformity.add(self.conformity)

        form = ActionForm(instance=action)
        self.assertFalse(form.fields['associated_conformity'].disabled)
        self.assertFalse(form.fields['organization'].disabled)

        form = ActionForm(
            data={
                'title': action.title,
                'status': action.status,
                'organization': self.other_organization.pk,
                'associated_conformity': [self.other_conformity.pk],
            },
            instance=action,
        )
        self.assertTrue(form.is_valid(), form.errors)
        action = form.save()
        self.assertEqual(action.organization, self.other_organization)
        self.assertEqual(list(action.associated_conformity.all()), [self.other_conformity])

    def test_conformity_prefills_and_locks_control(self):
        request = RequestFactory().get("/control/create", {"conformity": self.conformity.pk})
        view = ControlCreateView()
        view.setup(request)
        initial = view.get_initial()
        form = ControlForm(initial=initial)

        self.assertEqual(initial['conformity'], [self.conformity])
        self.assertTrue(form.fields['conformity'].disabled)

        submitted = ControlForm(
            data={
                'title': 'Control for conformity',
                'conformity': [self.other_conformity.pk],
                'frequency': Control.Frequency.YEARLY,
                'level': Control.Level.FIRST,
            },
            initial=initial,
        )
        self.assertTrue(submitted.is_valid(), submitted.errors)
        control = submitted.save()
        self.assertEqual(list(control.conformity.all()), [self.conformity])

        self.assertEqual(initial['organization'], self.organization.pk)
        self.assertTrue(form.fields['organization'].disabled)

    def test_control_form_filters_associations_by_organization(self):
        organization_control = Control.objects.create(
            title="Organization control", organization=self.organization
        )
        other_control = Control.objects.create(
            title="Other control", organization=self.other_organization
        )
        form = ControlForm(initial={'organization': self.organization.pk})

        self.assertQuerySetEqual(
            form.fields['conformity'].queryset,
            [self.conformity, self.other_conformity],
        )
        self.assertQuerySetEqual(
            form.fields['control'].queryset,
            [organization_control],
        )
        self.assertNotIn(other_control, form.fields['control'].queryset)

    def test_existing_action_and_control_filter_associations_by_organization(self):
        organization_control = Control.objects.create(
            title="Organization control", organization=self.organization
        )
        other_control = Control.objects.create(
            title="Other control", organization=self.other_organization
        )
        action = Action.objects.create(
            title="Organization action", organization=self.organization
        )
        control = Control.objects.create(
            title="Editable control", organization=self.organization
        )

        action_form = ActionForm(instance=action)
        control_form = ControlForm(instance=control)

        self.assertNotIn(other_control, control_form.fields['control'].queryset)
        self.assertIn(organization_control, control_form.fields['control'].queryset)
        self.assertQuerySetEqual(
            action_form.fields['associated_conformity'].queryset,
            [self.conformity, self.other_conformity],
        )
        self.assertQuerySetEqual(
            control_form.fields['conformity'].queryset,
            [self.conformity, self.other_conformity],
        )

    def test_existing_control_can_change_conformity(self):
        control = Control.objects.create(title="Editable conformity control")
        control.conformity.add(self.conformity)

        form = ControlForm(instance=control)
        self.assertFalse(form.fields['conformity'].disabled)

        form = ControlForm(
            data={
                'title': control.title,
                'conformity': [self.other_conformity.pk],
                'frequency': control.frequency,
                'level': control.level,
            },
            instance=control,
        )
        self.assertTrue(form.is_valid(), form.errors)
        control = form.save()
        self.assertEqual(list(control.conformity.all()), [self.other_conformity])

    def test_conformity_form_links_to_prefilled_action_and_control_creation(self):
        response = self.client.get(reverse('conformity:conformity_form', args=[self.conformity.pk]))

        self.assertEqual(response.status_code, 200)
        action_create_url = reverse('conformity:action_create')
        control_create_url = reverse('conformity:control_create')
        self.assertContains(
            response, f'href="{action_create_url}?conformity={self.conformity.pk}"'
        )
        self.assertContains(
            response, f'href="{control_create_url}?conformity={self.conformity.pk}"'
        )

    def test_action_creation_from_conformity_prefills_organization(self):
        response = self.client.get(
            reverse('conformity:action_create'),
            {'conformity': self.conformity.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<option value="{self.organization.pk}" selected>',
            html=False,
        )
