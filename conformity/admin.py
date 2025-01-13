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
    list_select_related = ['applicable_frameworks']


class FrameworkResources(resources.ModelResource):
    class Meta:
        model = Framework


class FrameworkAdmin(ImportExportModelAdmin):
    ressource_class = Framework
    list_select_related = ['attachment']


class RequirementResources(resources.ModelResource):
    class Meta:
        model = Requirement


class RequirementAdmin(ImportExportModelAdmin):
    ressource_class = Requirement
    list_select_related = ['framework', 'parent']


class ConformityResources(resources.ModelResource):
    class Meta:
        model = Conformity


class ConformityAdmin(ImportExportModelAdmin):
    ressource_class = Conformity
    list_select_related = ['organization', 'requirement']


class ActionResources(resources.ModelResource):
    class Meta:
        model = Action


class ActionAdmin(ImportExportModelAdmin):
    ressource_class = Action
    list_select_related = ['organization', 'responsible']


class ControlResources(resources.ModelResource):
    class Meta:
        model = Control


class ControlAdmin(ImportExportModelAdmin):
    ressource_class = Control
    list_select_related = ['organization']


class ControlPointResources(resources.ModelResource):
    class Meta:
        model = ControlPoint


class ControlPointAdmin(ImportExportModelAdmin):
    ressource_class = ControlPoint
    list_select_related = ['control', 'control_user']


class FindingResources(resources.ModelResource):
    class Meta:
        model = Finding


class FindingAdmin(ImportExportModelAdmin):
    ressource_class = Finding
    list_select_related = ['audit']


class AuditResources(resources.ModelResource):
    class Meta:
        model = Audit


class AuditAdmin(ImportExportModelAdmin):
    ressource_class = Audit
    list_select_related = ['organization', 'auditor']


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
