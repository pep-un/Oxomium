"""
View of the Conformity Module
"""
from urllib import request

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView, ListView, TemplateView
from django.views.generic.edit import UpdateView, CreateView, DeleteView
from django_filters.views import FilterView
from auditlog.models import LogEntry
from mptt.templatetags.mptt_tags import cache_tree_children

from .filterset import ActionFilter, ControlFilter, ControlPointFilter
from .forms import ConformityForm, AuditForm, FindingForm, ActionForm, OrganizationForm, ControlForm, ControlPointForm
from .models import Organization, Framework, Conformity, Audit, Action, Finding, Control, ControlPoint, Attachment, Requirement

from django.views import View
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
import os

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
        context['conformity_list'] = Conformity.objects.filter(requirement__level=0)
        context['audit_list'] = Audit.objects.all()
        context['action_list'] = Action.objects.all()
        context['my_action'] = Action.objects.filter(owner=user).filter(active=True).order_by('status')[:50]
        context['my_conformity'] = Conformity.objects.filter(responsible=user).order_by('status')[:50]
        context['cp_list'] = ControlPoint.objects.filter(status='TOBE').order_by('period_end_date')[:50]

        return context


#
# Audit
#
class AuditIndexView(LoginRequiredMixin, ListView):
    model = Audit


class AuditDetailView(LoginRequiredMixin, DetailView):
    model = Audit


class AuditUpdateView(LoginRequiredMixin, UpdateView):
    model = Audit
    form_class = AuditForm

    def form_valid(self, form):
        response = super().form_valid(form)
        attachments = self.request.FILES.getlist('attachments')
        for file in attachments:
            attachment = Attachment.objects.create(file=file)
            self.object.attachment.add(attachment)
        return response



class AuditCreateView(LoginRequiredMixin, CreateView):
    model = Audit
    form_class = AuditForm

    def form_valid(self, form):
        response = super().form_valid(form)
        attachments = self.request.FILES.getlist('attachments')
        for file in attachments:
            attachment = Attachment.objects.create(file=file)
            self.object.attachment.add(attachment)
        return response


#
# Findings
#
class FindingIndexView(LoginRequiredMixin, ListView):
    model = Finding

    def get_queryset(self, **kwargs):
        return Finding.objects.filter(severity__in=["CRT","MAJ","MIN", "OBS"]).filter(archived=False)


class FindingCreateView(LoginRequiredMixin, CreateView):
    model = Finding
    form_class = FindingForm


class FindingDetailView(LoginRequiredMixin, DetailView):
    model = Finding


class FindingUpdateView(LoginRequiredMixin, UpdateView):
    model = Finding
    form_class = FindingForm

#
# Organizations
#


class OrganizationIndexView(LoginRequiredMixin, ListView):
    model = Organization


class OrganizationDetailView(LoginRequiredMixin, DetailView):
    model = Organization


class OrganizationUpdateView(LoginRequiredMixin, UpdateView):
    model = Organization
    form_class = OrganizationForm

    def form_valid(self, form):
        response = super().form_valid(form)
        attachments = self.request.FILES.getlist('attachments')
        for file in attachments:
            attachment = Attachment.objects.create(file=file)
            self.object.attachment.add(attachment)
        return response


class OrganizationCreateView(LoginRequiredMixin, CreateView):
    model = Organization
    form_class = OrganizationForm

    def form_valid(self, form):
        response = super().form_valid(form)
        attachments = self.request.FILES.getlist('attachments')
        for file in attachments:
            attachment = Attachment.objects.create(file=file)
            self.object.attachment.add(attachment)
        return response

#
# Framework
#


class FrameworkIndexView(LoginRequiredMixin, ListView):
    model = Framework


class FrameworkDetailView(LoginRequiredMixin, DetailView):
    model = Framework

    # Not used yet, to be fixed (issue with recursetree)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = Requirement.objects.filter(framework=self.object).order_by('tree_id', 'lft')
        context['requirement_list'] = cache_tree_children(qs)
        return context


#
# Conformity
#
class ConformityIndexView(LoginRequiredMixin, ListView):
    model = Conformity

    def get_queryset(self, **kwargs):
        return Conformity.objects.filter(requirement__level=0)


class ConformityDetailIndexView(LoginRequiredMixin, ListView):
    model = Conformity
    template_name = 'conformity/conformity_detail_list.html'

    def get_queryset(self, **kwargs):
        return Conformity.objects.filter(organization__id=self.kwargs['org']) \
            .filter(requirement__framework__id=self.kwargs['pol']) \
            .filter(requirement__level=0) \
            .order_by('requirement__tree_id','requirement__lft')


class ConformityUpdateView(LoginRequiredMixin, UpdateView):
    model = Conformity
    form_class = ConformityForm

    def form_valid(self, form):
        # starting point of the set_status and status tree update logic
        self.object = form.save()

        # Object is save, we juste have to update the tree, when needed.
        if "applicable" in form.changed_data:
            self.object.update_applicable()
        if "responsible" in form.changed_data:
            self.object.update_responsible()
        if "status" in form.changed_data:
            self.object.update_status()

        # Manage Save&Next submitting to allow easy filling of the conformity
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

        return super().form_valid(form)


#
# Action
#


class ActionCreateView(LoginRequiredMixin, CreateView):
    model = Action
    form_class = ActionForm


class ActionIndexView(LoginRequiredMixin, FilterView):
    model = Action
    filterset_class = ActionFilter
    template_name = "conformity/action_list.html"


class ActionUpdateView(LoginRequiredMixin, UpdateView):
    model = Action
    form_class = ActionForm


#
# Control
#


class ControlCreateView(LoginRequiredMixin, CreateView):
    model = Control
    form_class = ControlForm


class ControlIndexView(LoginRequiredMixin, FilterView):
    model = Control
    filterset_class = ControlFilter
    template_name = 'conformity/control_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['controlpoint_list'] = ControlPoint.objects.all()
        context['c1st'] = Control.objects.filter(level="1").count()
        context['c2nd'] = Control.objects.filter(level="2").count()
        context['cp0x'] = ControlPoint.objects.filter(status="TOBE").count()
        context['cp1x'] = ControlPoint.objects.filter(control__frequency="1").filter(status="TOBE").count()
        context['cp2x'] = ControlPoint.objects.filter(control__frequency="2").filter(status="TOBE").count()
        context['cp4x'] = ControlPoint.objects.filter(control__frequency="4").filter(status="TOBE").count()
        context['cp6x'] = ControlPoint.objects.filter(control__frequency="6").filter(status="TOBE").count()
        context['cp12x'] = ControlPoint.objects.filter(control__frequency="12").filter(status="TOBE").count()

        return context


class ControlUpdateView(LoginRequiredMixin, UpdateView):
    model = Control
    form_class = ControlForm


class ControlDetailView(LoginRequiredMixin, DetailView):
    model = Control
    template_name = 'conformity/control_detail_list.html'


class ControlPointIndexView(LoginRequiredMixin, FilterView):
    model = ControlPoint
    filterset_class = ControlPointFilter
    template_name = 'conformity/controlpoint_list.html'


class ControlPointUpdateView(LoginRequiredMixin, UpdateView):
    model = ControlPoint
    form_class = ControlPointForm
    #success_url = reverse_lazy('conformity:controlpoint_list')  # Adjust the success URL as needed

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        attachments = self.request.FILES.getlist('attachments')
        for file in attachments:
            attachment = Attachment.objects.create(file=file)
            self.object.attachment.add(attachment)
        return response


#
# Attachment
#


class AttachmentIndexView(LoginRequiredMixin, ListView):
    model = Attachment


class AttachmentDownloadView(View):
    def get(self, request, pk):
        attachment = get_object_or_404(Attachment, id=pk)

        file_path = attachment.file.path
        file_name = os.path.basename(file_path)

        response = HttpResponse(open(file_path, 'rb'), content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{file_name}"'
        return response


#
# AuditLog
#


class AuditLogDetailView(LoginRequiredMixin, ListView):
    model = LogEntry
    paginate_by = 20

    def get_queryset(self, **kwargs):
        return LogEntry.objects.all().order_by('-timestamp')
