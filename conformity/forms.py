"""
Forms for front-end editing of Models instance
"""

from datetime import timedelta

from django import forms
from django.forms import Form, ModelForm, FileField, ClearableFileInput, BooleanField, ModelChoiceField, ModelMultipleChoiceField
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .models import (
    Action, Audit, Conformity, Control, ControlPoint, DocumentEvidence, Evidence,
    Finding, HumanEvidence, Indicator, IndicatorPoint, ManualEvidence,
    Organization,
)
from .validators import attachment_accept, attachment_max_size_help, validate_attachment_once


class MultipleFileInput(ClearableFileInput):
    """Native file input supporting several selected files."""

    allow_multiple_selected = True


class MultipleFileField(FileField):
    """Validate every file submitted through a multiple file input."""

    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if isinstance(data, (list, tuple)):
            return [FileField.clean(self, item, initial) for item in data]
        if data:
            return [FileField.clean(self, data, initial)]
        return []


class EvidenceValidityFormMixin:
    """Render Evidence validity bounds with native date/time pickers."""

    datetime_local_format = '%Y-%m-%dT%H:%M'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ('valid_from', 'valid_to'):
            field = self.fields.get(field_name)
            if field is None:
                continue
            field.widget = forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'step': 300},
                format=self.datetime_local_format,
            )
            field.input_formats = [
                self.datetime_local_format,
                '%Y-%m-%dT%H:%M:%S',
                *field.input_formats,
            ]


class AttachmentUploadFormMixin:
    """Apply the shared attachment policy to every multi-upload form."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields.get('attachments')
        if field:
            field.widget.attrs['accept'] = attachment_accept()
            field.widget.attrs['form'] = 'object-form'
            field.widget.attrs['class'] = 'visually-hidden js-attachment-input'
            field.help_text = attachment_max_size_help()

    def clean_attachments(self):
        uploaded_files = self.cleaned_data.get('attachments') or []
        for uploaded_file in uploaded_files:
            validate_attachment_once(uploaded_file)
        return uploaded_files

    def _save_m2m(self):
        """Do not feed uploaded file objects into a model Attachment M2M."""
        uploads = self.cleaned_data.pop('attachments', None)
        try:
            super()._save_m2m()
        finally:
            if uploads is not None:
                self.cleaned_data['attachments'] = uploads


class ConformityForm(ModelForm):
    propagate_to_children = BooleanField(
        required=False, label='Apply applicability and comment to child requirements'
    )

    class Meta:
        model = Conformity
        fields = ['applicable', 'responsible', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={
                'placeholder': 'Comment required',
                'class': 'form-control w-100',
            }),
        }


class EvidenceRequirementForm(Form):
    conformity = ModelChoiceField(
        queryset=Conformity.objects.none(),
        label='Requirement',
    )

    def __init__(self, *args, evidence=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = (
            Conformity.objects
            .filter(requirement__rght=models.F('requirement__lft') + 1)
            .select_related('organization', 'requirement__framework')
            .order_by(
                'organization__name',
                'requirement__framework__name',
                'requirement__tree_id',
                'requirement__lft',
            )
        )
        if evidence is not None:
            if evidence.periodic_organization is not None:
                queryset = queryset.filter(
                    organization=evidence.periodic_organization,
                )
            queryset = queryset.exclude(
                pk__in=evidence.conformities.values_list('pk', flat=True),
            )
        self.fields['conformity'].queryset = queryset


class HumanEvidenceForm(AttachmentUploadFormMixin, EvidenceValidityFormMixin, ModelForm):
    attachments = MultipleFileField(required=False)
    class Meta:
        model = HumanEvidence
        fields = ['decision', 'valid_from', 'valid_to', 'comment', 'attachments']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound and self.instance.pk is None:
            valid_from = self.initial.get('valid_from') or timezone.now()
            self.initial['valid_from'] = valid_from
            if not self.initial.get('valid_to'):
                self.initial['valid_to'] = valid_from + timedelta(days=365)


class EvidenceForm(AttachmentUploadFormMixin, EvidenceValidityFormMixin, ModelForm):
    attachments = MultipleFileField(required=False)
    class Meta:
        model = Evidence
        fields = ['result', 'valid_from', 'valid_to', 'evaluator', 'comment', 'attachments']


class ManualEvidenceForm(AttachmentUploadFormMixin, EvidenceValidityFormMixin, ModelForm):
    attachments = MultipleFileField(required=False)
    class Meta:
        model = ManualEvidence
        fields = ['title', 'result', 'valid_from', 'valid_to', 'comment', 'attachments']


class DocumentEvidenceForm(AttachmentUploadFormMixin, EvidenceValidityFormMixin, ModelForm):
    attachments = MultipleFileField(required=False)
    class Meta:
        model = DocumentEvidence
        fields = ['title', 'document', 'result', 'valid_from', 'valid_to', 'comment', 'attachments']


class OrganizationForm(AttachmentUploadFormMixin, ModelForm):
    attachments = MultipleFileField(required=False)
    class Meta:
        model = Organization
        fields = ['name', 'administrative_id', 'description', 'applicable_frameworks']


class AuditForm(AttachmentUploadFormMixin, ModelForm):
    attachments = MultipleFileField(required=False)
    class Meta:
        model = Audit
        fields = ['name', 'organization', 'description', 'conclusion', 'auditor', 'audited_frameworks', 'start_date',
                  'end_date', 'report_date', 'type', 'attachments']


class FindingForm(
    AttachmentUploadFormMixin,
    EvidenceValidityFormMixin,
    ModelForm,
):
    attachments = MultipleFileField(required=False)

    class Meta:
        model = Finding
        fields = [
            'name', 'audit', 'severity', 'short_description', 'description',
            'observation', 'recommendation', 'reference', 'cvss',
            'cvss_descriptor', 'valid_from', 'valid_to', 'comment',
            'attachments',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['valid_from'].required = False
        self.fields['audit'].required = False
        self.fields['cvss'].widget.attrs.update({
            'min': 0,
            'max': 10,
            'step': 0.1,
        })

        if not self.is_bound and self.instance.pk is None:
            valid_from = self.initial.get('valid_from') or timezone.now()
            self.initial['valid_from'] = valid_from
            if not self.initial.get('valid_to'):
                self.initial['valid_to'] = Finding._plus_years(valid_from, 3)

        audit = self.initial.get('audit')
        if self.instance.pk is None and audit:
            self.fields['audit'].disabled = True
            if isinstance(audit, Audit):
                self.initial['organization'] = audit.organization
            self.fields['organization'] = ModelChoiceField(
                queryset=Organization.objects.all(),
                required=False,
                disabled=True,
            )
            self.order_fields([
                'name', 'audit', 'organization', 'severity',
                'short_description', 'description', 'observation',
                'recommendation', 'reference', 'cvss', 'cvss_descriptor',
                'valid_from', 'valid_to', 'comment', 'attachments',
            ])

        conformity = self.initial.get('conformity')
        if self.instance.pk is None and conformity:
            organization = conformity.organization
            self.fields['audit'].queryset = Audit.objects.filter(
                organization=organization
            )
            self.fields['organization'] = ModelChoiceField(
                queryset=Organization.objects.filter(pk=organization.pk),
                required=False,
                disabled=True,
                initial=organization,
            )
            self.order_fields([
                'name', 'organization', 'audit', 'severity',
                'short_description', 'description', 'observation',
                'recommendation', 'reference', 'cvss', 'cvss_descriptor',
                'valid_from', 'valid_to', 'comment', 'attachments',
            ])


class ActionForm(ModelForm):
    class Meta:
        model = Action
        fields = [
            'title', 'create_date', 'update_date', 'owner', 'status', 'status_comment',
            'reference', 'active', 'priority', 'description', 'organization', 'associated_conformity',
            'associated_findings', 'associated_controlPoints', 'plan_start_date',
            'plan_end_date', 'plan_comment', 'implement_start_date', 'implement_end_date',
            'implement_status', 'implement_comment', 'control_date', 'control_comment',
            'control_user',
        ]

    def __init__(self, *args, **kwargs):
        super(ActionForm, self).__init__(*args, **kwargs)
        self.fields['create_date'].disabled = True
        self.fields['update_date'].disabled = True
        self.fields['priority'].choices = [('', _('Not defined')), *Action.Priority.choices]

        organization = self.initial.get('organization')
        if organization is None:
            organization_id = self.instance.organization_id
        else:
            organization_id = getattr(organization, 'pk', organization)
        if organization_id:
            self.fields['associated_conformity'].queryset = Conformity.objects.filter(
                organization_id=organization_id
            )
            self.fields['associated_findings'].queryset = Finding.objects.filter(
                audit__organization_id=organization_id
            )
            self.fields['associated_controlPoints'].queryset = ControlPoint.objects.filter(
                control__conformity__organization_id=organization_id
            ).distinct()

        if self.instance.pk is None and self.initial.get('associated_findings'):
            self.fields['associated_findings'].disabled = True
        if self.instance.pk is None and self.initial.get('associated_conformity'):
            self.fields['associated_conformity'].disabled = True
        if self.instance.pk is None and 'organization' in self.initial:
            self.fields['organization'].disabled = True

        generic_fields = ['title', 'owner', 'status', 'status_comment', 'reference', 'priority']
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

        current_status = self.get_initial_for_field(self.fields['status'], 'status')
        for key, value in self.fields.items():
            if key not in fields_by_status[current_status]:
                self.fields[key].disabled = True

        if (
            self.instance.pk is not None
            and current_status != Action.Status.ANALYSING.value
            and self.instance.priority is not None
        ):
            self.fields['priority'].disabled = True


class ControlForm(ModelForm):
    class Meta:
        model = Control
        fields = ['title', 'description', 'conformity', 'control', 'frequency', 'level']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk is None and self.initial.get('conformity'):
            self.fields['conformity'].disabled = True


class ControlPointForm(AttachmentUploadFormMixin, ModelForm):
    attachments = MultipleFileField(required=False)
    class Meta:
        model = ControlPoint
        fields = ['evaluated_at', 'evaluator', 'result', 'comment', 'attachments']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super(ControlPointForm, self).__init__(*args, **kwargs)

        # Set some value for all situation
        self.fields['evaluated_at'].disabled = True
        self.fields['evaluator'].disabled = True

        # Set some value if the ControlPoint has to be evaluated
        if self.instance.status == Evidence.Status.TOBEEVALUATED:
            self.initial['evaluated_at'] = timezone.now()
            self.initial['evaluator'] = self.user
            self.fields['result'].widget.choices = [
                (Evidence.Result.POSITIVE, _('Compliant')),
                (Evidence.Result.NEGATIVE, _('Non-Compliant')),
            ]
        # Keep attachment uploads available even when the control result is read-only.
        else:
            for field_name, field in self.fields.items():
                if field_name != 'attachments':
                    field.disabled = True


class IndicatorForm(ModelForm):
    class Meta:
        model = Indicator
        fields = [
            'name', 'goal', 'source', 'formula', 'worst', 'critical', 'warning', 'best',
            'responsible', 'conformity', 'frequency',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk is None and self.initial.get('conformity'):
            self.fields['conformity'].disabled = True


class IndicatorPointForm(AttachmentUploadFormMixin, ModelForm):
    attachments = MultipleFileField(required=False)

    class Meta:
        model = IndicatorPoint
        fields = ['value', 'comment', 'attachments']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.indicator_id is not None:
            lower, upper = self.instance.indicator.value_bounds
            self.fields['value'].widget.attrs.update(min=lower, max=upper, step=1)
            self.fields['value'].help_text = _(
                'Enter an integer between %(lower)s and %(upper)s (inclusive).'
            ) % {'lower': lower, 'upper': upper}

        if self.instance.status != Evidence.Status.TOBEEVALUATED:
            for field_name, field in self.fields.items():
                if field_name != 'attachments':
                    field.disabled = True
