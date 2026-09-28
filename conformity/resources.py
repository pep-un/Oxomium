from auditlog.models import LogEntry
from django.utils.autoreload import logger
from import_export import fields, resources
from import_export.widgets import ManyToManyWidget, ForeignKeyWidget
from .models import Attachment, Conformity, Control, ControlPoint, Finding, Action, Framework, Indicator, Organization, Audit


class ConformityResource(resources.ModelResource):
    actions = fields.Field(widget=ManyToManyWidget(Action))
    controls = fields.Field(widget=ManyToManyWidget(Control))

    class Meta:
        model = Conformity
        fields = ("requirement__name", "requirement__title", "requirement__description", "applicable", "responsible",
                  "status", "status_last_update", "status_justification", "comment", "actions", "controls")

    def dehydrate_applicable(self, obj):
        val = getattr(obj, "applicable", None)
        if val is None:
            return ""
        return "yes" if bool(val) else "No"

    def dehydrate_responsible(self, obj):
        if not getattr(obj, "responsible_id", None):
            return ""
        u = obj.responsible
        full = getattr(u, "get_full_name", None)
        if callable(full):
            name = full()
            if name:
                return name
        return getattr(u, "username", str(u))

    def dehydrate_status_justification(self, obj):
        if hasattr(obj, "get_status_justification_display"):
            return obj.get_status_justification_display()
        return getattr(obj, "status_justification", "")

    def dehydrate_status(self, obj):
        val = getattr(obj, "status", None)
        if val is None:
            return None
        try:
            return round(float(val) / 100, 2)
        except (ValueError, TypeError):
            return None

    def dehydrate_actions(self, obj):
        actions = obj.actions.all()
        if not actions.exists():
            return ""
        return ", ".join(f"{action.title}" for action in actions)

    def dehydrate_controls(self, obj):
        controls = obj.get_control()
        if not controls.exists():
            return ""
        return ", ".join(f"{control.title}" for control in controls)


class ControlResource(resources.ModelResource):
    class Meta:
        model = Control
        fields = ("title", "level", "frequency", "organization__name", "description", "conformity")

    def dehydrate_frequency(self, obj):
        if hasattr(obj, "get_frequency_display"):
            return obj.get_frequency_display()
        return getattr(obj, "frequency", "")

    def dehydrate_conformity(self, obj):
        conformities = obj.conformity.all()
        if not conformities.exists():
            return ""
        return ", ".join(f"{conformity.requirement.name}" for conformity in conformities)


class FindingResource(resources.ModelResource):
    actions = fields.Field(widget=ManyToManyWidget(Action))

    class Meta:
        model = Finding
        fields = ("name", "audit__name", "archived", "short_description", "cvss", "cvss_descriptor", "actions" )

    def dehydrate_archived(self, obj):
        val = getattr(obj, "archived", None)
        if val is None:
            return ""
        return "Yes" if bool(val) else "No"

    def dehydrate_actions(self, obj):
        actions = obj.actions.all()
        if not actions.exists():
            return ""
        return ", ".join(f"{action.title}" for action in actions)


class ActionResource(resources.ModelResource):
    class Meta:
        model = Action
        fields = ("title", "description", "organization__name", "owner", "status", "status_comment", "active", "create_date", "update_date")

    def dehydrate_active(self, obj):
        val = getattr(obj, "active", None)
        if val is None:
            return ""
        return "Yes" if bool(val) else "No"

    def dehydrate_status(self, obj):
        if hasattr(obj, "get_status_display"):
            return obj.get_status_display()
        return getattr(obj, "status", "")

    def dehydrate_owner(self, obj):
        if not getattr(obj, "owner_id", None):
            return ""
        u = obj.owner
        full = getattr(u, "get_full_name", None)
        if callable(full):
            name = full()
            if name:
                return name
        return getattr(u, "owner", str(u))


class IndicatorResource(resources.ModelResource):
    class Meta:
        model = Indicator
        fields = ("name", "coal", "source", "formula", "worst", "critical", "warning", "best",
                  "responsible", "organization_name", "conformity", "frequency")


    def dehydrate_responsible(self, obj):
        if not getattr(obj, "responsible_id", None):
            return ""
        u = obj.responsible
        full = getattr(u, "get_full_name", None)
        if callable(full):
            name = full()
            if name:
                return name
        return getattr(u, "responsible", str(u))

    def dehydrate_frequency(self, obj):
        if hasattr(obj, "get_frequency_display"):
            return obj.get_frequency_display()
        return getattr(obj, "frequency", "")

    def dehydrate_conformity(self, obj):
        conformities = obj.conformity.all()
        if not conformities.exists():
            return ""
        return ", ".join(f"{conformity.requirement.name}" for conformity in conformities)


class AuditResource(resources.ModelResource):
    finding = fields.Field(widget=ForeignKeyWidget(Finding))

    class Meta:
        model = Audit
        fields = ("name", "auditor", "type", "start_date", "end_date", "report_date", "finding")

    def dehydrate_type(self, obj):
        if hasattr(obj, "get_type_display"):
            return obj.get_type_display()
        return getattr(obj, "type", "")

    def dehydrate_finding(self, obj):
        finding_list = Finding.objects.filter(audit=obj)
        if not finding_list.exists():
            return "None"
        return ", ".join(f"[{finding.severity}] {finding.name}" for finding in finding_list)


class AttachmentResource(resources.ModelResource):
    class Meta:
        model = Attachment
        fields = ("file", "comment", "mime_type", "sha256", "create_date")

    def dehydrate_file(self, obj):
        return obj.file.name if obj.file else ""


class FrameworkResource(resources.ModelResource):
    class Meta:
        model = Framework
        fields = ("name", "version", "language", "publish_by", "type")

    def dehydrate_language(self, obj):
        return obj.get_language_display()

    def dehydrate_type(self, obj):
        return obj.get_type_display()


class OrganizationResource(resources.ModelResource):
    class Meta:
        model = Organization
        fields = ("name", "administrative_id", "description")


class ControlPointResource(resources.ModelResource):
    class Meta:
        model = ControlPoint
        fields = (
            "control__title", "control__organization__name", "valid_from",
            "valid_to", "status", "evaluator__username", "evaluated_at", "comment",
        )

    def dehydrate_status(self, obj):
        return obj.get_status_display()


class AuditLogResource(resources.ModelResource):
    class Meta:
        model = LogEntry
        fields = (
            "timestamp", "actor__username", "actor_email", "remote_addr", "action",
            "content_type__app_label", "content_type__model", "object_repr", "object_pk",
        )

    def dehydrate_action(self, obj):
        return obj.get_action_display()
