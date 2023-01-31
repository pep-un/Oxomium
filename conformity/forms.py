'''
Forms for front-end editing of Models instance
'''

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
            self.fields['status'].widget.attrs['readonly'] = True
            self.fields['status'].widget.attrs['title'] = 'This field is calculated from children.'


class OrganizationForm(LoginRequiredMixin, ModelForm):
    class Meta:
        model = Organization
        fields = '__all__'


class AuditForm(LoginRequiredMixin, ModelForm):
    class Meta:
        model = Audit
        fields = '__all__'
