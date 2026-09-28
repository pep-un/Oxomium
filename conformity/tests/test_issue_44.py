from django.contrib.auth import get_user_model
from django.test import TestCase
from django.template.loader import render_to_string
from constance.test import override_config
from django.urls import reverse

from conformity.models import (
    Action, Audit, Conformity, Control, ControlPoint, Evidence, Finding, Framework,
    Indicator, IndicatorPoint, Organization, Requirement,
)
from conformity.tables import (
    ActionTable, AttachmentTable, AuditLogTable, AuditTable, ConformityTable,
    ControlTable, ControlPointTable, FindingTable, FrameworkTable, OrganizationTable,
    PeriodicEvidenceTable,
)
from conformity.filterset import (
    AttachmentFilter, ConformityFilter, ControlPointFilter, FindingFilter,
    PeriodicEvidenceFilter,
)
from conformity.views import (
    ActionIndexView, AttachmentIndexView, AuditLogDetailView, AuditIndexView,
    ConformityIndexView, ControlIndexView, ControlPointIndexView, FindingIndexView,
    FrameworkIndexView, OrganizationIndexView,
)


class RichTableConfigurationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="issue44-config")
        self.client.force_login(self.user)

    def test_all_tabular_index_views_have_explicit_table_classes(self):
        expected = {
            ActionIndexView: ActionTable,
            AttachmentIndexView: AttachmentTable,
            AuditLogDetailView: AuditLogTable,
            AuditIndexView: AuditTable,
            ConformityIndexView: ConformityTable,
            ControlIndexView: PeriodicEvidenceTable,
            ControlPointIndexView: ControlPointTable,
            FindingIndexView: FindingTable,
            FrameworkIndexView: FrameworkTable,
            OrganizationIndexView: OrganizationTable,
        }
        for view, table in expected.items():
            with self.subTest(view=view.__name__):
                self.assertIs(view.table_class, table)

    def test_secondary_navigation_filters_are_available(self):
        self.assertIn("audit", getattr(FindingFilter, "base_filters"))
        self.assertIn("action", getattr(FindingFilter, "base_filters"))
        self.assertIn("action", getattr(ConformityFilter, "base_filters"))
        self.assertIn("action", getattr(ControlPointFilter, "base_filters"))

    def test_attachment_filters_cover_metadata_relations_and_dates(self):
        expected = {
            "file", "mime_type", "sha256", "organization", "framework", "audit",
            "control_point", "indicator_point", "create_date_after", "create_date_before",
        }
        self.assertTrue(expected.issubset(getattr(AttachmentFilter, "base_filters")))

    def test_primary_columns_share_name_and_width(self):
        table_classes = (
            ActionTable,
            AuditTable,
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

    def test_conformity_table_uses_balanced_column_widths(self):
        table = ConformityTable([])
        self.assertEqual(
            table.columns["conformity"].attrs["th"]["style"],
            "width: 35%;",
        )
        self.assertEqual(
            table.columns["requirements"].attrs["th"]["style"],
            "width: 10%;",
        )
        self.assertEqual(
            table.columns["evidence_status"].attrs["th"]["style"],
            "width: 55%;",
        )

    def test_conformity_table_uses_stacked_evidence_status_column(self):
        table = ConformityTable([])
        self.assertIn("evidence_status", table.columns)
        self.assertNotIn("completeness", table.columns)
        self.assertNotIn("status", table.columns)
        self.assertEqual(
            table.columns["evidence_status"].verbose_name,
            "Status",
        )

    def test_conformity_status_bar_uses_secondary_stripes_without_legend(self):
        table = ConformityTable([])
        template = table.columns["evidence_status"].column.template_code
        self.assertIn("bg-secondary progress-bar-striped", template)
        self.assertIn("repeating-linear-gradient", template)
        self.assertNotIn("text-body-secondary mt-1 text-nowrap", template)

    def test_conformity_evidence_distribution_counts_leaf_states(self):
        organization = Organization.objects.create(name="Evidence summary org")
        framework = Framework.objects.create(name="Evidence summary framework")
        root_req = Requirement.objects.create(
            framework=framework, code="SUM", title="Summary root"
        )
        root = Conformity.objects.create(
            organization=organization,
            requirement=root_req,
        )
        states = (
            Conformity.EvidenceState.COMPLIANT,
            Conformity.EvidenceState.PARTIAL,
            Conformity.EvidenceState.NON_COMPLIANT,
            Conformity.EvidenceState.INCONCLUSIVE,
        )
        for index, state in enumerate(states, start=1):
            requirement = Requirement.objects.create(
                framework=framework,
                parent=root_req,
                code=f"SUM{index}",
                title=f"Leaf {index}",
            )
            Conformity.objects.create(
                organization=organization,
                requirement=requirement,
                evidence_state=state,
            )

        distribution = root.get_evidence_state_distribution()
        self.assertEqual(distribution["total"], 4)
        self.assertEqual(distribution["compliant_pct"], 25)
        self.assertEqual(distribution["partial_pct"], 25)
        self.assertEqual(distribution["non_compliant_pct"], 25)
        self.assertEqual(distribution["inconclusive_pct"], 25)

    def test_periodic_controls_table_has_operational_columns_only(self):
        table = PeriodicEvidenceTable([])
        self.assertEqual(
            list(table.columns.names()),
            [
                "name",
                "organization",
                "type",
                "level",
                "frequency",
                "last_result",
                "requirements",
            ],
        )
        self.assertNotIn("actions", table.columns)

    def test_periodic_controls_filter_uses_standard_status_field(self):
        filters = getattr(PeriodicEvidenceFilter, "base_filters")
        self.assertIn("name", filters)
        self.assertIn("status", filters)
        self.assertIn("organization", filters)
        self.assertIn("source_type", filters)
        self.assertIn("requirement", filters)
        self.assertIn("reference", filters)
        self.assertEqual(filters["status"].label, "Last result")
        self.assertEqual(filters["requirement"].label, "Associated requirement")
        self.assertEqual(filters["reference"].label, "Associated Framework")

    def test_periodic_controls_show_export_and_result_count(self):
        organization = Organization.objects.create(name="Periodic toolbar org")
        control = Control.objects.create(
            title="Toolbar control",
            organization=organization,
            frequency=Control.Frequency.YEARLY,
        )
        point = next(
            item for item in control.get_controlpoint()
            if item.is_current_period()
        )

        response = self.client.get(
            reverse("conformity:control_index"),
            {"status": "TOBE"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("conformity:control_export"))
        self.assertContains(response, "Export CSV (All)")
        self.assertContains(response, "Export XLSX (All)")
        self.assertEqual(response.context["result_total_count"], 1)
        self.assertEqual(response.context["result_visible_count"], 1)
        self.assertEqual(
            [row.record.pk for row in response.context["table"].page.object_list],
            [point.pk],
        )

    def test_periodic_controls_selection_export_uses_current_filters(self):
        organization = Organization.objects.create(name="Periodic export org")
        pending = Control.objects.create(
            title="Pending export control",
            organization=organization,
            frequency=Control.Frequency.YEARLY,
        )
        completed = Control.objects.create(
            title="Completed export control",
            organization=organization,
            frequency=Control.Frequency.YEARLY,
        )
        completed_point = next(
            item for item in completed.get_controlpoint()
            if item.is_current_period()
        )
        completed_point.status = ControlPoint.Status.COMPLIANT
        completed_point.save(update_fields=["status"])

        response = self.client.get(
            reverse("conformity:control_export"),
            {"format": "csv", "scope": "selection", "status": "TOBE"},
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Pending export control", content)
        self.assertNotIn("Completed export control", content)

    def test_periodic_controls_filters_name_requirement_and_reference(self):
        organization = Organization.objects.create(name="Filter org")
        framework = Framework.objects.create(name="Filter reference")
        root = Requirement.objects.create(
            framework=framework,
            code="FR",
            title="Filter root",
        )
        leaf = Requirement.objects.create(
            framework=framework,
            parent=root,
            code="1",
            title="Target requirement",
        )
        conformity = Conformity.objects.create(
            organization=organization,
            requirement=leaf,
        )
        control = Control.objects.create(
            title="Quarterly access review",
            organization=organization,
            frequency=Control.Frequency.YEARLY,
        )
        point = next(
            item for item in control.get_controlpoint()
            if item.is_current_period()
        )
        point.conformities.add(conformity)

        base = Evidence.objects.filter(pk=point.pk)

        by_name = PeriodicEvidenceFilter(
            {"name": "access"},
            queryset=base,
        )
        self.assertEqual(list(by_name.qs), [point.evidence_ptr])

        by_requirement = PeriodicEvidenceFilter(
            {"requirement": leaf.pk},
            queryset=base,
        )
        self.assertEqual(list(by_requirement.qs), [point.evidence_ptr])

        by_reference = PeriodicEvidenceFilter(
            {"reference": framework.pk},
            queryset=base,
        )
        self.assertEqual(list(by_reference.qs), [point.evidence_ptr])

    def test_control_table_exposes_organization_and_last_result(self):
        table = ControlTable([])
        self.assertIn("organization", table.columns)
        self.assertIn("last_result", table.columns)
        self.assertEqual(table.columns["organization"].verbose_name, "Organization")
        self.assertEqual(table.columns["last_result"].verbose_name, "Last result")

    def test_control_point_name_uses_control_title(self):
        self.assertEqual(
            str(getattr(ControlPointTable, "base_columns")["name"].accessor),
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


class ControlPointStatusComponentTests(TestCase):
    def test_non_compliant_uses_danger_filled_hexagon(self):
        control_point = ControlPoint(status=ControlPoint.Status.NONCOMPLIANT)

        html = render_to_string(
            "conformity/includes/controlpoint_status.html",
            {"controlpoint": control_point},
        )

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
        self.assertRegex(
            ascending.content.decode(),
            r'<th class="[^"]*\basc\b[^"]*\borderable\b[^"]*"',
        )

        descending = self.client.get(url, {"sort": "-name"})
        self.assertEqual(descending.status_code, 200)
        self.assertRegex(
            descending.content.decode(),
            r'<th class="[^"]*\bdesc\b[^"]*\borderable\b[^"]*"',
        )

    def test_all_rich_table_indexes_render(self):
        view_names = (
            "conformity:action_index",
            "conformity:attachment_index",
            "conformity:auditlog_index",
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
                params = {"status": "TOBE"} if view_name == "conformity:control_index" else {}
                response = self.client.get(reverse(view_name), params)
                self.assertEqual(response.status_code, 200)

    def test_missing_list_actions_are_now_exposed(self):
        export_routes = {
            "conformity:attachment_index": "conformity:attachment_export",
            "conformity:auditlog_index": "conformity:auditlog_export",
            "conformity:framework_index": "conformity:framework_export",
            "conformity:organization_index": "conformity:organization_export",
            "conformity:conformity_index": "conformity:conformity_index_export",
            "conformity:controlpoint_index": "conformity:controlpoint_export",
        }
        for view_name, export_name in export_routes.items():
            with self.subTest(view_name=view_name):
                response = self.client.get(reverse(view_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, reverse(export_name))

        finding_response = self.client.get(reverse("conformity:finding_index"))
        self.assertEqual(finding_response.status_code, 200)
        self.assertContains(finding_response, reverse("conformity:finding_create"))

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


    def test_control_index_shows_current_point_evaluate_call_to_action(self):
        organization = Organization.objects.create(name="Control result org")
        control = Control.objects.create(
            title="Control awaiting evaluation",
            organization=organization,
            frequency=Control.Frequency.YEARLY,
        )
        current_point = next(
            point for point in control.get_controlpoint()
            if point.is_current_period()
        )

        response = self.client.get(
            reverse("conformity:control_index"),
            {"status": "TOBE"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("conformity:organization_detail", args=[organization.pk]),
        )
        self.assertContains(
            response,
            reverse("conformity:controlpoint_form", args=[current_point.pk]),
        )
        self.assertContains(response, "Evaluate")

    def test_control_index_shows_current_control_point_result_when_completed(self):
        organization = Organization.objects.create(name="Completed control org")
        control = Control.objects.create(
            title="Completed current control",
            organization=organization,
            frequency=Control.Frequency.YEARLY,
        )
        current_point = next(
            point for point in control.get_controlpoint()
            if point.is_current_period()
        )
        current_point.status = ControlPoint.Status.COMPLIANT
        current_point.save(update_fields=["status"])

        response = self.client.get(
            reverse("conformity:control_index"),
            {"status": ""},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "bi-hexagon-fill text-success")
        self.assertContains(response, "Compliant")

    def test_periodic_controls_default_to_items_to_evaluate(self):
        organization = Organization.objects.create(name="Periodic default org")
        pending_control = Control.objects.create(
            title="Pending control",
            organization=organization,
            frequency=Control.Frequency.YEARLY,
        )
        pending_point = next(
            point for point in pending_control.get_controlpoint()
            if point.is_current_period()
        )

        completed_control = Control.objects.create(
            title="Completed hidden control",
            organization=organization,
            frequency=Control.Frequency.YEARLY,
        )
        completed_point = next(
            point for point in completed_control.get_controlpoint()
            if point.is_current_period()
        )
        completed_point.status = ControlPoint.Status.COMPLIANT
        completed_point.save(update_fields=["status"])

        response = self.client.get(reverse("conformity:control_index"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f'{reverse("conformity:control_index")}?status=TOBE',
        )

        response = self.client.get(response.url)
        self.assertEqual(response.status_code, 200)
        records = [row.record.pk for row in response.context["table"].page.object_list]
        self.assertIn(pending_point.pk, records)
        self.assertNotIn(completed_point.pk, records)
        self.assertEqual(response.context["filter"].form["status"].value(), "TOBE")
        self.assertContains(response, 'btn btn-primary dropdown-toggle')
        self.assertNotContains(response, reverse("conformity:control_create"))
        self.assertNotContains(response, reverse("conformity:indicator_create"))

    def test_periodic_controls_status_filter_can_be_cleared(self):
        organization = Organization.objects.create(name="Periodic all org")
        control = Control.objects.create(
            title="Completed visible control",
            organization=organization,
            frequency=Control.Frequency.YEARLY,
        )
        point = next(
            item for item in control.get_controlpoint()
            if item.is_current_period()
        )
        point.status = ControlPoint.Status.COMPLIANT
        point.save(update_fields=["status"])

        response = self.client.get(
            reverse("conformity:control_index"),
            {"status": ""},
        )

        self.assertEqual(response.status_code, 200)
        records = [row.record.pk for row in response.context["table"].page.object_list]
        self.assertIn(point.pk, records)
        self.assertNotContains(response, 'btn btn-primary dropdown-toggle')

    def test_periodic_control_name_links_to_result_editor(self):
        organization = Organization.objects.create(name="Periodic title link org")
        control = Control.objects.create(
            title="Linked periodic control",
            organization=organization,
            frequency=Control.Frequency.YEARLY,
        )
        point = next(
            item for item in control.get_controlpoint()
            if item.is_current_period()
        )

        response = self.client.get(
            reverse("conformity:control_index"),
            {"status": "TOBE"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'href="{reverse("conformity:controlpoint_form", args=[point.pk])}"',
            count=2,
        )
        self.assertContains(response, "Linked periodic control")

    def test_periodic_controls_include_indicator_evidence(self):
        organization = Organization.objects.create(name="Indicator queue org")
        indicator = Indicator.objects.create(
            name="MFA coverage",
            responsible=self.user,
            organization=organization,
            frequency=Indicator.Frequency.YEARLY,
            worst=0,
            critical=20,
            warning=80,
            best=100,
        )
        point = indicator.get_current_point()

        self.assertIsNotNone(point)
        self.assertEqual(point.status, IndicatorPoint.Status.TOBEEVALUATED)

        response = self.client.get(
            reverse("conformity:control_index"),
            {"status": "TOBE"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MFA coverage")
        self.assertContains(response, "Indicator")
        self.assertContains(
            response,
            reverse("conformity:indicatorpoint_form", args=[point.pk]),
        )
        self.assertContains(response, "Enter value")

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

