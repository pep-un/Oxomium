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

        if self.get_initial_for_field(self.fields['status'], 'status') is Action.Status.CANCELED.value \
                or self.get_initial_for_field(self.fields['status'], 'status') is Action.Status.ENDED.value:
            for key, value in self.fields.items():
                self.fields[key].disabled = True
