"""
View of the Conformity Module
"""

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Count, F, Prefetch, Q
from django.views.generic import DetailView, ListView, TemplateView
from django.views.generic.edit import UpdateView, CreateView, FormView
from django_filters import FilterSet
from django_filters.views import FilterView
from constance import config as constance_config
from django_tables2.views import SingleTableMixin
from django.utils import timezone
from auditlog.models import LogEntry
from import_export.formats import base_formats
from import_export.resources import ModelResource
from mptt.templatetags.mptt_tags import cache_tree_children

from .filterset import ActionFilter, ControlFilter, ControlPointFilter, FrameworkFilter, OrganizationFilter, \
    ConformityFilter, AuditFilter, FindingFilter, IndicatorFilter, AttachmentFilter, AuditLogFilter, \
    PeriodicControlFilter
from .forms import (
    ActionForm, AuditForm, ConformityForm, ControlForm, ControlPointForm,
    DocumentEvidenceForm, EvidenceForm, FindingForm, HumanEvidenceForm,
    IndicatorForm, IndicatorPointForm, ManualEvidenceForm,
    OrganizationForm, EvidenceRequirementForm,
)
from .models import (
    Action, Attachment, Audit, Conformity, Control, ControlPoint,
    DocumentEvidence, Evidence, Finding, Framework, HumanEvidence, Indicator,
    IndicatorPoint, ManualEvidence, Organization,
    Requirement,
)
from .resources import (
    ActionResource, AttachmentResource, AuditLogResource, AuditResource,
    ConformityResource, ControlPointResource, ControlResource, FindingResource,
    FrameworkResource, IndicatorResource, OrganizationResource,
    PeriodicControlResource,
)
from .tables import (
    ActionTable, AttachmentTable, AuditLogTable, AuditTable, ConformityTable,
    ControlTable, ControlPointTable, FindingTable, FrameworkTable,
    OrganizationTable, PeriodicControlTable,
)
from .services.attachments import unlink_attachment

from django.views import View
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
import os

class SaveStayMixin:
    """Redirect back to the edit form when Save & Stay is requested."""

    stay_url_name = None

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.POST.get("action") == "save_stay":
            return redirect(self.stay_url_name, self.object.pk)
        return response


class DefaultFilterMixin:
    """Expose and apply a reusable default filter preset."""

    default_filter_url_name = None
    default_filter_params = {}

    def get_default_filter_url(self):
        params = self.request.GET.copy()
        params.clear()
        for key, value in self.default_filter_params.items():
            if isinstance(value, (tuple, list)):
                params.setlist(key, [str(item) for item in value])
            else:
                params[key] = value
        return f"{reverse(self.default_filter_url_name)}?{params.urlencode()}"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['default_filter_url'] = self.get_default_filter_url()
        context['reset_filter_url'] = '?defaults=off'
        return context


class RichTableMixin(SingleTableMixin):
    """Common pagination policy and result counts for filtered rich tables."""

    def get_paginate_by(self, table_data):
        return constance_config.TABLE_PAGE_SIZE

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        table = context.get("table")
        if table is not None and getattr(table, "paginator", None) is not None:
            context["result_total_count"] = table.paginator.count
            context["result_visible_count"] = len(table.page.object_list)
            context["result_is_paginated"] = table.paginator.num_pages > 1
        else:
            object_list = context.get("object_list", ())
            context["result_visible_count"] = len(object_list)
            context["result_total_count"] = len(object_list)
            context["result_is_paginated"] = False
        return context


class FilteredExportMixin:
    """Export all rows or the current filtered selection."""

    resource_class = ModelResource
    filterset_class = FilterSet
    filename = "export"

    def get_export_queryset(self, request):
        raise NotImplementedError

    def get_selection_queryset(self, request):
        return self.get_export_queryset(request)

    def get_queryset_for_export(self, request):
        if request.GET.get("scope") != "selection":
            return self.get_export_queryset(request)

        data = request.GET.copy()
        for key in ("format", "scope", "page", "sort"):
            data.pop(key, None)
        filterset_class = getattr(self, "filterset_class")
        return filterset_class(
            data=data,
            queryset=self.get_selection_queryset(request),
            request=request,
        ).qs

    def get(self, request, *args, **kwargs):
        resource_class = getattr(self, "resource_class")
        dataset = resource_class().export(self.get_queryset_for_export(request))
        export_format = (
            base_formats.CSV()
            if request.GET.get("format") == "csv"
            else base_formats.XLSX()
        )
        response = HttpResponse(
            export_format.export_data(dataset),
            content_type=export_format.get_content_type(),
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{self.filename}.{export_format.get_extension()}"'
        )
        return response


#
# Home
#


class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['organization_list'] = Organization.objects.all()
        context['framework_list'] = Framework.objects.all()
        context['conformity_list'] = Conformity.objects.with_related().roots()
        context['audit_list'] = Audit.objects.all()
        context['action_list'] = Action.objects.all()
        context['my_action'] = Action.objects.filter(owner=user).filter(active=True).order_by('status', 'pk')[:constance_config.HOME_ITEMS_LIMIT]
        context['my_conformity'] = Conformity.objects.with_related().filter(
            responsible=user
        ).order_by('status', 'pk')[:50]
        context['cp_list'] = ControlPoint.objects.filter(status='TOBE').order_by('valid_to', 'pk')[:constance_config.HOME_ITEMS_LIMIT]

        return context


#
# Audit
#
class AuditIndexView(LoginRequiredMixin, RichTableMixin, FilterView):
    model = Audit
    table_class = AuditTable
    filterset_class = AuditFilter
    template_name = "conformity/audit_list.html"

    def get_queryset(self):
        return Audit.objects.annotate(
            findings_count=Count("finding", distinct=True),
        ).order_by("-report_date", "-start_date", "pk")


class AuditDetailView(LoginRequiredMixin, DetailView):
    model = Audit


class AttachmentUploadViewMixin:
    """Surface attachment validation errors from the shared upload forms."""

    def form_invalid(self, form):
        for error in form.errors.get('attachments', ()):
            messages.error(
                self.request,
                f"Attachment upload failed: {error}",
                fail_silently=True,
            )
        return super().form_invalid(form)


class AuditUpdateView(AttachmentUploadViewMixin, LoginRequiredMixin, SaveStayMixin, UpdateView):
    stay_url_name = "conformity:audit_form"
    model = Audit
    form_class = AuditForm

    def form_valid(self, form):
        response = super().form_valid(form)
        attachments = self.request.FILES.getlist('attachments')
        for file in attachments:
            attachment = Attachment.get_or_create_for_upload(file)[0]
            self.object.attachment.add(attachment)
        return response



class AuditCreateView(AttachmentUploadViewMixin, LoginRequiredMixin, SaveStayMixin, CreateView):
    stay_url_name = "conformity:audit_form"
    model = Audit
    form_class = AuditForm

    def form_valid(self, form):
        response = super().form_valid(form)
        attachments = self.request.FILES.getlist('attachments')
        for file in attachments:
            attachment = Attachment.get_or_create_for_upload(file)[0]
            self.object.attachment.add(attachment)
        return response


class AuditExportView(LoginRequiredMixin, FilteredExportMixin, View):
    resource_class = AuditResource
    filterset_class = AuditFilter
    filename = "audits"

    def get_export_queryset(self, request):
        return Audit.objects.all()



#
# Findings
#
class FindingIndexView(DefaultFilterMixin, LoginRequiredMixin, RichTableMixin, FilterView):
    model = Finding
    table_class = FindingTable
    filterset_class = FindingFilter
    template_name = "conformity/finding_list.html"
    default_natures = (
        Finding.Severity.CRITICAL,
        Finding.Severity.MAJOR,
        Finding.Severity.MINOR,
        Finding.Severity.OBSERVATION,
    )
    default_filter_url_name = 'conformity:finding_index'
    default_filter_params = {
        'nature': default_natures,
        'status': 'active',
    }

    def get(self, request, *args, **kwargs):
        if not request.GET:
            return redirect(self.get_default_filter_url())
        return super().get(request, *args, **kwargs)

    def get_queryset(self, **kwargs):
        return (
            Finding.objects
            .select_related("audit")
            .annotate(actions_count=Count("actions", distinct=True))
            .order_by("severity", "pk")
        )


class FindingCreateView(
    AttachmentUploadViewMixin,
    LoginRequiredMixin,
    SaveStayMixin,
    CreateView,
):
    stay_url_name = "conformity:finding_form"
    model = Finding
    form_class = FindingForm

    def get_initial(self):
        initial = super().get_initial()

        conformity_id = self.request.GET.get('conformity')
        if conformity_id:
            try:
                conformity_id = int(conformity_id)
            except ValueError as exc:
                raise Http404('Invalid conformity identifier.') from exc
            conformity = get_object_or_404(Conformity, pk=conformity_id)
            if not conformity.requirement.is_leaf_node():
                raise Http404('Evidence can only target a leaf requirement.')
            initial['conformity'] = conformity
            initial['organization'] = conformity.organization

        audit_id = self.request.GET.get('audit')
        if audit_id:
            try:
                audit_id = int(audit_id)
            except ValueError as exc:
                raise Http404('Invalid audit identifier.') from exc
            audit = get_object_or_404(Audit, pk=audit_id)
            initial['audit'] = audit
            initial['organization'] = audit.organization
        return initial

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save(commit=False)
            if not self.object.evaluator_id:
                self.object.evaluator = self.request.user
            self.object.save()
            form.save_m2m()

            conformity_id = self.request.GET.get('conformity')
            if conformity_id:
                conformity = get_object_or_404(Conformity, pk=conformity_id)
                self.object.conformities.add(conformity)

            for file in self.request.FILES.getlist('attachments'):
                attachment = Attachment.get_or_create_for_upload(file)[0]
                self.object.attachments.add(attachment)

        return HttpResponseRedirect(self.get_success_url())


class FindingDetailView(LoginRequiredMixin, DetailView):
    model = Finding


class FindingUpdateView(
    AttachmentUploadViewMixin,
    LoginRequiredMixin,
    SaveStayMixin,
    UpdateView,
):
    stay_url_name = "conformity:finding_form"
    model = Finding
    form_class = FindingForm

    def form_valid(self, form):
        response = super().form_valid(form)
        for file in self.request.FILES.getlist('attachments'):
            attachment = Attachment.get_or_create_for_upload(file)[0]
            self.object.attachments.add(attachment)
        return response


class FindingExportView(LoginRequiredMixin, FilteredExportMixin, View):
    resource_class = FindingResource
    filterset_class = FindingFilter
    filename = "findings"

    def get_export_queryset(self, request):
        return Finding.objects.all()


#
# Organizations
#


class OrganizationIndexView(LoginRequiredMixin, RichTableMixin, FilterView):
    model = Organization
    table_class = OrganizationTable
    filterset_class = OrganizationFilter
    template_name = "conformity/organization_list.html"

    def get_queryset(self):
        return Organization.objects.prefetch_related("applicable_frameworks").order_by(
            "name", "pk"
        )


class OrganizationDetailView(LoginRequiredMixin, DetailView):
    model = Organization


class OrganizationFrameworkFormMixin(AttachmentUploadViewMixin):
    """Save organization fields and reconcile frameworks through the service."""

    def form_valid(self, form):
        from .services.conformities import set_frameworks

        with transaction.atomic():
            self.object = form.save(commit=False)
            self.object.save()
            set_frameworks(self.object, form.cleaned_data['applicable_frameworks'])
            for file in self.request.FILES.getlist('attachments'):
                attachment = Attachment.get_or_create_for_upload(file)[0]
                self.object.attachment.add(attachment)
        return HttpResponseRedirect(self.get_success_url())


class OrganizationUpdateView(LoginRequiredMixin, SaveStayMixin, OrganizationFrameworkFormMixin, UpdateView):
    stay_url_name = "conformity:organization_form"
    model = Organization
    form_class = OrganizationForm


class OrganizationCreateView(LoginRequiredMixin, SaveStayMixin, OrganizationFrameworkFormMixin, CreateView):
    stay_url_name = "conformity:organization_form"
    model = Organization
    form_class = OrganizationForm

#
# Framework
#


class FrameworkIndexView(LoginRequiredMixin, RichTableMixin, FilterView):
    model = Framework
    table_class = FrameworkTable
    filterset_class = FrameworkFilter
    template_name = 'conformity/framework_list.html'

    def get_queryset(self):
        return Framework.objects.prefetch_related("requirements").order_by("name", "pk")


class FrameworkDetailView(LoginRequiredMixin, DetailView):
    model = Framework

    # Not used yet, to be fixed (issue with recursetree)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = Requirement.objects.for_framework(self.object).with_tree_relations().in_tree_order()
        context['requirement_list'] = cache_tree_children(qs)
        return context


#
# Conformity
#
class ConformityIndexView(LoginRequiredMixin, RichTableMixin, FilterView):
    model = Conformity
    table_class = ConformityTable
    template_name = 'conformity/conformity_list.html'
    filterset_class = ConformityFilter

    def get_queryset(self, **kwargs):
        return Conformity.objects.with_related().roots().order_by(
            "organization",
            "requirement__framework",
            "requirement__tree_id",
            "requirement__lft",
            "pk",
        )


class ConformityDetailIndexView(LoginRequiredMixin, ListView):
    model = Conformity
    template_name = 'conformity/conformity_detail_list.html'

    def get_queryset(self, **kwargs):
        root_id = self.request.GET.get('root_id')

        if root_id:
            root = Conformity.objects.filter(id=root_id)
        else:
            root = Conformity.objects.filter(organization__id=self.kwargs['org']) \
                .filter(requirement__framework__id=self.kwargs['pol']) \
                .filter(requirement__level=0)

        if not root.exists():
            raise Http404("No conformity review exists for this organization and framework.")

        return root


class ConformityUpdateView(LoginRequiredMixin, UpdateView):
    model = Conformity
    form_class = ConformityForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        is_leaf = self.object.requirement.is_leaf_node()

        if is_leaf:
            active_evidence = (
                self.object.evidence.valid_at(now)
                .order_by('-valid_from', '-pk')
            )
        else:
            descendant_conformities = (
                Conformity.objects
                .filter(
                    organization=self.object.organization,
                    requirement__in=self.object.requirement.get_descendants(),
                    requirement__rght=F('requirement__lft') + 1,
                )
                .select_related('requirement')
            )
            active_evidence = (
                Evidence.objects.valid_at(now)
                .filter(conformities__in=descendant_conformities)
                .prefetch_related(
                    Prefetch(
                        'conformities',
                        queryset=descendant_conformities,
                        to_attr='display_conformities',
                    )
                )
                .distinct()
                .order_by('-valid_from', '-pk')
            )

        context['active_evidence'] = active_evidence
        context['show_evidence_conformities'] = not is_leaf
        return context

    def form_valid(self, form):
        # starting point of the set_status and status tree update logic
        self.object = form.save()

        # Child propagation is an explicit form action.
        if form.cleaned_data['propagate_to_children']:
            from .services.conformities import propagate_applicable_and_comment
            propagate_applicable_and_comment(
                self.object, self.object.applicable, self.object.comment
            )
        if "responsible" in form.changed_data:
            self.object.update_responsible()

        # Manage Save&Next and Save&Stay submitting to allow easy filling of the conformity
        if self.request.POST.get("action") == "save_next":
            nxt_req = self.object.requirement.get_next_sibling()
            if nxt_req:
                try:
                    nxt = Conformity.objects.get(
                        organization=self.object.organization,
                        requirement=nxt_req,
                    )
                    return redirect("conformity:conformity_form", nxt.pk)
                except Conformity.DoesNotExist:
                    pass

        elif self.request.POST.get("action") == "save_stay":
            return redirect("conformity:conformity_form", self.object.pk)

        return super().form_valid(form)


def _resolve_evidence_subtype(evidence):
    """Return the concrete Evidence instance when one exists."""
    for accessor in (
        'controlpoint', 'indicatorpoint', 'humanevidence',
        'manualevidence', 'documentevidence', 'finding',
    ):
        try:
            return getattr(evidence, accessor)
        except (AttributeError, ObjectDoesNotExist):
            continue
    return evidence


class EvidenceRequirementAddView(LoginRequiredMixin, FormView):
    template_name = 'conformity/evidence_requirement_form.html'
    form_class = EvidenceRequirementForm

    def dispatch(self, request, *args, **kwargs):
        self.evidence = get_object_or_404(Evidence, pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['evidence'] = self.evidence
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['evidence'] = self.evidence
        return context

    def form_valid(self, form):
        self.evidence.conformities.add(form.cleaned_data['conformity'])
        messages.success(self.request, 'Requirement associated with Evidence.')
        return super().form_valid(form)

    def get_success_url(self):
        if self.evidence.source_type == Evidence.SourceType.CONTROL:
            return reverse('conformity:controlpoint_form', args=[self.evidence.pk])
        if self.evidence.source_type == Evidence.SourceType.INDICATOR:
            return reverse('conformity:indicatorpoint_form', args=[self.evidence.pk])
        return reverse('conformity:evidence_form', args=[self.evidence.pk])


class EvidenceDetailView(LoginRequiredMixin, DetailView):
    model = Evidence
    template_name = 'conformity/evidence_detail.html'
    context_object_name = 'evidence'

    def get_object(self, queryset=None):
        return _resolve_evidence_subtype(super().get_object(queryset))


class EvidenceUpdateView(AttachmentUploadViewMixin, LoginRequiredMixin, UpdateView):
    model = Evidence
    template_name = 'conformity/evidence_form.html'

    form_classes = {
        Evidence.SourceType.HUMAN: HumanEvidenceForm,
        Evidence.SourceType.MANUAL: ManualEvidenceForm,
        Evidence.SourceType.DOCUMENT: DocumentEvidenceForm,
        Evidence.SourceType.FINDING: FindingForm,
    }

    def get_object(self, queryset=None):
        evidence = _resolve_evidence_subtype(super().get_object(queryset))
        if evidence.source_type in {
            Evidence.SourceType.CONTROL,
            Evidence.SourceType.INDICATOR,
        }:
            raise Http404('Control and Indicator evidence are immutable here.')
        return evidence

    def get_form_class(self):
        if type(self.object) is Evidence:
            return EvidenceForm
        try:
            return self.form_classes[self.object.source_type]
        except KeyError as exc:
            raise Http404('Unsupported Evidence type.') from exc

    def get_return_conformity(self):
        if self.object.source_type != Evidence.SourceType.HUMAN:
            return None
        return self.object.conformities.order_by('pk').first()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['return_conformity'] = self.get_return_conformity()
        context['evidence_conformities'] = (
            self.object.conformities
            .select_related('organization', 'requirement__framework')
            .order_by('requirement__tree_id', 'requirement__lft', 'pk')
        )
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        for file in self.request.FILES.getlist('attachments'):
            attachment = Attachment.get_or_create_for_upload(file)[0]
            self.object.attachments.add(attachment)
        return response

    def get_success_url(self):
        conformity = self.get_return_conformity()
        if conformity is not None:
            return reverse('conformity:conformity_form', args=[conformity.pk])
        return reverse('conformity:evidence_detail', args=[self.object.pk])


class ConformityEvidenceCreateMixin:
    """Create an Evidence subtype already attached to one Conformity."""

    template_name = 'conformity/evidence_form.html'
    success_message = 'Evidence recorded.'
    evidence_label = 'Evidence'

    def dispatch(self, request, *args, **kwargs):
        self.conformity = get_object_or_404(
            Conformity,
            pk=kwargs['conformity_pk'],
        )
        if not self.conformity.requirement.is_leaf_node():
            raise Http404('Evidence can only be created for leaf requirements.')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['conformity'] = self.conformity
        context['evidence_conformities'] = [self.conformity]
        context['creating_evidence'] = True
        context['evidence_label'] = self.evidence_label
        return context

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save(commit=False)
            if not self.object.evaluator_id:
                self.object.evaluator = self.request.user
            if not self.object.evaluated_at:
                self.object.evaluated_at = timezone.now()
            self.object.save()
            self.object.conformities.add(self.conformity)
            for file in self.request.FILES.getlist('attachments'):
                attachment = Attachment.get_or_create_for_upload(file)[0]
                self.object.attachments.add(attachment)
        messages.success(self.request, self.success_message)
        return redirect('conformity:conformity_form', self.conformity.pk)


class HumanEvidenceCreateView(
    LoginRequiredMixin,
    ConformityEvidenceCreateMixin,
    CreateView,
):
    model = HumanEvidence
    form_class = HumanEvidenceForm
    success_message = 'Human evidence recorded.'
    evidence_label = 'Human assessment'


class ManualEvidenceCreateView(
    LoginRequiredMixin,
    ConformityEvidenceCreateMixin,
    CreateView,
):
    model = ManualEvidence
    form_class = ManualEvidenceForm
    success_message = 'Manual evidence recorded.'
    evidence_label = 'Manual evidence'


class DocumentEvidenceCreateView(
    LoginRequiredMixin,
    ConformityEvidenceCreateMixin,
    CreateView,
):
    model = DocumentEvidence
    form_class = DocumentEvidenceForm
    success_message = 'Document evidence recorded.'
    evidence_label = 'Document evidence'


class ConformityExportView(LoginRequiredMixin, View):
    def get(self, request, org: int, pol: int, *args, **kwargs):
        framework = get_object_or_404(Framework, pk=pol)
        organization = get_object_or_404(Organization, pk=org)

        qs = (
            Conformity.objects.filter(requirement__framework=framework, organization=organization)
            .select_related("requirement__framework", "organization")
        )
        dataset = ConformityResource().export(qs)

        if request.GET.get("format") == "csv":
            export_format = base_formats.CSV()
        else:
            export_format = base_formats.XLSX()

        data = export_format.export_data(dataset)
        content_type = export_format.get_content_type()
        filename = f"conformity.{export_format.get_extension()}"

        response = HttpResponse(data, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


#
# Action
#


class ActionCreateView(LoginRequiredMixin, SaveStayMixin, CreateView):
    stay_url_name = "conformity:action_form"
    model = Action
    form_class = ActionForm

    def get_initial(self):
        initial = super().get_initial()
        finding_id = self.request.GET.get('finding')
        if finding_id:
            try:
                finding_id = int(finding_id)
            except ValueError as exc:
                raise Http404('Invalid finding identifier.') from exc
            finding = get_object_or_404(Finding, pk=finding_id)
            initial['associated_findings'] = [finding]
            initial['organization'] = finding.audit.organization_id

        conformity_id = self.request.GET.get('conformity')
        if conformity_id:
            try:
                conformity_id = int(conformity_id)
            except ValueError as exc:
                raise Http404('Invalid conformity identifier.') from exc
            conformity = get_object_or_404(Conformity, pk=conformity_id)
            initial['associated_conformity'] = [conformity]
            initial['organization'] = conformity.organization_id
        return initial


class ActionIndexView(LoginRequiredMixin, RichTableMixin, FilterView):
    model = Action
    table_class = ActionTable
    filterset_class = ActionFilter
    template_name = "conformity/action_list.html"

    def get_queryset(self):
        queryset = (
            Action.objects
            .select_related("owner")
            .annotate(
                conformities_count=Count("associated_conformity", distinct=True),
                findings_count=Count("associated_findings", distinct=True),
                controlpoints_count=Count("associated_controlPoints", distinct=True),
            )
        )
        if not self.request.GET.get('status'):
            queryset = queryset.exclude(
                status__in=[Action.Status.ENDED, Action.Status.CANCELED]
            )
        return queryset.order_by(
            F('priority').asc(nulls_last=True),
            'status',
            '-update_date',
            'pk',
        )


class ActionUpdateView(LoginRequiredMixin, SaveStayMixin, UpdateView):
    stay_url_name = "conformity:action_form"
    model = Action
    form_class = ActionForm


class ActionExportView(LoginRequiredMixin, FilteredExportMixin, View):
    resource_class = ActionResource
    filterset_class = ActionFilter
    filename = "actions"

    def get_export_queryset(self, request):
        return Action.objects.all()

    def get_selection_queryset(self, request):
        queryset = Action.objects.all()
        if not request.GET.get("status"):
            queryset = queryset.exclude(
                status__in=[Action.Status.ENDED, Action.Status.CANCELED]
            )
        return queryset



#
# Control
#


class ConformityTargetedSourceCreateMixin:
    """Preselect one Conformity when creating a periodic evidence source."""

    def get_target_conformity(self):
        conformity_id = self.request.GET.get('conformity')
        if not conformity_id:
            return None
        try:
            conformity_id = int(conformity_id)
        except ValueError as exc:
            raise Http404('Invalid conformity identifier.') from exc
        return get_object_or_404(Conformity, pk=conformity_id)

    def get_initial(self):
        initial = super().get_initial()
        conformity = self.get_target_conformity()
        if conformity is not None:
            initial['conformity'] = [conformity]
        return initial

    def get_success_url(self):
        conformity = self.get_target_conformity()
        if conformity is not None and self.request.POST.get("action") != "save_stay":
            return reverse('conformity:conformity_form', args=[conformity.pk])
        return super().get_success_url()


class ControlCreateView(
    LoginRequiredMixin,
    ConformityTargetedSourceCreateMixin,
    SaveStayMixin,
    CreateView,
):
    stay_url_name = "conformity:control_form"
    model = Control
    form_class = ControlForm


def _periodic_sources():
    control_points = ControlPoint.objects.order_by('-valid_from', '-pk')
    indicator_points = IndicatorPoint.objects.order_by('-valid_from', '-pk')
    controls = (
        Control.objects
        .prefetch_related(
            'conformity__organization',
            'conformity__requirement__framework',
            Prefetch('controlpoint_set', queryset=control_points, to_attr='periodic_points'),
        )
    )
    indicators = (
        Indicator.objects
        .prefetch_related(
            'conformity__organization',
            'conformity__requirement__framework',
            Prefetch('indicatorpoint_set', queryset=indicator_points, to_attr='periodic_points'),
        )
    )
    return sorted(
        [*controls, *indicators],
        key=lambda item: (
            ', '.join(sorted({str(conf.organization) for conf in item.conformity.all()})).casefold(),
            item.periodic_name.casefold(),
            item.periodic_kind,
            item.pk,
        ),
    )


class ControlIndexView(DefaultFilterMixin, LoginRequiredMixin, RichTableMixin, TemplateView):
    """Unified periodic source list: Controls and Indicators."""

    table_class = PeriodicControlTable
    template_name = 'conformity/periodic_control_list.html'
    default_filter_url_name = 'conformity:control_index'
    default_filter_params = {
        'status': ControlPoint.Status.TOBEEVALUATED,
    }

    def get(self, request, *args, **kwargs):
        if 'status' not in request.GET and 'defaults' not in request.GET:
            return redirect(self.get_default_filter_url())
        return super().get(request, *args, **kwargs)

    def get_periodic_items(self):
        if not hasattr(self, '_periodic_items'):
            self.periodic_filter = PeriodicControlFilter(
                data=self.request.GET,
                queryset=_periodic_sources(),
                request=self.request,
            )
            self._periodic_items = self.periodic_filter.qs
        return self._periodic_items

    def get_table_data(self):
        return self.get_periodic_items()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        items = self.get_periodic_items()
        context['object_list'] = items
        context['filter'] = self.periodic_filter
        return context


class ControlUpdateView(LoginRequiredMixin, SaveStayMixin, UpdateView):
    stay_url_name = "conformity:control_form"
    model = Control
    form_class = ControlForm


class ControlDetailView(LoginRequiredMixin, DetailView):
    model = Control
    template_name = 'conformity/control_detail_list.html'


class ControlPointIndexView(LoginRequiredMixin, RichTableMixin, FilterView):
    model = ControlPoint
    table_class = ControlPointTable
    filterset_class = ControlPointFilter
    template_name = 'conformity/controlpoint_list.html'

    def get_queryset(self):
        return ControlPoint.objects.select_related(
            "control", "evaluator"
        ).order_by("valid_to", "pk")


class ControlPointUpdateView(AttachmentUploadViewMixin, LoginRequiredMixin, SaveStayMixin, UpdateView):
    stay_url_name = "conformity:controlpoint_form"
    model = ControlPoint
    form_class = ControlPointForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['evidence_conformities'] = (
            self.object.conformities
            .select_related('organization', 'requirement__framework')
            .order_by('requirement__tree_id', 'requirement__lft', 'pk')
        )
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        attachments = self.request.FILES.getlist('attachments')
        for file in attachments:
            attachment = Attachment.get_or_create_for_upload(file)[0]
            self.object.attachment.add(attachment)
        return response


class ControlExportView(LoginRequiredMixin, FilteredExportMixin, View):
    """Export periodic Control and Indicator source objects."""

    resource_class = PeriodicControlResource
    filename = "periodic-controls"

    def get_export_queryset(self, request):
        return _periodic_sources()

    def get_queryset_for_export(self, request):
        items = self.get_export_queryset(request)
        if request.GET.get("scope") != "selection":
            return items

        data = request.GET.copy()
        for key in ("format", "scope", "page", "sort"):
            data.pop(key, None)
        return PeriodicControlFilter(
            data=data,
            queryset=items,
            request=request,
        ).qs



#
# Indicator
#


class IndicatorCreateView(
    LoginRequiredMixin,
    ConformityTargetedSourceCreateMixin,
    SaveStayMixin,
    CreateView,
):
    stay_url_name = "conformity:indicator_form"
    model = Indicator
    form_class = IndicatorForm


class IndicatorDetailView(LoginRequiredMixin, DetailView):
    model = Indicator
    context_object_name = 'indicator'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        indicator = self.get_object()

        context['indicator_point_list'] = IndicatorPoint.objects.filter(indicator=indicator).order_by('period_start_date')
        return context


class IndicatorIndexView(LoginRequiredMixin, FilterView):
    model = Indicator
    filterset_class = IndicatorFilter
    template_name = 'conformity/indicator_list.html'


class IndicatorUpdateView(LoginRequiredMixin, SaveStayMixin, UpdateView):
    stay_url_name = "conformity:indicator_form"
    model = Indicator
    form_class = IndicatorForm


class IndicatorPointUpdateView(AttachmentUploadViewMixin, LoginRequiredMixin, SaveStayMixin, UpdateView):
    stay_url_name = "conformity:indicatorpoint_form"
    model = IndicatorPoint
    form_class = IndicatorPointForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['evidence_conformities'] = (
            self.object.conformities
            .select_related('organization', 'requirement__framework')
            .order_by('requirement__tree_id', 'requirement__lft', 'pk')
        )
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        attachments = self.request.FILES.getlist('attachments')
        for file in attachments:
            attachment = Attachment.get_or_create_for_upload(file)[0]
            self.object.attachment.add(attachment)
        return response

class IndicatorExportView(LoginRequiredMixin, FilteredExportMixin, View):
    resource_class = IndicatorResource
    filterset_class = IndicatorFilter
    filename = "indicators"

    def get_export_queryset(self, request):
        return Indicator.objects.all()



#
# Attachment
#


class AttachmentIndexView(LoginRequiredMixin, RichTableMixin, FilterView):
    model = Attachment
    table_class = AttachmentTable
    filterset_class = AttachmentFilter
    template_name = "conformity/attachment_list.html"

    def get_queryset(self):
        return Attachment.objects.prefetch_related(
            "organizations",
            "frameworks",
            Prefetch(
                "audits",
                queryset=Audit.objects.select_related("organization"),
            ),
            "evidence",
        ).order_by("-create_date", "file", "pk")


class AttachmentDownloadView(LoginRequiredMixin, View):
    def get(self, pk):
        attachment = get_object_or_404(Attachment, id=pk)

        file_path = attachment.file.path
        file_name = os.path.basename(file_path)

        response = HttpResponse(open(file_path, 'rb'), content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{file_name}"'
        return response


class AttachmentChecksumView(LoginRequiredMixin, View):
    def post(self, request, pk):
        attachment = get_object_or_404(Attachment, id=pk)
        attachment.calculate_checksum_and_merge()
        return redirect('conformity:attachment_index')


class AttachmentUnlinkView(LoginRequiredMixin, View):
    """Remove an attachment from one allowed owner and clean up orphans."""

    owner_models = {
        "framework": (Framework, "conformity:framework_detail"),
        "organization": (Organization, "conformity:organization_form"),
        "audit": (Audit, "conformity:audit_form"),
        "controlpoint": (ControlPoint, "conformity:controlpoint_form"),
        "indicatorpoint": (IndicatorPoint, "conformity:indicatorpoint_form"),
        "evidence": (Evidence, "conformity:evidence_form"),
    }

    def post(self, request, owner_type, owner_pk, attachment_pk):
        owner_config = self.owner_models.get(owner_type)
        if owner_config is None:
            raise Http404("Unsupported attachment owner.")

        owner_model, return_route = owner_config
        owner = get_object_or_404(owner_model, pk=owner_pk)
        attachment_manager = (
            owner.attachments
            if isinstance(owner, Evidence)
            else owner.attachment
        )
        attachment = get_object_or_404(
            attachment_manager.all(),
            pk=attachment_pk,
        )
        orphan_deleted = unlink_attachment(owner, attachment)

        if orphan_deleted:
            messages.success(request, "Attachment removed and orphaned document deleted.")
        else:
            messages.success(request, "Attachment removed from this object.")

        return redirect(return_route, owner.pk)




#
# AuditLog
#


class AuditLogDetailView(LoginRequiredMixin, RichTableMixin, FilterView):
    model = LogEntry
    table_class = AuditLogTable
    template_name = 'auditlog/logentry_list.html'
    filterset_class = AuditLogFilter

    def get_queryset(self, **kwargs):
        return LogEntry.objects.all().order_by('-timestamp', '-pk')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        table = context.get("table")
        rows = table.page.object_list if table is not None and getattr(table, "page", None) else ()
        for row in rows:
            logentry = row.record
            changes = logentry.changes_dict
            m2m_fields = {
                field_name: values
                for field_name, values in changes.items()
                if isinstance(values, dict) and values.get('type') == 'm2m'
            }
            logentry.m2m_changes = [
                {
                    'field': field_name,
                    'operation': values['operation'],
                    'objects': values['objects'],
                }
                for field_name, values in m2m_fields.items()
            ]
            standard_changes = {
                field_name: values
                for field_name, values in changes.items()
                if field_name not in m2m_fields
            }
            if standard_changes == changes:
                logentry.standard_changes = logentry.changes_display_dict
            else:
                logentry.standard_changes = standard_changes
        return context



class FrameworkExportView(LoginRequiredMixin, FilteredExportMixin, View):
    resource_class = FrameworkResource
    filterset_class = FrameworkFilter
    filename = "frameworks"

    def get_export_queryset(self, request):
        return Framework.objects.all()


class OrganizationExportView(LoginRequiredMixin, FilteredExportMixin, View):
    resource_class = OrganizationResource
    filterset_class = OrganizationFilter
    filename = "organizations"

    def get_export_queryset(self, request):
        return Organization.objects.all()


class ConformityIndexExportView(LoginRequiredMixin, FilteredExportMixin, View):
    resource_class = ConformityResource
    filterset_class = ConformityFilter
    filename = "conformities"

    def get_export_queryset(self, request):
        return Conformity.objects.all()

    def get_selection_queryset(self, request):
        return Conformity.objects.with_related().roots()


class ControlPointExportView(LoginRequiredMixin, FilteredExportMixin, View):
    resource_class = ControlPointResource
    filterset_class = ControlPointFilter
    filename = "controlpoints"

    def get_export_queryset(self, request):
        return ControlPoint.objects.all()


class AttachmentExportView(LoginRequiredMixin, FilteredExportMixin, View):
    resource_class = AttachmentResource
    filterset_class = AttachmentFilter
    filename = "attachments"

    def get_export_queryset(self, request):
        return Attachment.objects.all()


class AuditLogExportView(LoginRequiredMixin, FilteredExportMixin, View):
    resource_class = AuditLogResource
    filterset_class = AuditLogFilter
    filename = "audit-log"

    def get_export_queryset(self, request):
        return LogEntry.objects.all().order_by("-timestamp")
