"""
Customize Django Admin Site to manage my Models instances
"""

from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from .models import Organization, Policy, Measure, Conformity, Audit, Finding, Action, Control, ControlPoint


class OrganizationResources(resources.ModelResource):
    class Meta:
        model = Organization


class OrganizationAdmin(ImportExportModelAdmin):
    ressource_class = Organization


class PolicyResources(resources.ModelResource):
    class Meta:
        model = Policy


class PolicyAdmin(ImportExportModelAdmin):
    ressource_class = Policy


class MeasureResources(resources.ModelResource):
    class Meta:
        model = Measure


class MeasureAdmin(ImportExportModelAdmin):
    ressource_class = Measure


class ConformityResources(resources.ModelResource):
    class Meta:
        model = Conformity


class ConformityAdmin(ImportExportModelAdmin):
    ressource_class = Conformity


# Action
class ActionResources(resources.ModelResource):
    class Meta:
        model = Action


class ActionAdmin(ImportExportModelAdmin):
    ressource_class = Action


# Registration
admin.site.register(Policy, PolicyAdmin)
admin.site.register(Measure, MeasureAdmin)
admin.site.register(Conformity, ConformityAdmin)
admin.site.register(Action, ActionAdmin)
admin.site.register(Audit)
admin.site.register(Finding)
admin.site.register(Organization, OrganizationAdmin)
admin.site.register(Control)
admin.site.register(ControlPoint)
