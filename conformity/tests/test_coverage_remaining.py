from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django_filters.views import FilterView
from django.views.generic import DetailView, ListView
from django.utils import timezone

from conformity.forms import (
    ActionForm,
    ConformityForm,
    ControlPointForm,
    FindingForm,
)
from conformity.models import (
    Action,
    Audit,
    Conformity,
    Control,
    ControlPoint,
    Evidence,
    Finding,
    Framework,
    Indicator,
    IndicatorPoint,
    Organization,
    Requirement,
)
from conformity.resources import (
    ActionResource,
    AuditResource,
    ConformityResource,
    ControlResource,
    FindingResource,
    IndicatorResource,
)
from conformity.views import (
    ActionExportView,
    AttachmentDownloadView,
    AttachmentExportView,
    AuditExportView,
    AuditLogExportView,
    ConformityExportView,
    ConformityIndexExportView,
    ControlExportView,
    ControlPointExportView,
    FindingExportView,
    FrameworkExportView,
    IndicatorDetailView,
    IndicatorExportView,
    OrganizationExportView,
    FrameworkDetailView,
    ControlIndexView,
    AuditLogDetailView,
)


User = get_user_model()


class RemainingCoverageTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="coverage-user", password="secret")
        self.framework = Framework.objects.create(name="Coverage framework", publish_by="Test")
        self.organization = Organization.objects.create(name="Coverage organization")
        self.root = Requirement.objects.create(
            framework=self.framework, code="ROOT", title="Root"
        )
        self.leaf = Requirement.objects.create(
            framework=self.framework, code="LEAF", title="Leaf", parent=self.root
        )
        self.root_conformity = Conformity.objects.create(
            organization=self.organization, requirement=self.root
        )
        self.leaf_conformity = Conformity.objects.create(
            organization=self.organization, requirement=self.leaf, responsible=self.user
        )
        self.audit = Audit.objects.create(
            organization=self.organization, auditor="Auditor", name="Audit"
        )
        self.finding = Finding.objects.create(
            audit=self.audit, short_description="Finding", name="Finding"
        )
        self.action = Action.objects.create(
            title="Action", organization=self.organization, owner=self.user
        )
        self.control = Control.objects.create(
            title="Control",)
        self.control.conformity.add(self.root_conformity)
        self.control_point = ControlPoint.objects.create(
            control=self.control,
            period_start_date=date.today(),
            period_end_date=date.today(),
            status=ControlPoint.Status.TOBEEVALUATED,
        )
        self.indicator = Indicator.objects.create(
            name="Indicator", responsible=self.user,)

    def test_forms_cover_stateful_initialization(self):
        parent_form = ConformityForm(instance=self.root_conformity)
        self.assertNotIn("status", parent_form.fields)

        invalidated = Finding.objects.create(
            audit=self.audit,
            short_description="Invalidated",
            valid_from=timezone.now() - timedelta(days=1),
            valid_to=timezone.now() - timedelta(minutes=1),
        )
        invalidated_form = FindingForm(instance=invalidated)
        self.assertIn("valid_to", invalidated_form.fields)

        for status in Action.Status:
            form = ActionForm(instance=Action(status=status))
            self.assertTrue(form.fields["create_date"].disabled)
            self.assertTrue(form.fields["update_date"].disabled)

        evaluating = ControlPointForm(instance=self.control_point, user=self.user)
        self.assertNotIn("status", evaluating.fields)
        scheduled = ControlPoint.objects.create(
            control=self.control,
            period_start_date=date.today().replace(year=date.today().year + 1),
            period_end_date=date.today().replace(year=date.today().year + 1),
            status=ControlPoint.Status.SCHEDULED,
        )
        display = ControlPointForm(instance=scheduled, user=self.user)
        self.assertIn("attachments", display.fields)
        self.assertFalse(display.fields["attachments"].disabled)
        self.assertTrue(
            all(
                field.disabled
                for name, field in display.fields.items()
                if name != "attachments"
            )
        )

    def test_resources_export_all_values_and_empty_fallbacks(self):
        self.action.associated_findings.add(self.finding)
        self.action.associated_conformity.add(self.root_conformity)
        self.action.associated_controlPoints.add(self.control_point)
        self.finding.actions.add(self.action)

        conformity_resource = ConformityResource()
        self.assertEqual(conformity_resource.dehydrate_applicable(self.root_conformity), "yes")
        self.assertEqual(conformity_resource.dehydrate_applicable(SimpleNamespace(applicable=None)), "")
        self.assertEqual(conformity_resource.dehydrate_responsible(self.leaf_conformity), "coverage-user")
        self.assertEqual(conformity_resource.dehydrate_responsible(SimpleNamespace(responsible_id=None)), "")
        self.assertEqual(conformity_resource.dehydrate_status(self.root_conformity), None)
        self.root_conformity.status = 75
        self.assertEqual(conformity_resource.dehydrate_status(self.root_conformity), 0.75)
        self.assertEqual(conformity_resource.dehydrate_status(SimpleNamespace(status="bad")), None)
        self.assertIn("Action", conformity_resource.dehydrate_actions(self.root_conformity))
        self.assertEqual(
            conformity_resource.dehydrate_actions(
                Conformity.objects.get(pk=self.leaf_conformity.pk)
            ),
            "",
        )
        self.assertIn("Control", conformity_resource.dehydrate_controls(self.root_conformity))
        self.assertEqual(
            conformity_resource.dehydrate_controls(self.leaf_conformity), ""
        )

        self.assertEqual(
            ControlResource().dehydrate_frequency(self.control),
            self.control.get_frequency_display(),
        )
        self.assertIn("ROOT", ControlResource().dehydrate_conformity(self.control))
        self.assertEqual(
            ControlResource().dehydrate_conformity(
                Control.objects.create(title="Empty control")
            ),
            "",
        )
        finding_resource = FindingResource()
        self.assertIn("Action", finding_resource.dehydrate_actions(self.finding))
        self.assertEqual(
            finding_resource.dehydrate_actions(
                Finding.objects.create(audit=self.audit, short_description="Empty")
            ),
            "",
        )

        action_resource = ActionResource()
        self.assertEqual(action_resource.dehydrate_active(self.action), "Yes")
        self.assertEqual(
            action_resource.dehydrate_active(SimpleNamespace(active=None)), ""
        )
        self.assertEqual(
            action_resource.dehydrate_status(self.action),
            self.action.get_status_display(),
        )
        self.assertEqual(
            action_resource.dehydrate_owner(self.action), "coverage-user"
        )
        self.assertEqual(
            action_resource.dehydrate_owner(SimpleNamespace(owner_id=None)), ""
        )

        indicator_resource = IndicatorResource()
        self.assertEqual(indicator_resource.dehydrate_responsible(self.indicator), "coverage-user")
        self.assertEqual(
            indicator_resource.dehydrate_responsible(SimpleNamespace(responsible_id=None)), ""
        )
        self.assertEqual(
            indicator_resource.dehydrate_frequency(self.indicator),
            self.indicator.get_frequency_display(),
        )
        empty_indicator = Indicator.objects.create(
            name="Empty indicator", responsible=self.user
        )
        self.assertEqual(indicator_resource.dehydrate_conformity(empty_indicator), "")

        audit_resource = AuditResource()
        self.assertEqual(audit_resource.dehydrate_type(self.audit), self.audit.get_type_display())
        self.assertIn("Finding", audit_resource.dehydrate_finding(self.audit))
        empty_audit = Audit.objects.create(organization=self.organization, auditor="Other")
        self.assertEqual(audit_resource.dehydrate_finding(empty_audit), "None")

    def test_export_views_support_csv_and_xlsx(self):
        cases = (
            (AuditExportView, "/audits", "audits"),
            (FindingExportView, "/findings", "findings"),
            (ActionExportView, "/actions", "actions"),
            (ControlExportView, "/controls", "periodic-controls"),
            (IndicatorExportView, "/indicators", "indicators"),
            (AttachmentExportView, "/attachments", "attachments"),
            (AuditLogExportView, "/auditlog", "audit-log"),
            (FrameworkExportView, "/frameworks", "frameworks"),
            (OrganizationExportView, "/organizations", "organizations"),
            (ConformityIndexExportView, "/conformities", "conformities"),
            (ControlPointExportView, "/controlpoints", "controlpoints"),
        )
        for view, path, filename in cases:
            for fmt, extension in (("csv", "csv"), ("xlsx", "xlsx")):
                request = self.factory.get(path, {"format": fmt})
                response = view().get(request)
                self.assertEqual(response.status_code, 200)
                self.assertIn(f'filename="{filename}.{extension}"', response["Content-Disposition"])

        for fmt, extension in (("csv", "csv"), ("xlsx", "xlsx")):
            request = self.factory.get("/export", {"format": fmt})
            response = ConformityExportView().get(
                request, org=self.organization.pk, pol=self.framework.pk
            )
            self.assertIn(f'filename="conformity.{extension}"', response["Content-Disposition"])

    def test_selection_export_applies_current_filters(self):
        matched = Action.objects.create(
            title="Matched export action",
            organization=self.organization,
            owner=self.user,
        )
        excluded = Action.objects.create(
            title="Excluded export action",
            organization=self.organization,
            owner=self.user,
        )

        selection_request = self.factory.get(
            "/actions",
            {"format": "csv", "scope": "selection", "title": "Matched export"},
        )
        selection_response = ActionExportView().get(selection_request)
        selection_content = selection_response.content.decode()

        self.assertIn(matched.title, selection_content)
        self.assertNotIn(excluded.title, selection_content)

        all_request = self.factory.get(
            "/actions",
            {"format": "csv", "title": "Matched export"},
        )
        all_content = ActionExportView().get(all_request).content.decode()

        self.assertIn(matched.title, all_content)
        self.assertIn(excluded.title, all_content)

    def test_indicator_detail_context(self):
        point = IndicatorPoint.objects.create(
            indicator=self.indicator,
            period_start_date=date.today(),
            period_end_date=date.today(),
        )
        view = IndicatorDetailView()
        view.object = self.indicator
        view.request = self.factory.get("/")
        view.kwargs = {"pk": self.indicator.pk}
        context = view.get_context_data(object=self.indicator)
        self.assertIn(point, list(context["indicator_point_list"]))

    def test_attachment_download(self):
        attachment = self.control_point.attachment.create(
            file=SimpleUploadedFile("coverage.txt", b"coverage")
        )
        response = AttachmentDownloadView().get(attachment.pk)
        self.assertEqual(response.status_code, 200)
        self.assertIn("coverage", response["Content-Disposition"])

    def test_requirement_code_audit_reports_duplicates(self):
        Requirement.objects.create(
            framework=self.framework, code="", title="Missing code"
        )
        with self.assertRaises(CommandError):
            call_command("audit_requirement_codes")

    def test_remaining_model_helpers_and_indicator_statuses(self):
        self.assertEqual(Requirement.objects.get_by_natural_key(self.leaf.name), self.leaf)
        self.assertEqual(self.root_conformity.get_completeness(), 0)
        self.leaf_conformity.status = 100
        self.leaf_conformity.save(update_fields=["status"])
        self.assertEqual(self.root_conformity.get_completeness(), 100)
        self.assertEqual(self.action.get_associated(), [])
        self.assertEqual(Audit.objects.create(
            organization=self.organization, auditor="Auditor", end_date=date.today()
        ).__str__().split("/")[0], "Auditor")

        point = IndicatorPoint.objects.filter(indicator=self.indicator).first()
        point.indicator = self.indicator
        self.indicator.best, self.indicator.warning, self.indicator.critical, self.indicator.worst = 100, 80, 50, 0
        for value, result in ((90, Evidence.Result.POSITIVE),
                              (70, Evidence.Result.NEUTRAL),
                              (40, Evidence.Result.NEGATIVE),
                              (20, Evidence.Result.NEGATIVE),
                              (-1, Evidence.Result.NEUTRAL)):
            point.value = value
            point.result_update()
            self.assertEqual(point.result, result)
        self.indicator.best, self.indicator.warning, self.indicator.critical, self.indicator.worst = 0, 20, 50, 100
        for value, result in ((10, Evidence.Result.POSITIVE),
                              (30, Evidence.Result.NEUTRAL),
                              (75, Evidence.Result.NEGATIVE),
                              (150, Evidence.Result.NEUTRAL)):
            point.value = value
            point.result_update()
            self.assertEqual(point.result, result)
        self.indicator.best = self.indicator.worst = 50
        point.value = 50
        point.result_update()
        self.assertEqual(point.result, Evidence.Result.NEUTRAL)

    def test_view_context_helpers(self):
        framework_view = FrameworkDetailView()
        framework_view.object = self.framework
        framework_view.request = self.factory.get("/")
        framework_view.kwargs = {"pk": self.framework.pk}
        self.assertIn(self.root, list(
            framework_view.get_context_data(object=self.framework)["requirement_list"]
        ))

        control_view = ControlIndexView()
        control_view.request = self.factory.get("/", {"status": "TOBE"})
        control_view.request.user = self.user
        control_view.kwargs = {}
        context = control_view.get_context_data()
        self.assertNotIn("controlpoint_list", context)
        self.assertIn("filter", context)

        log_view = AuditLogDetailView()
        self.assertEqual(log_view.get_queryset().query.order_by, ("-timestamp", "-pk"))
