from cProfile import label
from random import choices

from auditlog.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django import forms
from django_filters import FilterSet, CharFilter, DateFilter, ModelChoiceFilter, ChoiceFilter
from .models import Action, Control, ControlPoint, Conformity, Finding, Requirement, Framework, Organization, Audit, \
    Indicator


def audit_actor_choices():
    return [
        ('system', 'Oxomium'),
        *(
            (str(user.pk), user.get_username())
            for user in get_user_model().objects.order_by('username')
        ),
    ]


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
    action = ModelChoiceFilter(
        field_name='actions',
        queryset=Action.objects.all(),
        label='Action',
        distinct=True,
    )

    class Meta:
        model = ControlPoint
        fields = ['status', 'control', 'control__frequency', 'action']

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
    action = ModelChoiceFilter(
        queryset=Action.objects.all(),
        label='Action',
        method='filter_action',
    )

    class Meta:
        model = Conformity
        fields = ['organization', 'requirement__framework', 'action']

    def filter_action(self, queryset, name, action):
        if not action:
            return queryset

        mappings = action.associated_conformity.values_list(
            'organization_id',
            'requirement__framework_id',
        ).distinct()

        condition = Q(pk__in=[])
        for organization_id, framework_id in mappings:
            condition |= Q(
                organization_id=organization_id,
                requirement__framework_id=framework_id,
            )
        return queryset.filter(condition)

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
    audit = ModelChoiceFilter(queryset=Audit.objects.all(), label='Audit')
    action = ModelChoiceFilter(
        field_name='actions',
        queryset=Action.objects.all(),
        label='Action',
        distinct=True,
    )

    class Meta:
        model = Finding
        fields = ['name', 'short_description', 'cvss', 'audit', 'action']

class IndicatorFilter(FilterSet):
    name = CharFilter(lookup_expr='icontains', label='Name')
    goal = CharFilter(lookup_expr='icontains', label='Goal')

    class Meta:
        model = Indicator
        fields = [ 'name', 'goal' ]


class AuditLogFilter(FilterSet):
    object_repr = CharFilter(
        lookup_expr='icontains',
        label='Object',
    )
    object_pk = CharFilter(label='Object ID')
    content_type = ModelChoiceFilter(
        queryset=ContentType.objects.order_by('app_label', 'model'),
        label='Object type',
    )
    action = ChoiceFilter(choices=LogEntry.Action.choices, label='Action')
    actor = ChoiceFilter(
        choices=audit_actor_choices,
        method='filter_actor',
        label='User',
    )
    remote_addr = CharFilter(lookup_expr='icontains', label='IP address')
    timestamp_after = DateFilter(
        field_name='timestamp',
        lookup_expr='date__gte',
        label='From date',
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    timestamp_before = DateFilter(
        field_name='timestamp',
        lookup_expr='date__lte',
        label='To date',
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(attrs={'type': 'date'}),
    )

    class Meta:
        model = LogEntry
        fields = [
            'object_repr', 'object_pk', 'content_type', 'action', 'actor',
            'remote_addr', 'timestamp_after', 'timestamp_before',
        ]

    def filter_actor(self, queryset, name, value):
        if value == 'system':
            return queryset.filter(Q(actor__isnull=True) | Q(actor_email='system'))
        return queryset.filter(actor_id=value)