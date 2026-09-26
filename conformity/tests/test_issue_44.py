from django.contrib.auth import get_user_model
from django.test import TestCase
from constance.test import override_config
from django.urls import reverse

from conformity.models import Organization
from conformity.tables import (
    ActionTable, AuditTable, ConformityTable, ControlTable, ControlPointTable,
    FindingTable, FrameworkTable, OrganizationTable,
)
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


class RichTableInteractionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="issue44")
        Organization.objects.bulk_create(
            Organization(name=f"Alpha {index:02d}", description="matching")
            for index in range(25)
        )
        Organization.objects.create(name="Beta", description="not matching")

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

    def test_primary_label_links_to_organization_detail(self):
        organization = Organization.objects.order_by("pk").first()
        response = self.client.get(reverse("conformity:organization_index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("conformity:organization_detail", args=[organization.pk]),
        )

