"""
Forms for front-end editing of Models instance
"""

from django.forms import ModelForm, FileField, ClearableFileInput, BooleanField, ModelChoiceField, ModelMultipleChoiceField
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .models import (
    Action, Audit, Conformity, Control, ControlPoint, DocumentEvidence, Evidence,
    Finding, FindingEvidence, HumanEvidence, Indicator, IndicatorPoint,
    ManualEvidence, Organization,
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


class HumanEvidenceForm(ModelForm):
    class Meta:
        model = HumanEvidence
        fields = ['decision', 'valid_from', 'valid_to', 'comment']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound and self.instance.pk is None:
            valid_from = self.initial.get('valid_from') or timezone.now()
            self.initial['valid_from'] = valid_from
            if not self.initial.get('valid_to'):
                self.initial['valid_to'] = valid_from + timedelta(days=365)


class EvidenceForm(ModelForm):
    class Meta:
        model = Evidence
        fields = ['result', 'valid_from', 'valid_to', 'evaluator', 'comment']


class ManualEvidenceForm(ModelForm):
    class Meta:
        model = ManualEvidence
        fields = ['title', 'result', 'valid_from', 'valid_to', 'comment']


class DocumentEvidenceForm(ModelForm):
    class Meta:
        model = DocumentEvidence
        fields = ['title', 'document', 'result', 'valid_from', 'valid_to', 'comment']


class FindingEvidenceForm(ModelForm):
    class Meta:
        model = FindingEvidence
        fields = ['finding', 'result', 'valid_from', 'valid_to', 'comment']


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


class FindingForm(ModelForm):
    class Meta:
        model = Finding
        fields = ['name', 'audit', 'severity', 'short_description', 'description', 'observation', 'recommendation', 'reference', 'cvss', 'cvss_descriptor', 'archived']
    def __init__(self, *args, **kwargs):
        super(FindingForm, self).__init__(*args, **kwargs)

        # Only lock the audit when creating a finding from an audit page.
        # Existing findings carry their audit in initial too and must stay editable.
        if self.instance.pk is None and self.initial.get('audit'):
            audit = self.initial['audit']
            self.fields['audit'].disabled = True
            if isinstance(audit, Audit):
                self.initial['organization'] = audit.organization
            self.fields['organization'] = ModelChoiceField(
                queryset=Organization.objects.all(), required=False, disabled=True
            )
            self.order_fields([
                'name', 'audit', 'organization', 'severity', 'short_description',
                'description', 'observation', 'recommendation', 'reference', 'cvss',
                'cvss_descriptor', 'archived',
            ])
        if self.get_initial_for_field(self.fields['archived'], 'archived') :
            for key, value in self.fields.items():
                self.fields[key].disabled = True


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
                control__organization_id=organization_id
            )

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
    # Compatibility UI: users still select organization-specific Conformity
    # records, but the Control stores only normative Requirement targets.
    conformity = ModelMultipleChoiceField(queryset=Conformity.objects.all(), required=False)

    class Meta:
        model = Control
        fields = ['title', 'description', 'organization', 'conformity', 'control', 'frequency', 'level']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        organization = self.initial.get('organization')
        if organization is None:
            organization_id = self.instance.organization_id
        else:
            organization_id = getattr(organization, 'pk', organization)

        if self.instance.pk and 'conformity' not in self.initial:
            self.initial['conformity'] = Conformity.objects.filter(
                organization_id=self.instance.organization_id,
                requirement__in=self.instance.requirements.all(),
            )

        if organization_id:
            self.fields['conformity'].queryset = Conformity.objects.filter(
                organization_id=organization_id
            )
            self.fields['control'].queryset = Control.objects.filter(
                organization_id=organization_id
            )
        if self.instance.pk is None and 'organization' in self.initial:
            self.fields['organization'].disabled = True
        if self.instance.pk is None and self.initial.get('conformity'):
            self.fields['conformity'].disabled = True

    def _save_m2m(self):
        super()._save_m2m()
        conformities = self.cleaned_data.get('conformity')
        if conformities is not None:
            self.instance.requirements.set(conformities.values_list('requirement_id', flat=True))


class ControlPointForm(AttachmentUploadFormMixin, ModelForm):
    attachments = MultipleFileField(required=False)
    class Meta:
        model = ControlPoint
        fields = ['evaluated_at', 'evaluator', 'status', 'comment', 'attachments']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super(ControlPointForm, self).__init__(*args, **kwargs)

        # Set some value for all situation
        self.fields['evaluated_at'].disabled = True
        self.fields['evaluator'].disabled = True

        # Set some value if the ControlPoint has to be evaluated
        if self.get_initial_for_field(self.fields['status'], 'status') == ControlPoint.Status.TOBEEVALUATED.value:
            self.initial['evaluated_at'] = timezone.now()
            self.initial['evaluator'] = self.user
            self.fields['status'].widget.choices = [
                (ControlPoint.Status.COMPLIANT, ControlPoint.Status.COMPLIANT.label),
                (ControlPoint.Status.NONCOMPLIANT, ControlPoint.Status.NONCOMPLIANT.label),
            ]
        # Keep attachment uploads available even when the control result is read-only.
        else:
            for field_name, field in self.fields.items():
                if field_name != 'attachments':
                    field.disabled = True


class IndicatorForm(ModelForm):
    conformity = ModelMultipleChoiceField(queryset=Conformity.objects.all(), required=False)

    class Meta:
        model = Indicator
        fields = [
            'name', 'goal', 'source', 'formula', 'worst', 'critical', 'warning', 'best',
            'responsible', 'organization', 'conformity', 'frequency',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        organization = self.initial.get('organization')
        if organization is None:
            organization_id = self.instance.organization_id
        else:
            organization_id = getattr(organization, 'pk', organization)

        if self.instance.pk and 'conformity' not in self.initial:
            self.initial['conformity'] = Conformity.objects.filter(
                organization_id=self.instance.organization_id,
                requirement__in=self.instance.requirements.all(),
            )
        if organization_id:
            self.fields['conformity'].queryset = Conformity.objects.filter(
                organization_id=organization_id
            )

    def _save_m2m(self):
        super()._save_m2m()
        conformities = self.cleaned_data.get('conformity')
        if conformities is not None:
            self.instance.requirements.set(conformities.values_list('requirement_id', flat=True))


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
