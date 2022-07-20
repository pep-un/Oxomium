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


class OrganizationForm(LoginRequiredMixin, ModelForm):
    class Meta:
        model = Organization
        fields = '__all__'


class AuditForm(LoginRequiredMixin, ModelForm):
    class Meta:
        model = Audit
        fields = '__all__'
