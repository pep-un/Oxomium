"""
Customize Django Admin Site to manage my Models instances
"""

from django.contrib import admin
from django import forms
from django.db import transaction
from auditlog import get_logentry_model
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from .services.conformities import set_frameworks
from .models import Organization, Framework, Requirement, Conformity, Audit, Finding, Action, Control, ControlPoint, \
    Attachment, Indicator, IndicatorPoint


class OrganizationResources(resources.ModelResource):
    class Meta:
        model = Organization


def _log_framework_changes(organization, previous_ids, selected, actor):
    """Record explicit framework reconciliation in django-auditlog."""
    selected_ids = {framework.pk for framework in selected}
    LogEntry = get_logentry_model()
    LogEntry.objects.log_m2m_changes(
        Framework.objects.filter(pk__in=previous_ids - selected_ids),
        organization,
        'delete',
        'applicable_frameworks',
        actor=actor,
    )
    LogEntry.objects.log_m2m_changes(
        Framework.objects.filter(pk__in=selected_ids - previous_ids),
        organization,
        'add',
        'applicable_frameworks',
        actor=actor,
    )


class OrganizationAdminForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = '__all__'


class OrganizationAdmin(ImportExportModelAdmin):
    form = OrganizationAdminForm
    ressource_class = Organization
    list_select_related = ['applicable_frameworks']

    def save_related(self, request, form, formsets, change):
        """Save regular relations normally and reconcile frameworks explicitly."""
        selected = form.cleaned_data.pop('applicable_frameworks', None)
        previous_ids = (
            set(form.instance.applicable_frameworks.values_list('pk', flat=True))
            if selected is not None else set()
        )
        try:
            with transaction.atomic():
                super().save_related(request, form, formsets, change)
                if selected is not None:
                    set_frameworks(form.instance, selected)
                    _log_framework_changes(form.instance, previous_ids, selected, request.user)
        finally:
            if selected is not None:
                form.cleaned_data['applicable_frameworks'] = selected


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

class IndicatorResources(resources.ModelResource):
    class Meta:
        model = Indicator

class IndicatorAdmin(ImportExportModelAdmin):
    ressource_class = Indicator

class IndicatorPointResources(resources.ModelResource):
    class Meta:
        model = IndicatorPoint

class IndicatorPointAdmin(ImportExportModelAdmin):
    ressource_class = IndicatorPoint


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
admin.site.register(Indicator, IndicatorAdmin)
admin.site.register(IndicatorPoint, IndicatorPointAdmin)
