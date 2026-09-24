from datetime import date
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
    AuditExportView,
    ConformityExportView,
    ControlExportView,
    FindingExportView,
    IndicatorDetailView,
    IndicatorExportView,
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
            title="Control", organization=self.organization
        )
        self.control.conformity.add(self.root_conformity)
        self.control_point = ControlPoint.objects.create(
            control=self.control,
            period_start_date=date.today(),
            period_end_date=date.today(),
            status=ControlPoint.Status.TOBEEVALUATED,
        )
        self.indicator = Indicator.objects.create(
            name="Indicator", responsible=self.user, organization=self.organization
        )

    def test_forms_cover_stateful_initialization(self):
        parent_form = ConformityForm(instance=self.root_conformity)
        self.assertTrue(parent_form.fields["status"].disabled)

        archived = Finding.objects.create(
            audit=self.audit, short_description="Archived", archived=True
        )
        archived_form = FindingForm(instance=archived)
        self.assertTrue(all(field.disabled for field in archived_form.fields.values()))

        for status in Action.Status:
            form = ActionForm(instance=Action(status=status))
            self.assertTrue(form.fields["create_date"].disabled)
            self.assertTrue(form.fields["update_date"].disabled)

        evaluating = ControlPointForm(instance=self.control_point, user=self.user)
        self.assertIn(
            (ControlPoint.Status.COMPLIANT, ControlPoint.Status.COMPLIANT.label),
            list(evaluating.fields["status"].widget.choices),
        )
        scheduled = ControlPoint.objects.create(
            control=self.control,
            period_start_date=date.today().replace(year=date.today().year + 1),
            period_end_date=date.today().replace(year=date.today().year + 1),
            status=ControlPoint.Status.SCHEDULED,
        )
        display = ControlPointForm(instance=scheduled, user=self.user)
        self.assertNotIn("attachments", display.fields)
        self.assertTrue(all(field.disabled for field in display.fields.values()))

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
        self.assertEqual(finding_resource.dehydrate_archived(self.finding), "No")
        self.assertEqual(
            finding_resource.dehydrate_archived(SimpleNamespace(archived=None)), ""
        )
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
            (ControlExportView, "/controls", "controls"),
            (IndicatorExportView, "/indicators", "indicators"),
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
        for value, status in ((90, IndicatorPoint.Status.COMPLIANT),
                              (70, IndicatorPoint.Status.WARNING),
                              (40, IndicatorPoint.Status.CRITICAL),
                              (20, IndicatorPoint.Status.CRITICAL),
                              (-1, IndicatorPoint.Status.MISSED)):
            point.value = value
            point.status_update()
            self.assertEqual(point.status, status)
        self.indicator.best, self.indicator.warning, self.indicator.critical, self.indicator.worst = 0, 20, 50, 100
        for value, status in ((10, IndicatorPoint.Status.COMPLIANT),
                              (30, IndicatorPoint.Status.WARNING),
                              (75, IndicatorPoint.Status.CRITICAL),
                              (150, IndicatorPoint.Status.MISSED)):
            point.value = value
            point.status_update()
            self.assertEqual(point.status, status)
        self.indicator.best = self.indicator.worst = 50
        point.value = 50
        point.status_update()
        self.assertEqual(point.status, IndicatorPoint.Status.MISSED)

    def test_view_context_helpers(self):
        framework_view = FrameworkDetailView()
        framework_view.object = self.framework
        framework_view.request = self.factory.get("/")
        framework_view.kwargs = {"pk": self.framework.pk}
        self.assertIn(self.root, list(
            framework_view.get_context_data(object=self.framework)["requirement_list"]
        ))

        control_view = ControlIndexView()
        control_view.request = self.factory.get("/")
        control_view.request.user = self.user
        control_view.object_list = Control.objects.all()
        control_view.kwargs = {}
        with patch.object(FilterView, "get_context_data", return_value={}):
            context = control_view.get_context_data()
        self.assertIn("controlpoint_list", context)

        log_view = AuditLogDetailView()
        self.assertEqual(log_view.get_queryset().query.order_by, ("-timestamp",))
