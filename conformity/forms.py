"""
Forms for front-end editing of Models instance
"""

from django.forms import ModelForm, FileField, ClearableFileInput, BooleanField, ModelChoiceField
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .models import Conformity, Organization, Audit, Finding, Action, Control, ControlPoint, Indicator, IndicatorPoint


class ConformityForm(ModelForm):
    propagate_to_children = BooleanField(
        required=False, label='Apply applicability and comment to child requirements'
    )

    class Meta:
        model = Conformity
        fields = ['applicable', 'responsible', 'status', 'comment']

    def __init__(self, *args, **kwargs):
        super(ConformityForm, self).__init__(*args, **kwargs)
        if self.instance.get_descendants().exists():
            self.fields['status'].disabled = True


class OrganizationForm(ModelForm):
    attachments = FileField(required=False, widget=ClearableFileInput())
    class Meta:
        model = Organization
        fields = ['name', 'administrative_id', 'description', 'applicable_frameworks']


class AuditForm(ModelForm):
    attachments = FileField(required=False, widget=ClearableFileInput())
    class Meta:
        model = Audit
        fields = ['name', 'organization', 'description', 'conclusion', 'auditor', 'audited_frameworks', 'start_date',
                  'end_date', 'report_date', 'type', 'attachments']


class FindingForm(ModelForm):
    class Meta:
        model = Finding
        fields = ['name', 'audit', 'severity', 'short_description', 'description', 'observation', 'recommendation', 'reference', 'cvss', 'cvss_descriptor', 'archived']
    def __init__(self, *args, **kwargs):
        super(FindingForm, self).__init__(*args, **kwargs)

        # Only lock the audit when creating a finding from an audit page.
        # Existing findings carry their audit in initial too and must stay editable.
        if self.instance.pk is None and self.initial.get('audit'):
            audit = self.initial['audit']
            self.fields['audit'].disabled = True
            if isinstance(audit, Audit):
                self.initial['organization'] = audit.organization
            self.fields['organization'] = ModelChoiceField(
                queryset=Organization.objects.all(), required=False, disabled=True
            )
            self.order_fields([
                'name', 'audit', 'organization', 'severity', 'short_description',
                'description', 'observation', 'recommendation', 'reference', 'cvss',
                'cvss_descriptor', 'archived',
            ])
        if self.get_initial_for_field(self.fields['archived'], 'archived') :
            for key, value in self.fields.items():
                self.fields[key].disabled = True


class ActionForm(ModelForm):
    class Meta:
        model = Action
        fields = [
            'title', 'create_date', 'update_date', 'owner', 'status', 'status_comment',
            'reference', 'active', 'description', 'organization', 'associated_conformity',
            'associated_findings', 'associated_controlPoints', 'plan_start_date',
            'plan_end_date', 'plan_comment', 'implement_start_date', 'implement_end_date',
            'implement_status', 'implement_comment', 'control_date', 'control_comment',
            'control_user',
        ]

    def __init__(self, *args, **kwargs):
        super(ActionForm, self).__init__(*args, **kwargs)
        self.fields['create_date'].disabled = True
        self.fields['update_date'].disabled = True

        if self.instance.pk is None and self.initial.get('associated_findings'):
            self.fields['associated_findings'].disabled = True
        if self.instance.pk is None and self.initial.get('associated_conformity'):
            self.fields['associated_conformity'].disabled = True
        if self.instance.pk is None and 'organization' in self.initial:
            self.fields['organization'].disabled = True

        generic_fields = ['title', 'owner', 'status', 'status_comment', 'reference']
        analyse_fields = ['organization', 'associated_conformity', 'associated_findings', 'associated_controlPoints', 'description']
        plan_fields = ['plan_start_date', 'plan_end_date', 'plan_comment']
        implement_fields = ['implement_start_date', 'implement_end_date', 'implement_status', 'implement_comment']
        control_fields = ['control_date', 'control_comment', 'control_user']
        fields_by_status = {
            Action.Status.ANALYSING.value: generic_fields + analyse_fields,
            Action.Status.PLANNING.value: generic_fields + plan_fields,
            Action.Status.IMPLEMENTING.value: generic_fields + implement_fields,
            Action.Status.CONTROLLING.value: generic_fields + control_fields,
            Action.Status.FROZEN.value: generic_fields,
            Action.Status.CANCELED.value: generic_fields,
            Action.Status.ENDED.value: generic_fields,
        }

        for key, value in self.fields.items():
            if key not in fields_by_status[self.get_initial_for_field(self.fields['status'], 'status')]:
                self.fields[key].disabled = True


class ControlForm(ModelForm):
    class Meta:
        model = Control
        fields = ['title', 'description', 'organization', 'conformity', 'control', 'frequency', 'level']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk is None and self.initial.get('conformity'):
            self.fields['conformity'].disabled = True


class ControlPointForm(ModelForm):
    attachments = FileField(required=False, widget=ClearableFileInput())
    class Meta:
        model = ControlPoint
        fields = ['control_date', 'control_user', 'status', 'comment', 'attachments']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super(ControlPointForm, self).__init__(*args, **kwargs)

        # Set some value for all situation
        self.fields['control_date'].disabled = True
        self.fields['control_user'].disabled = True

        # Set some value if the ControlPoint has to be evaluated
        if self.get_initial_for_field(self.fields['status'], 'status') == ControlPoint.Status.TOBEEVALUATED.value:
            self.initial['control_date'] = timezone.now()
            self.initial['control_user'] = self.user
            self.fields['status'].widget.choices = [
                (ControlPoint.Status.COMPLIANT, ControlPoint.Status.COMPLIANT.label),
                (ControlPoint.Status.NONCOMPLIANT, ControlPoint.Status.NONCOMPLIANT.label),
            ]
        # Switch to display mode if ControlPoint is not to be evaluated
        else:
            del self.fields['attachments']
            for field in self.fields:
                self.fields[field].disabled = True


class IndicatorForm(ModelForm):
    class Meta:
        model = Indicator
        fields = [
            'name', 'goal', 'source', 'formula', 'worst', 'best', 'warning', 'critical',
            'responsible', 'organization', 'conformity', 'frequency',
        ]


class IndicatorPointForm(ModelForm):
    class Meta:
        model = IndicatorPoint
        fields = ['value', 'comment', 'attachment']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.indicator_id is not None:
            lower, upper = self.instance.indicator.value_bounds
            self.fields['value'].widget.attrs.update(min=lower, max=upper, step=1)
            self.fields['value'].help_text = _(
                'Enter an integer between %(lower)s and %(upper)s (inclusive).'
            ) % {'lower': lower, 'upper': upper}
