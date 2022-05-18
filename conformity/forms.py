from django.forms import ModelForm
from .models import *

class ConformityForm(ModelForm):
    class Meta:
        model = Conformity
        fields = ['responsible','status']

class OrganizationForm(ModelForm):
    class Meta:
        model = Organization
        fields = '__all__'