from cProfile import label
from random import choices

from auditlog.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django import forms
from django_filters import (
    FilterSet, CharFilter, DateFilter, ModelChoiceFilter, ChoiceFilter,
    MultipleChoiceFilter,
)
from .models import Action, Attachment, Control, ControlPoint, Conformity, Finding, Requirement, Framework, Organization, Audit, \
    Evidence, Indicator, IndicatorPoint


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
        fields = ['title', 'owner', 'status', 'priority', 'organization',
                  'associated_conformity', 'associated_findings', 'associated_controlPoints']


class ControlFilter(FilterSet):
    title = CharFilter(lookup_expr='icontains', label="Title")
    conformity = ModelChoiceFilter(queryset=Conformity.objects.all(), label='Conformity')

    class Meta:
        model = Control
        fields = ['title', 'level', 'frequency', 'organization',
                  'conformity']


class PeriodicEvidenceFilter(FilterSet):
    name = CharFilter(
        method='filter_name',
        label='Name',
    )
    status = ChoiceFilter(
        choices=(
            (ControlPoint.Status.TOBEEVALUATED, 'To evaluate'),
            (ControlPoint.Status.SCHEDULED, 'Scheduled'),
            (ControlPoint.Status.COMPLIANT, 'Compliant'),
            (ControlPoint.Status.NONCOMPLIANT, 'Non-Compliant'),
            (IndicatorPoint.Status.WARNING, 'Warning'),
            (IndicatorPoint.Status.CRITICAL, 'Critical'),
            (ControlPoint.Status.MISSED, 'Missed'),
        ),
        method='filter_status',
        label='Last result',
    )
    organization = ModelChoiceFilter(
        queryset=Organization.objects.all(),
        method='filter_organization',
        label='Organization',
    )
    source_type = ChoiceFilter(
        choices=(
            (Evidence.SourceType.CONTROL, 'Control'),
            (Evidence.SourceType.INDICATOR, 'Indicator'),
        ),
        label='Type',
    )
    level = ChoiceFilter(
        choices=Control.Level.choices,
        method='filter_level',
        label='Level',
    )
    frequency = ChoiceFilter(
        choices=Control.Frequency.choices,
        method='filter_frequency',
        label='Frequency',
    )
    requirement = ModelChoiceFilter(
        queryset=Requirement.objects.all(),
        field_name='conformities__requirement',
        label='Associated requirement',
        distinct=True,
    )
    reference = ModelChoiceFilter(
        queryset=Framework.objects.all(),
        field_name='conformities__requirement__framework',
        label='Associated Framework',
        distinct=True,
    )

    class Meta:
        model = Evidence
        fields = [
            'name', 'status', 'organization', 'source_type', 'level',
            'frequency', 'requirement', 'reference',
        ]

    def filter_name(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(controlpoint__control__title__icontains=value)
            | Q(indicatorpoint__indicator__name__icontains=value)
        )

    def filter_status(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(controlpoint__status=value)
            | Q(indicatorpoint__status=value)
        )

    def filter_organization(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(controlpoint__control__organization=value)
            | Q(indicatorpoint__indicator__organization=value)
        )

    def filter_level(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(controlpoint__control__level=value)

    def filter_frequency(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(controlpoint__control__frequency=value)
            | Q(indicatorpoint__indicator__frequency=value)
        )


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
    nature = MultipleChoiceFilter(
        field_name='severity',
        choices=Finding.Severity.choices,
        label='Nature',
    )
    status = ChoiceFilter(
        choices=(('active', 'Active'), ('archived', 'Archived')),
        method='filter_status',
        label='Status',
    )
    audit = ModelChoiceFilter(queryset=Audit.objects.all(), label='Audit')
    action = ModelChoiceFilter(
        field_name='actions',
        queryset=Action.objects.all(),
        label='Action',
        distinct=True,
    )

    class Meta:
        model = Finding
        fields = [
            'name', 'short_description', 'cvss', 'nature', 'status',
            'audit', 'action',
        ]

    def filter_status(self, queryset, name, value):
        if value == 'active':
            return queryset.filter(archived=False)
        if value == 'archived':
            return queryset.filter(archived=True)
        return queryset

class IndicatorFilter(FilterSet):
    name = CharFilter(lookup_expr='icontains', label='Name')
    goal = CharFilter(lookup_expr='icontains', label='Goal')

    class Meta:
        model = Indicator
        fields = [ 'name', 'goal' ]



class AttachmentFilter(FilterSet):
    file = CharFilter(field_name='file', lookup_expr='icontains', label='File name')
    mime_type = CharFilter(lookup_expr='icontains', label='MIME type')
    sha256 = CharFilter(lookup_expr='icontains', label='SHA-256')
    organization = ModelChoiceFilter(field_name='organizations', queryset=Organization.objects.all(), label='Organization', distinct=True)
    framework = ModelChoiceFilter(field_name='frameworks', queryset=Framework.objects.all(), label='Framework', distinct=True)
    audit = ModelChoiceFilter(field_name='audits', queryset=Audit.objects.all(), label='Audit', distinct=True)
    control_point = ModelChoiceFilter(field_name='evidence__controlpoint', queryset=ControlPoint.objects.all(), label='Control Point', distinct=True)
    indicator_point = ModelChoiceFilter(field_name='evidence__indicatorpoint', queryset=IndicatorPoint.objects.all(), label='Indicator Point', distinct=True)
    create_date_after = DateFilter(
        field_name='create_date', lookup_expr='date__gte', label='Created from',
        input_formats=['%Y-%m-%d'], widget=forms.DateInput(attrs={'type': 'date'}),
    )
    create_date_before = DateFilter(
        field_name='create_date', lookup_expr='date__lte', label='Created to',
        input_formats=['%Y-%m-%d'], widget=forms.DateInput(attrs={'type': 'date'}),
    )

    class Meta:
        model = Attachment
        fields = [
            'file', 'mime_type', 'sha256', 'organization', 'framework', 'audit',
            'control_point', 'indicator_point', 'create_date_after', 'create_date_before',
        ]


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