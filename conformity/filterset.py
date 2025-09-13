from cProfile import label
from random import choices

from django_filters import FilterSet, CharFilter, DateFromToRangeFilter, ModelChoiceFilter, ChoiceFilter, NumberFilter
from .models import Action, Control, ControlPoint, Conformity, Finding, Requirement, Framework, Organization, Audit, \
    Indicator


class ActionFilter(FilterSet):
    title = CharFilter(lookup_expr='icontains', label="Title")
    associated_conformity = ModelChoiceFilter(queryset=Conformity.objects.all(), label='Conformity')
    associated_findings = ModelChoiceFilter(queryset=Finding.objects.all(), label='Finding')
    associated_controlPoints = ModelChoiceFilter(queryset=ControlPoint.objects.all(), label='Control Point')

    class Meta:
        model = Action
        fields = ['title', 'owner', 'status', 'organization',
                  'associated_conformity', 'associated_findings', 'associated_controlPoints']


class ControlFilter(FilterSet):
    title = CharFilter(lookup_expr='icontains', label="Title")
    conformity = ModelChoiceFilter(queryset=Conformity.objects.all(), label='Conformity')

    class Meta:
        model = Control
        fields = ['title', 'level', 'frequency', 'organization',
                  'conformity']


class ControlPointFilter(FilterSet):
    control = ModelChoiceFilter(queryset=Control.objects.all(), label='Control')
    class Meta:
        model = ControlPoint
        fields = [ 'status',
                   'control', 'control__frequency']

class FrameworkFilter(FilterSet):
    name = CharFilter(lookup_expr='icontains', label="Name")
    publish_by = CharFilter(lookup_expr='icontains', label="Publish by")
    type = ChoiceFilter(choices=Framework.Type.choices, label='Type')
    language = ChoiceFilter(choices=Framework.Language.choices, label='Language')

    class Meta:
        model = Framework
        fields = [ 'name', 'version', 'language', 'publish_by', 'type' ]

class OrganizationFilter(FilterSet):
    name = CharFilter(lookup_expr='icontains', label="Name")
    description = CharFilter(lookup_expr='icontains', label="Description")
    administrative_id = CharFilter(lookup_expr='icontains', label="Administrative identifier")

    class Meta:
        model = Organization
        fields = [ 'name', 'description', 'administrative_id' ]

class ConformityFilter(FilterSet):
    organization = ModelChoiceFilter(queryset=Organization.objects.all(), label="Organization")
    requirement__framework = ModelChoiceFilter(queryset=Framework.objects.all(), label="Framework")

    class Meta:
        model = Conformity
        fields = [ 'organization', 'requirement__framework' ]

class AuditFilter(FilterSet):
    name = CharFilter(lookup_expr='icontains', label='Name')
    auditor = CharFilter(lookup_expr='icontains', label='Auditor')
    type = ChoiceFilter(choices=Audit.Type.choices, label='Type')

    class Meta:
        model = Audit
        fields = [ 'name', 'auditor', 'type' ]

class FindingFilter(FilterSet):
    name = CharFilter(lookup_expr='icontains', label='Name')
    short_description = CharFilter(lookup_expr='icontains', label='Short Description')
    cvss = CharFilter(lookup_expr='icontains', label='CVSS')

    class Meta:
        model = Finding
        fields = [ 'name', 'short_description', 'cvss']

class IndicatorFilter(FilterSet):
    name = CharFilter(lookup_expr='icontains', label='Name')
    goal = CharFilter(lookup_expr='icontains', label='Goal')

    class Meta:
        model = Indicator
        fields = [ 'name', 'goal' ]