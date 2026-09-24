from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from conformity.forms import ActionForm, FindingForm
from conformity.models import Action, Audit, Finding, Organization
from conformity.views import ActionCreateView, FindingCreateView


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
        self.assertTrue(form.fields["audit"].disabled)

        different_audit = Audit.objects.create(
            organization=organization, auditor="Unselected auditor"
        )
        submitted = FindingForm(
            data={
                "audit": different_audit.pk,
                "short_description": "New finding",
                "severity": Finding.Severity.OBSERVATION,
            },
            initial=initial,
        )
        self.assertTrue(submitted.is_valid(), submitted.errors)
        self.assertEqual(submitted.cleaned_data["audit"], audit)

    def test_existing_finding_can_change_audit(self):
        organization = Organization.objects.create(name="Editable finding organization")
        original = Audit.objects.create(organization=organization, auditor="Original auditor")
        replacement = Audit.objects.create(organization=organization, auditor="New auditor")
        finding = Finding.objects.create(audit=original, short_description="Finding to move")

        form = FindingForm(instance=finding)
        self.assertFalse(form.fields["audit"].disabled)

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
        audit = Audit.objects.create(organization=organization, auditor="Action test auditor")
        finding = Finding.objects.create(audit=audit, short_description="Selected finding")
        other_finding = Finding.objects.create(audit=audit, short_description="Other finding")
        request = RequestFactory().get("/action/create", {"finding": finding.pk})

        view = ActionCreateView()
        view.setup(request)
        initial = view.get_initial()
        form = ActionForm(initial=initial)

        self.assertEqual(initial["associated_findings"], [finding])
        self.assertTrue(form.fields["associated_findings"].disabled)

        submitted = ActionForm(
            data={
                "title": "Corrective action",
                "status": Action.Status.ANALYSING,
                "associated_findings": [other_finding.pk],
            },
            initial=initial,
        )
        self.assertTrue(submitted.is_valid(), submitted.errors)
        action = submitted.save()
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
