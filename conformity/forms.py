"""
Forms for front-end editing of Models instance
"""

from django.forms import ModelForm, FileField, ClearableFileInput
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import request
from django.utils import timezone

from .models import Conformity, Organization, Audit, Finding, Action, Control, ControlPoint, Indicator, IndicatorPoint


class ConformityForm(ModelForm):
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
        fields = '__all__'
        exclude = ['attachment']


class FindingForm(ModelForm):
    class Meta:
        model = Finding
        fields = ['name', 'audit', 'severity', 'short_description', 'description', 'observation', 'recommendation', 'reference', 'cvss', 'cvss_descriptor', 'archived']
        # TODO add a preselection and a disable selector for 'audit' field when the form is open from an audit.

    def __init__(self, *args, **kwargs):
        super(FindingForm, self).__init__(*args, **kwargs)

        if self.get_initial_for_field(self.fields['archived'], 'archived') :
            for key, value in self.fields.items():
                self.fields[key].disabled = True


class ActionForm(ModelForm):
    class Meta:
        model = Action
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(ActionForm, self).__init__(*args, **kwargs)
        self.fields['create_date'].disabled = True
        self.fields['update_date'].disabled = True

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
        fields = '__all__'


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
        fields = '__all__'


class IndicatorPointForm(ModelForm):
    class Meta:
        model = IndicatorPoint
        fields = ['value', 'comment', 'attachment']