"""
Forms for front-end editing of Models instance
"""

from django.forms import ModelForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import request
from django.utils import timezone

from .models import Conformity, Organization, Audit, Finding, Action, Control, ControlPoint


class ConformityForm(LoginRequiredMixin, ModelForm):
    class Meta:
        model = Conformity
        fields = ['applicable', 'responsible', 'status', 'comment']

    def __init__(self, *args, **kwargs):
        super(ConformityForm, self).__init__(*args, **kwargs)
        if self.instance.get_children().exists():
            self.fields['status'].disabled = True


class OrganizationForm(LoginRequiredMixin, ModelForm):
    class Meta:
        model = Organization
        fields = '__all__'


class AuditForm(LoginRequiredMixin, ModelForm):
    class Meta:
        model = Audit
        fields = '__all__'


class FindingForm(LoginRequiredMixin, ModelForm):
    class Meta:
        model = Finding
        fields = ['audit', 'severity', 'short_description', 'description', 'reference']
        # TODO add a preselection and a disable selector for 'audit' field when the form is open from an audit.


class ActionForm(LoginRequiredMixin, ModelForm):
    class Meta:
        model = Action
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(ActionForm, self).__init__(*args, **kwargs)
        self.fields['create_date'].disabled = True
        self.fields['update_date'].disabled = True

        generic_fields = ['title', 'owner', 'status', 'status_comment']
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


class ControlForm(LoginRequiredMixin, ModelForm):
    class Meta:
        model = Control
        fields = '__all__'


class ControlPointForm(LoginRequiredMixin, ModelForm):
    class Meta:
        model = ControlPoint
        fields = ['control_date', 'control_user', 'status', 'comment']

    def __init__(self, *args, **kwargs):
        super(ControlPointForm, self).__init__(*args, **kwargs)
        self.initial['control_date'] = timezone.now()
        self.fields['control_date'].disabled = True

        if self.get_initial_for_field(self.fields['status'], 'status') != ControlPoint.Status.TOBEEVALUATED.value:
            for field in self.fields:
                self.fields[field].disabled = True
