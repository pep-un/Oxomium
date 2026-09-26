from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.utils import timezone

from conformity import views
from conformity.models import (
    Organization, Framework, Requirement, Conformity,
    Audit, Action, Finding, Control, ControlPoint, Attachment
)
from conformity.views import ConformityUpdateView

User = get_user_model()


class BaseDataMixin:
    """
    Base mixin for preparing minimal test data.
    Key points:
      - Do NOT set `name` on Requirement (it is globally unique).
      - Instead, set `code` and let model signals build the unique `name`.
      - Each subclass must override FRAMEWORK_NAME to avoid collisions.
    """

    FRAMEWORK_NAME = "FW-BASE"

    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()

        # User
        self.user = User.objects.create_user(username="user1", password="p@ss")

        # Framework and Organization
        self.fw = Framework.objects.create(
            name=self.FRAMEWORK_NAME,  # unique per test class
            publish_by="ISO",
            version=1,
        )
        self.org = Organization.objects.create(name="Org-A")

        # Minimal MPTT tree (root + 2 children).
        # Use `code` only, let model compute `name`.
        self.req_root = Requirement.objects.create(
            code="ROOT", title="Root", framework=self.fw, parent=None, order=1
        )
        self.req_a = Requirement.objects.create(
            code="A", title="A", framework=self.fw, parent=self.req_root, order=1
        )
        self.req_b = Requirement.objects.create(
            code="B", title="B", framework=self.fw, parent=self.req_root, order=2
        )

        # Conformities
        self.c_root = Conformity.objects.create(
            organization=self.org, requirement=self.req_root
        )
        self.c_a = Conformity.objects.create(
            organization=self.org, requirement=self.req_a, responsible=self.user
        )
        self.c_b = Conformity.objects.create(
            organization=self.org, requirement=self.req_b
        )

        # Audit and Findings
        self.audit = Audit.objects.create(
            organization=self.org,
            auditor="Auditor Inc.",
            report_date=timezone.now().date(),
        )
        self.find_obs = Finding.objects.create(
            audit=self.audit,
            short_description="Obs",
            severity=Finding.Severity.OBSERVATION,
        )
        self.find_maj_arch = Finding.objects.create(
            audit=self.audit,
            short_description="MajA",
            severity=Finding.Severity.MAJOR,
            archived=True,
        )

        # Actions
        self.act1 = Action.objects.create(
            title="Act1", owner=self.user, organization=self.org
        )
        self.act2 = Action.objects.create(
            title="Act2", organization=self.org
        )

        # Controls and ControlPoints
        self.ctrl_q = Control.objects.create(
            title="CtrlQ",
            organization=self.org,
            frequency=Control.Frequency.QUARTERLY,
            level=Control.Level.FIRST,
        )
        self.cp = ControlPoint.objects.create(
            control=self.ctrl_q,
            period_start_date=timezone.now().date().replace(month=1, day=1),
            period_end_date=timezone.now().date().replace(month=12, day=31),
            status=ControlPoint.Status.TOBEEVALUATED,
        )


class LoginRequired(BaseDataMixin, TestCase):
    FRAMEWORK_NAME = "FW-LoginRequired"

    def test_home_requires_login(self):
        """HomeView should redirect unauthenticated users."""
        request = self.factory.get("/")
        request.user = mock.Mock(is_authenticated=False)
        response = views.HomeView.as_view()(request)
        self.assertIn(response.status_code, (301, 302))


class HomeViewContext(BaseDataMixin, TestCase):
    FRAMEWORK_NAME = "FW-HomeView"

    def test_context_lists_and_filters(self):
        """HomeView context must contain expected lists and proper filters."""
        request = self.factory.get("/home")
        request.user = self.user
        resp = views.HomeView.as_view()(request)
        self.assertEqual(resp.status_code, 200)

        ctx = resp.context_data
        self.assertIn("conformity_list", ctx)
        # Only root conformity should be in level=0 list
        self.assertIn(self.c_root, list(ctx["conformity_list"]))
        self.assertNotIn(self.c_a, list(ctx["conformity_list"]))
        self.assertIn(self.act1, list(ctx["my_action"]))
        self.assertIn(self.c_a, list(ctx["my_conformity"]))
        self.assertIn(self.cp, list(ctx["cp_list"]))


class FindingIndexView(BaseDataMixin, TestCase):
    FRAMEWORK_NAME = "FW-FindingIndex"

    def test_queryset_filters_severity_and_archived(self):
        """FindingIndexView should exclude archived findings."""
        request = self.factory.get("/findings")
        request.user = self.user
        resp = views.FindingIndexView.as_view()(request)
        self.assertEqual(resp.status_code, 200)

        qs = list(resp.context_data["object_list"])
        self.assertIn(self.find_obs, qs)
        self.assertNotIn(self.find_maj_arch, qs)


class ConformityIndexViews(BaseDataMixin, TestCase):
    FRAMEWORK_NAME = "FW-ConformityIndex"

    def test_conformity_index_queryset_level0(self):
        """ConformityIndexView must only return level=0 conformities."""
        request = self.factory.get("/conformities")
        request.user = self.user
        resp = views.ConformityIndexView.as_view()(request)
        self.assertEqual(resp.status_code, 200)
        objs = list(resp.context_data["object_list"])
        self.assertEqual(objs, [self.c_root])

    def test_progress_bar_shows_zero_when_not_yet_evaluated(self):
        self.client.force_login(self.user)
        url = reverse('conformity:conformity_index')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'style="width: 0%"')
        self.assertContains(response, 'aria-valuenow="0"')
        self.assertNotContains(response, 'None%')

        self.c_root.status = 80
        self.c_root.save(update_fields=['status'])
        response = self.client.get(url)
        self.assertContains(response, 'style="width: 80%"')
        self.assertContains(response, 'aria-valuenow="80"')

    def test_conformity_detail_index_queryset_scoped(self):
        """ConformityDetailIndexView must filter by org and framework (pol)."""
        request = self.factory.get("/conformities/detail")
        request.user = self.user
        resp = views.ConformityDetailIndexView.as_view()(request, org=self.org.id, pol=self.fw.id)
        self.assertEqual(resp.status_code, 200)
        objs = list(resp.context_data["object_list"])
        self.assertEqual(objs, [self.c_root])

    def test_conformity_detail_returns_404_without_review(self):
        """An organization/framework without conformities must return a 404."""
        other_framework = Framework.objects.create(name="FW-No-Conformity")
        self.client.force_login(self.user)
        url = reverse(
            "conformity:conformity_detail_index",
            kwargs={"org": self.org.id, "pol": other_framework.id},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

class ConformitySaveNextTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="u1", password="p")
        self.org = Organization.objects.create(name="Org-SaveNext")
        self.fw = Framework.objects.create(name="FW-SaveNext")
        self.root = Requirement.objects.create(framework=self.fw, code="R")
        self.a = Requirement.objects.create(framework=self.fw, code="A", parent=self.root, order=1)
        self.b = Requirement.objects.create(framework=self.fw, code="B", parent=self.root, order=2)
        # Conformities for A and B (root is auto via signals in ton setup, sinon crée-les)
        self.ca = Conformity.objects.create(organization=self.org, requirement=self.a)
        self.cb = Conformity.objects.create(organization=self.org, requirement=self.b)

    def test_save_next_redirects_to_sibling(self):
        # Simulate POST with "save_next"
        url = reverse("conformity:conformity_form", args=[self.ca.pk])
        data = {"status": 100, "applicable": True, "action": "save_next"}
        request = self.factory.post(url, data=data)
        request.user = self.user

        resp = ConformityUpdateView.as_view()(request, pk=self.ca.pk)
        self.assertIn(resp.status_code, (301, 302))
        self.assertIn(str(self.cb.pk), resp.url, "Should redirect to the next sibling conformity")

    def test_save_next_no_sibling_falls_back(self):
        # Remove B so A has no next sibling -> should behave like normal valid POST (redirect to success_url)
        self.cb.delete()
        url = reverse("conformity:conformity_form", args=[self.ca.pk])
        data = {"status": 0, "applicable": True, "action": "save_next"}
        request = self.factory.post(url, data=data)
        request.user = self.user

        resp = ConformityUpdateView.as_view()(request, pk=self.ca.pk)
        self.assertIn(resp.status_code, (301, 302), "Should still redirect (normal success flow)")

class SharedUxComponentsTests(BaseDataMixin, TestCase):
    FRAMEWORK_NAME = "FW-SharedUx"

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def test_action_list_uses_shared_toolbar_and_active_filter_state(self):
        response = self.client.get(reverse("conformity:action_index"), {"title": "Act"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="d-flex flex-wrap gap-2 align-items-center justify-content-between mb-3 list-toolbar"')
        self.assertContains(response, "Reset filters")
        self.assertContains(response, "1 active")
        self.assertNotContains(response, "btn-danger")

    def test_pagination_does_not_mark_filters_active(self):
        response = self.client.get(reverse("conformity:action_index"), {"page": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, ">Active<")

    def test_audit_detail_uses_accessible_breadcrumb(self):
        response = self.client.get(reverse("conformity:audit_detail", args=[self.audit.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, reverse("conformity:audit_index"))

    def test_control_detail_does_not_duplicate_return_navigation(self):
        response = self.client.get(reverse("conformity:control_detail", args=[self.ctrl_q.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-label="Breadcrumb"')
        self.assertNotContains(response, "Return to control")
