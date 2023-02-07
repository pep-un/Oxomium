"""
Forms for front-end editing of Models instance
"""

from django.forms import ModelForm
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import *


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
        analyse_fields = ['organization', 'associated_conformity', 'associated_findings', 'description']
        plan_fields = ['plan_start_date', 'plan_end_date', 'plan_comment']
        implement_fields = ['implement_start_date', 'implement_end_date', 'implement_status', 'implement_comment']
        control_fields = ['control_date', 'control_comment', 'control_user']

        '''Disable everything and enable only the on matching the current status'''
        for key, value in self.fields.items():
            if key not in generic_fields:
                self.fields[key].disabled = True

        if self.get_initial_for_field(self.fields['status'], 'status') is Action.Status.ANALYSING.value:
            for key in analyse_fields:
                self.fields[key].disabled = False
        elif self.get_initial_for_field(self.fields['status'], 'status') is Action.Status.PLANNING.value:
            for key in plan_fields:
                self.fields[key].disabled = False
        elif self.get_initial_for_field(self.fields['status'], 'status') is Action.Status.IMPLEMENTING.value:
            for key in implement_fields:
                self.fields[key].disabled = False
        elif self.get_initial_for_field(self.fields['status'], 'status') is Action.Status.CONTROLLING.value:
            for key in control_fields:
                self.fields[key].disabled = False
        elif self.get_initial_for_field(self.fields['status'], 'status') is Action.Status.CANCELED.value:
            for key in generic_fields:
                self.fields[key].disabled = True
        elif self.get_initial_for_field(self.fields['status'], 'status') is Action.Status.ENDED.value:
            for key in generic_fields:
                self.fields[key].disabled = True
