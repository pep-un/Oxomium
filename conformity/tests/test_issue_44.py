from django.contrib.auth import get_user_model
from django.test import TestCase
from constance.test import override_config
from django.urls import reverse

from conformity.models import Action, Audit, Control, ControlPoint, Finding, Organization
from conformity.tables import (
    ACTION_STATUS_STYLES, CONTROL_POINT_STATUS_STYLES, ActionTable, AuditTable,
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


class StatusColumnRenderingTests(TestCase):
    def test_action_status_uses_raw_choice_value_for_style_lookup(self):
        action = Action(status=Action.Status.PLANNING)
        column = StatusColumn(ACTION_STATUS_STYLES)

        html = str(column.render(action.get_status_display(), action))

        self.assertIn("bi-hexagon-fill text-primary", html)
        self.assertIn("Planning", html)

    def test_frozen_action_status_uses_info_outline(self):
        action = Action(status=Action.Status.FROZEN)
        column = StatusColumn(ACTION_STATUS_STYLES)

        html = str(column.render(action.get_status_display(), action))

        self.assertIn("bi-hexagon text-info", html)
        self.assertIn("Frozen", html)

    def test_control_point_status_uses_raw_choice_value_for_style_lookup(self):
        control_point = ControlPoint(status=ControlPoint.Status.NONCOMPLIANT)
        column = StatusColumn(CONTROL_POINT_STATUS_STYLES)

        html = str(column.render(control_point.get_status_display(), control_point))

        self.assertIn("bi-hexagon-fill text-danger", html)
        self.assertIn("Non-Compliant", html)


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

