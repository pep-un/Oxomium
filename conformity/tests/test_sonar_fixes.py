from django.test import RequestFactory, TestCase

from conformity.forms import FindingForm
from conformity.models import Audit, Finding, Organization
from conformity.views import FindingCreateView


class FindingCreateViewTest(TestCase):
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
