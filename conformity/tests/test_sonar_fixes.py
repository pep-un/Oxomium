from django.test import RequestFactory, TestCase

from conformity.forms import FindingForm
from conformity.models import Audit, Organization
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
