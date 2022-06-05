'''
Forms for front-end editing of Models instance
'''

from django.forms import ModelForm
from .models import *

class ConformityForm(ModelForm):
    class Meta:
        model = Conformity
        fields = ['applicable', 'responsible','status', 'comment']

class OrganizationForm(ModelForm):
    class Meta:
        model = Organization
        fields = '__all__'
