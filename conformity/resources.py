from import_export import resources
from .models import Conformity

class ConformityResource(resources.ModelResource):
    class Meta:
        model = Conformity
        fields = ("requirement__name", "requirement__title", "requirement__description", "applicable", "responsible", "status", "status_last_update", "status_justification", "comment")

    def dehydrate_requirement__name(self, obj):
        return getattr(obj.requirement, "name", "") if obj.requirement_id else ""

    def dehydrate_requirement__title(self, obj):
        return getattr(obj.requirement, "title", "") if obj.requirement_id else ""

    def dehydrate_requirement__description(self, obj):
        return getattr(obj.requirement, "description", "") if obj.requirement_id else ""

    def dehydrate_applicable(self, obj):
        val = getattr(obj, "applicable", None)
        if val is None:
            return ""
        return "Oui" if bool(val) else "Non"

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
