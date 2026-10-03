from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.utils import timezone
from constance.test import override_config

from conformity import views
from conformity.forms import FindingForm
from conformity.models import (
    Organization, Framework, Requirement, Conformity,
    Audit, Action, Finding, Control, ControlPoint, Attachment, Indicator, IndicatorPoint
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
            valid_to=timezone.now() - timedelta(minutes=1),
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

    def test_default_filters_preserve_active_findings_view(self):
        """Default URL filters preserve the former Active findings result."""
        request = self.factory.get(
            "/findings",
            {
                "nature": ["CRT", "MAJ", "MIN", "OBS"],
                "status": "active",
            },
        )
        request.user = self.user
        resp = views.FindingIndexView.as_view()(request)
        self.assertEqual(resp.status_code, 200)

        qs = list(resp.context_data["object_list"])
        self.assertIn(self.find_obs, qs)
        self.assertNotIn(self.find_maj_arch, qs)

    def test_finding_queryset_can_show_invalidated_items(self):
        request = self.factory.get(
            "/findings",
            {"status": "invalidated"},
        )
        request.user = self.user
        resp = views.FindingIndexView.as_view()(request)
        self.assertEqual(resp.status_code, 200)

        qs = list(resp.context_data["object_list"])
        self.assertIn(self.find_maj_arch, qs)
        self.assertNotIn(self.find_obs, qs)


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

    def test_status_bar_shows_not_evaluated_and_leaf_distribution(self):
        self.client.force_login(self.user)
        url = reverse('conformity:conformity_index')

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'aria-label="Evidence status: 0 compliant, 0 partially compliant, '
            '0 non-compliant, 0 inconclusive, 2 not evaluated"',
        )
        self.assertNotContains(response, 'None%')

        self.c_a.evidence_state = Conformity.EvidenceState.COMPLIANT
        self.c_a.save(update_fields=['evidence_state'])

        response = self.client.get(url)
        self.assertContains(response, 'style="width: 50.0%"')
        self.assertContains(response, 'title="Compliant: 1"')

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

    def test_crud_forms_use_shared_footer_toolbar(self):
        indicator = Indicator.objects.create(
            name="Toolbar indicator",
            responsible=self.user,
        )
        indicator_point = IndicatorPoint.objects.create(
            indicator=indicator,
            period_start_date=timezone.localdate(),
            period_end_date=timezone.localdate(),
        )
        form_urls = (
            reverse("conformity:audit_form", args=[self.audit.pk]),
            reverse("conformity:finding_form", args=[self.find_obs.pk]),
            reverse("conformity:organization_form", args=[self.org.pk]),
            reverse("conformity:action_form", args=[self.act1.pk]),
            reverse("conformity:control_form", args=[self.ctrl_q.pk]),
            reverse("conformity:controlpoint_form", args=[self.cp.pk]),
            reverse("conformity:conformity_form", args=[self.c_a.pk]),
            reverse("conformity:indicator_form", args=[indicator.pk]),
            reverse("conformity:indicatorpoint_form", args=[indicator_point.pk]),
        )

        for url in form_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "form-toolbar")
                self.assertContains(response, 'name="action" value="save"')
                self.assertContains(response, 'name="action" value="save_stay"')
                self.assertContains(response, "btn btn-outline-danger w-100")

    def test_save_next_only_appears_on_conformity_form(self):
        conformity_response = self.client.get(
            reverse("conformity:conformity_form", args=[self.c_a.pk])
        )
        self.assertContains(conformity_response, "Save &amp; Next")

        for url in (
            reverse("conformity:audit_form", args=[self.audit.pk]),
            reverse("conformity:finding_form", args=[self.find_obs.pk]),
            reverse("conformity:organization_form", args=[self.org.pk]),
            reverse("conformity:action_form", args=[self.act1.pk]),
            reverse("conformity:control_form", args=[self.ctrl_q.pk]),
            reverse("conformity:controlpoint_form", args=[self.cp.pk]),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertNotContains(response, "Save &amp; Next")

    def test_organization_create_save_stay_redirects_to_edit_form(self):
        response = self.client.post(
            reverse("conformity:organization_create"),
            {
                "name": "Save Stay Organization",
                "administrative_id": "",
                "description": "",
                "action": "save_stay",
            },
        )
        organization = Organization.objects.get(name="Save Stay Organization")
        self.assertRedirects(
            response,
            reverse("conformity:organization_form", args=[organization.pk]),
            fetch_redirect_response=False,
        )

    def test_action_list_uses_shared_toolbar_and_active_filter_state(self):
        response = self.client.get(reverse("conformity:action_index"), {"title": "Act"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="d-flex flex-wrap gap-2 align-items-center mb-3 list-toolbar"')
        self.assertContains(response, "Reset filters")
        self.assertContains(response, 'btn btn-primary dropdown-toggle w-100 d-flex align-items-center text-start')
        self.assertContains(response, 'badge text-bg-light">1</span>')
        self.assertContains(
            response,
            'href="' + reverse("conformity:action_create") + '"',
        )
        self.assertContains(response, 'class="btn btn-secondary dropdown-toggle w-100 d-flex align-items-center text-start"')
        self.assertContains(response, "2 résultats affichés")
        self.assertContains(response, "Export CSV (All)")
        self.assertContains(response, "Export XLSX (All)")
        self.assertContains(response, "Export CSV (Selection)")
        self.assertContains(response, "Export XLSX (Selection)")
        self.assertNotContains(response, '<h2 class="h6 mb-0">Filters</h2>')
        self.assertContains(response, "btn-outline-danger")

    def test_pagination_does_not_mark_filters_active(self):
        response = self.client.get(reverse("conformity:action_index"), {"page": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'btn btn-secondary dropdown-toggle')
        self.assertNotContains(response, 'badge text-bg-light ms-1">')
        self.assertContains(response, 'btn btn-outline-danger disabled')
        self.assertContains(response, 'aria-disabled="true" tabindex="-1"')
        self.assertContains(response, "Export CSV (All)")
        self.assertContains(response, "Export XLSX (All)")
        self.assertNotContains(response, "Export CSV (Selection)")
        self.assertNotContains(response, "Export XLSX (Selection)")

    def test_rich_table_sorting_uses_pk_tie_breaker(self):
        table = views.ActionTable(
            Action.objects.all(),
            order_by=("title",),
        )

        self.assertEqual(
            tuple(str(item) for item in table.columns["title"].order_by),
            ("title", "pk"),
        )

        table.order_by = ("-title",)
        self.assertEqual(
            tuple(str(item) for item in table.columns["title"].order_by),
            ("-title", "-pk"),
        )

    def test_paginated_list_querysets_end_with_pk_tie_breaker(self):
        request = self.factory.get("/list")
        request.user = self.user

        view_classes = (
            views.AuditIndexView,
            views.FindingIndexView,
            views.OrganizationIndexView,
            views.FrameworkIndexView,
            views.ConformityIndexView,
            views.ActionIndexView,
            views.ControlPointIndexView,
            views.AttachmentIndexView,
            views.AuditLogDetailView,
        )

        for view_class in view_classes:
            with self.subTest(view=view_class.__name__):
                view = view_class()
                view.request = request
                queryset = view.get_queryset()
                self.assertTrue(queryset.query.order_by)
                self.assertEqual(str(queryset.query.order_by[-1]).lstrip("-"), "pk")

    def test_paginated_toolbar_shows_total_and_visible_results(self):
        with override_config(TABLE_PAGE_SIZE=1):
            response = self.client.get(reverse("conformity:action_index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2 résultats, dont 1 affiché")

    def test_empty_dataset_offers_create_action(self):
        Action.objects.all().delete()
        response = self.client.get(reverse("conformity:action_index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No actions have been created yet.")
        self.assertContains(response, 'href="' + reverse("conformity:action_create") + '"', count=2)
        self.assertNotContains(response, "No results match the active filters.")

    def test_filtered_empty_result_offers_reset_instead_of_create(self):
        response = self.client.get(reverse("conformity:action_index"), {"title": "missing-action"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No results match the active filters.")
        self.assertContains(response, "Reset filters", count=2)
        self.assertContains(response, 'href="?" class="btn btn-outline-danger"')
        self.assertContains(response, 'href="' + reverse("conformity:action_create") + '"', count=1)

    def test_empty_state_without_create_url_does_not_offer_create(self):
        Finding.objects.all().delete()
        response = self.client.get(
            reverse("conformity:finding_index"),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No results match the active filters.")
        self.assertNotContains(response, "> Create</a>")

    def test_indicator_cards_use_shared_empty_state(self):
        response = self.client.get(reverse("conformity:indicator_index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No indicators have been created yet.")
        self.assertContains(response, reverse("conformity:indicator_create"))

    def test_audit_detail_uses_object_title_and_back_link(self):
        response = self.client.get(reverse("conformity:audit_detail", args=[self.audit.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="header-back-link"')
        self.assertContains(response, reverse("conformity:audit_index"))
        self.assertNotContains(response, 'aria-label="Breadcrumb"')

    def test_control_detail_uses_title_and_back_link(self):
        response = self.client.get(reverse("conformity:control_detail", args=[self.ctrl_q.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.ctrl_q.title)
        self.assertContains(response, 'class="header-back-link"')
        self.assertContains(response, reverse("conformity:control_index"))

class FindingEvidenceFormTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Finding form organization")
        self.audit = Audit.objects.create(
            organization=self.organization,
            auditor="Auditor",
        )

    def test_new_finding_defaults_and_optional_audit(self):
        before = timezone.now()
        form = FindingForm()
        after = timezone.now()

        self.assertFalse(form.fields["audit"].required)
        self.assertEqual(form.fields["cvss"].widget.attrs["min"], 0)
        self.assertEqual(form.fields["cvss"].widget.attrs["max"], 10)
        self.assertEqual(form.fields["cvss"].widget.attrs["step"], 0.1)

        valid_from = form.initial["valid_from"]
        valid_to = form.initial["valid_to"]
        self.assertGreaterEqual(valid_from, before)
        self.assertLessEqual(valid_from, after)
        self.assertEqual(valid_to.year, valid_from.year + 3)
        self.assertEqual(valid_to.month, valid_from.month)
        self.assertEqual(valid_to.day, valid_from.day)

    def test_finding_can_be_created_without_audit(self):
        finding = Finding(
            short_description="Discovery outside audit",
            severity=Finding.Severity.MAJOR,
            cvss=0,
        )
        finding.full_clean(exclude=["valid_from"])
        finding.save()

        self.assertIsNone(finding.audit)
        self.assertEqual(finding.cvss, 0)
        self.assertIsNotNone(finding.valid_from)
        self.assertIsNotNone(finding.valid_to)


class ConformityPeriodicEvidenceCreationTests(BaseDataMixin, TestCase):
    FRAMEWORK_NAME = "FW-ConformityPeriodicEvidenceCreation"

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def test_evidence_creation_shows_organization_before_requirements(self):
        self.org.description = "Organization description for evidence context."
        self.org.save(update_fields=["description"])

        response = self.client.get(
            reverse("conformity:manual_evidence_create", args=[self.c_a.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Associated organization")
        self.assertContains(response, self.org.name)
        self.assertContains(response, self.org.description)
        content = response.content.decode()
        self.assertLess(
            content.index("Associated organization"),
            content.index("Associated requirements"),
        )

    def test_leaf_conformity_offers_control_and_indicator_creation(self):
        response = self.client.get(
            reverse("conformity:conformity_form", args=[self.c_a.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'{reverse("conformity:control_create")}?conformity={self.c_a.pk}',
        )
        self.assertContains(
            response,
            f'{reverse("conformity:indicator_create")}?conformity={self.c_a.pk}',
        )

    def test_control_create_from_conformity_preselects_target_and_returns(self):
        url = f'{reverse("conformity:control_create")}?conformity={self.c_a.pk}'

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].fields["conformity"].disabled)
        self.assertEqual(
            list(response.context["form"].initial["conformity"]),
            [self.c_a],
        )

        response = self.client.post(
            url,
            {
                "title": "Control from conformity",
                "description": "",
                "frequency": Control.Frequency.YEARLY,
                "level": Control.Level.FIRST,
            },
        )

        control = Control.objects.get(title="Control from conformity")
        self.assertEqual(list(control.conformity.all()), [self.c_a])
        self.assertRedirects(
            response,
            reverse("conformity:conformity_form", args=[self.c_a.pk]),
        )

    def test_indicator_create_from_conformity_preselects_target_and_returns(self):
        url = f'{reverse("conformity:indicator_create")}?conformity={self.c_a.pk}'

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].fields["conformity"].disabled)
        self.assertEqual(
            list(response.context["form"].initial["conformity"]),
            [self.c_a],
        )

        response = self.client.post(
            url,
            {
                "name": "Indicator from conformity",
                "goal": "",
                "source": "",
                "formula": "",
                "worst": 0,
                "critical": 20,
                "warning": 80,
                "best": 100,
                "responsible": self.user.pk,
                "frequency": Indicator.Frequency.QUARTERLY,
            },
        )

        indicator = Indicator.objects.get(name="Indicator from conformity")
        self.assertEqual(list(indicator.conformity.all()), [self.c_a])
        self.assertRedirects(
            response,
            reverse("conformity:conformity_form", args=[self.c_a.pk]),
        )

