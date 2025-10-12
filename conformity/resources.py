from import_export import fields, resources
from import_export.widgets import ManyToManyWidget
from .models import Conformity, Control, Finding, Action, Indicator


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
        controls = obj.controls.all()
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