"""
Customize Django Admin Site to manage my Models instances
"""

from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from .models import Organization, Framework, Requirement, Conformity, Audit, Finding, Action, Control, ControlPoint, Attachment


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


class ActionResources(resources.ModelResource):
    class Meta:
        model = Action


class ActionAdmin(ImportExportModelAdmin):
    ressource_class = Action


class ControlResources(resources.ModelResource):
    class Meta:
        model = Control


class ControlAdmin(ImportExportModelAdmin):
    ressource_class = Control


class ControlPointResources(resources.ModelResource):
    class Meta:
        model = ControlPoint


class ControlPointAdmin(ImportExportModelAdmin):
    ressource_class = ControlPoint


class FindingResources(resources.ModelResource):
    class Meta:
        model = Finding


class FindingAdmin(ImportExportModelAdmin):
    ressource_class = Finding


class AuditResources(resources.ModelResource):
    class Meta:
        model = Audit


class AuditAdmin(ImportExportModelAdmin):
    ressource_class = Audit


class AttachmentResources(resources.ModelResource):
    class Meta:
        model = Attachment


class AttachmentAdmin(ImportExportModelAdmin):
    ressource_class = Attachment


# Registration
admin.site.register(Action, ActionAdmin)
admin.site.register(Attachment, AttachmentAdmin)
admin.site.register(Audit, AuditAdmin)
admin.site.register(Conformity, ConformityAdmin)
admin.site.register(Control, ControlAdmin)
admin.site.register(ControlPoint, ControlPointAdmin)
admin.site.register(Finding, FindingAdmin)
admin.site.register(Framework, FrameworkAdmin)
admin.site.register(Organization, OrganizationAdmin)
admin.site.register(Requirement, RequirementAdmin)