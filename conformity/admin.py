"""
Customize Django Admin Site to manage my Models instances
"""

from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from .models import Organization, Framework, Requirement, Conformity, Audit, Finding, Action, Control, ControlPoint


class OrganizationResources(resources.ModelResource):
    class Meta:
        model = Organization


class OrganizationAdmin(ImportExportModelAdmin):
    ressource_class = Organization


class FrameworkResources(resources.ModelResource):
    class Meta:
        model = Framework


class FrameworkAdmin(ImportExportModelAdmin):
    ressource_class = Framework


class RequirementResources(resources.ModelResource):
    class Meta:
        model = Requirement


class RequirementAdmin(ImportExportModelAdmin):
    ressource_class = Requirement


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
admin.site.register(Framework, FrameworkAdmin)
admin.site.register(Requirement, RequirementAdmin)
admin.site.register(Conformity, ConformityAdmin)
admin.site.register(Action, ActionAdmin)
admin.site.register(Audit)
admin.site.register(Finding)
admin.site.register(Organization, OrganizationAdmin)
admin.site.register(Control)
admin.site.register(ControlPoint)
