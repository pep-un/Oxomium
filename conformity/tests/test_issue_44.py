from django.contrib.auth import get_user_model
from django.test import TestCase
from django.template.loader import render_to_string
from constance.test import override_config
from django.urls import reverse

from conformity.models import Action, Audit, Control, ControlPoint, Finding, Organization
from conformity.tables import (
    CONTROL_POINT_STATUS_STYLES, ActionTable, AuditTable,
    ConformityTable, ControlTable, ControlPointTable, FindingTable, FrameworkTable,
    OrganizationTable, StatusColumn,
)
from conformity.filterset import ConformityFilter, ControlPointFilter, FindingFilter
from conformity.views import (
    ActionIndexView, AuditIndexView, ConformityIndexView, ControlIndexView,
    ControlPointIndexView, FindingIndexView, FrameworkIndexView,
    OrganizationIndexView,
)


class RichTableConfigurationTests(TestCase):
    def test_all_tabular_index_views_have_explicit_table_classes(self):
        expected = {
            ActionIndexView: ActionTable,
            AuditIndexView: AuditTable,
            ConformityIndexView: ConformityTable,
            ControlIndexView: ControlTable,
            ControlPointIndexView: ControlPointTable,
            FindingIndexView: FindingTable,
            FrameworkIndexView: FrameworkTable,
            OrganizationIndexView: OrganizationTable,
        }
        for view, table in expected.items():
            with self.subTest(view=view.__name__):
                self.assertIs(view.table_class, table)

    def test_secondary_navigation_filters_are_available(self):
        self.assertIn("audit", FindingFilter.base_filters)
        self.assertIn("action", FindingFilter.base_filters)
        self.assertIn("action", ConformityFilter.base_filters)
        self.assertIn("action", ControlPointFilter.base_filters)

    def test_primary_columns_share_name_and_width(self):
        table_classes = (
            ActionTable,
            AuditTable,
            ConformityTable,
            ControlTable,
            ControlPointTable,
            FindingTable,
            FrameworkTable,
            OrganizationTable,
        )
        for table_class in table_classes:
            with self.subTest(table=table_class.__name__):
                table = table_class([])
                first_column = next(iter(table.columns))
                self.assertEqual(first_column.verbose_name, "Name")
                self.assertIn("col-2", first_column.attrs["th"]["class"])
                self.assertIn("text-start", first_column.attrs["th"]["class"])
                self.assertIn("col-2", first_column.attrs["td"]["class"])
                self.assertIn("text-start", first_column.attrs["td"]["class"])

    def test_control_point_name_uses_control_title(self):
        self.assertEqual(
            str(ControlPointTable.base_columns["name"].accessor),
            "control__title",
        )


class ActionStatusComponentTests(TestCase):
    def test_planning_uses_primary_filled_hexagon(self):
        action = Action(status=Action.Status.PLANNING)

        html = render_to_string(
            "conformity/includes/action_status.html",
            {"action": action},
        )

        self.assertIn("bi-hexagon-fill text-primary", html)
        self.assertIn("Planning", html)

    def test_frozen_uses_info_outline_hexagon(self):
        action = Action(status=Action.Status.FROZEN)

        html = render_to_string(
            "conformity/includes/action_status.html",
            {"action": action},
        )

        self.assertIn("bi-hexagon text-info", html)
        self.assertIn("Frozen", html)


class StatusColumnRenderingTests(TestCase):
    def test_control_point_status_uses_raw_choice_value_for_style_lookup(self):
        control_point = ControlPoint(status=ControlPoint.Status.NONCOMPLIANT)
        column = StatusColumn(CONTROL_POINT_STATUS_STYLES)

        html = str(column.render(control_point.get_status_display(), control_point))

        self.assertIn("bi-hexagon-fill text-danger", html)
        self.assertIn("Non-Compliant", html)


class FindingActionStatusTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="finding-status")
        organization = Organization.objects.create(name="Finding status org")
        cls.audit = Audit.objects.create(
            name="Finding status audit",
            organization=organization,
            auditor="Auditor",
        )
        cls.finding = Finding.objects.create(
            name="Finding status",
            short_description="Finding status",
            audit=cls.audit,
            severity=Finding.Severity.MAJOR,
            cvss=7.0,
        )
        cls.action = Action.objects.create(
            title="Planning action",
            status=Action.Status.PLANNING,
        )
        cls.action.associated_findings.add(cls.finding)

    def setUp(self):
        self.client.force_login(self.user)

    def test_finding_detail_wraps_shared_action_status_in_neutral_pill(self):
        response = self.client.get(
            reverse("conformity:finding_detail", args=[self.finding.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'badge rounded-pill text-bg-light text-dark border col-5 text-center',
        )
        self.assertContains(response, "bi-hexagon-fill text-primary")
        self.assertContains(response, "Planning")


class FindingCvssBadgeTests(TestCase):
    def test_critical_badge_includes_severity_and_score(self):
        finding = Finding(severity=Finding.Severity.CRITICAL, cvss=9.9)

        html = render_to_string(
            "conformity/includes/finding_cvss_badge.html",
            {"finding": finding},
        )

        self.assertIn("text-bg-dark", html)
        self.assertIn("cvss-badge", html)
        self.assertIn("Critical (9.9)", html)

    def test_other_badge_uses_light_style(self):
        finding = Finding(severity=Finding.Severity.OTHER, cvss=4.2)

        html = render_to_string(
            "conformity/includes/finding_cvss_badge.html",
            {"finding": finding},
        )

        self.assertIn("text-bg-light text-dark border", html)
        self.assertIn("Other (4.2)", html)

    def test_missing_cvss_score_uses_dash(self):
        finding = Finding(severity=Finding.Severity.MINOR, cvss=None)

        html = render_to_string(
            "conformity/includes/finding_cvss_badge.html",
            {"finding": finding},
        )

        self.assertIn("Minor (-)", html)


class RichTableInteractionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="issue44")
        Organization.objects.bulk_create(
            Organization(name=f"Alpha {index:02d}", description="matching")
            for index in range(25)
        )
        Organization.objects.create(name="Beta", description="not matching")
        organization = Organization.objects.order_by("pk").first()
        cls.audit = Audit.objects.create(
            name="Navigation audit",
            organization=organization,
            auditor="Auditor",
        )
        cls.relation_only_finding = Finding.objects.create(
            name="Positive relation finding",
            short_description="Only visible through explicit relation navigation",
            audit=cls.audit,
            severity=Finding.Severity.POSITIVE,
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_filter_sort_and_pagination_work_together(self):
        response = self.client.get(
            reverse("conformity:organization_index"),
            {"name": "Alpha", "sort": "-name", "page": "2"},
        )

        self.assertEqual(response.status_code, 200)
        table = response.context["table"]
        self.assertEqual(table.paginator.per_page, 20)
        self.assertEqual(table.paginator.count, 25)
        self.assertEqual([row.record.name for row in table.page.object_list],
                         ["Alpha 04", "Alpha 03", "Alpha 02", "Alpha 01", "Alpha 00"])
        self.assertContains(response, "sort=-name")
        self.assertContains(response, "name=Alpha")

    @override_config(TABLE_PAGE_SIZE=7)
    def test_page_size_is_configurable(self):
        response = self.client.get(reverse("conformity:organization_index"))

        self.assertEqual(response.status_code, 200)
        table = response.context["table"]
        self.assertEqual(table.paginator.per_page, 7)
        self.assertEqual(len(table.page.object_list), 7)

    def test_sorted_header_exposes_direction_classes_for_styling(self):
        url = reverse("conformity:organization_index")

        ascending = self.client.get(url, {"sort": "name"})
        self.assertEqual(ascending.status_code, 200)
        self.assertContains(ascending, 'class="asc orderable"')

        descending = self.client.get(url, {"sort": "-name"})
        self.assertEqual(descending.status_code, 200)
        self.assertContains(descending, 'class="desc orderable"')

    def test_all_rich_table_indexes_render(self):
        view_names = (
            "conformity:action_index",
            "conformity:audit_index",
            "conformity:conformity_index",
            "conformity:control_index",
            "conformity:controlpoint_index",
            "conformity:finding_index",
            "conformity:framework_index",
            "conformity:organization_index",
        )
        for view_name in view_names:
            with self.subTest(view_name=view_name):
                response = self.client.get(reverse(view_name))
                self.assertEqual(response.status_code, 200)

    def test_relation_filtered_findings_include_items_hidden_from_general_list(self):
        general = self.client.get(reverse("conformity:finding_index"))
        general_ids = [
            row.record.pk for row in general.context["table"].page.object_list
        ]
        self.assertNotIn(self.relation_only_finding.pk, general_ids)

        filtered = self.client.get(
            reverse("conformity:finding_index"),
            {"audit": self.audit.pk},
        )
        filtered_ids = [
            row.record.pk for row in filtered.context["table"].page.object_list
        ]
        self.assertIn(self.relation_only_finding.pk, filtered_ids)


    def test_control_detail_renders_generated_control_points(self):
        control = Control.objects.create(
            title="Rendered control",
            frequency=Control.Frequency.YEARLY,
        )
        control_points = control.get_controlpoint()
        self.assertTrue(control_points.exists())

        control_point = control_points.first()
        response = self.client.get(
            reverse("conformity:control_detail", args=[control.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            control_point.period_start_date.strftime("%d-%b-%Y"),
        )
        self.assertContains(
            response,
            control_point.period_end_date.strftime("%d-%b-%Y"),
        )


    def test_primary_label_links_to_organization_detail(self):
        organization = Organization.objects.order_by("pk").first()
        response = self.client.get(reverse("conformity:organization_index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("conformity:organization_detail", args=[organization.pk]),
        )

