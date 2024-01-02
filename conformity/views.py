"""
View of the Conformity Module
"""
from urllib import request

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView, ListView, TemplateView
from django.views.generic.edit import UpdateView, CreateView, DeleteView
from django_filters.views import FilterView
from auditlog.models import LogEntry

from .filterset import ActionFilter, ControlFilter, ControlPointFilter
from .forms import ConformityForm, AuditForm, FindingForm, ActionForm, OrganizationForm, ControlForm, ControlPointForm
from .models import Organization, Policy, Conformity, Audit, Action, Finding, Control, ControlPoint


#
# Home
#


class HomeView(LoginRequiredMixin, TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context['organization_list'] = Organization.objects.all()
        context['policy_list'] = Policy.objects.all()
        context['conformity_list'] = Conformity.objects.filter(measure__level=0)
        context['audit_list'] = Audit.objects.all()
        context['action_list'] = Action.objects.all()
        context['my_action'] = Action.objects.filter(owner=user).filter(active=True).order_by('status')[:50]
        context['my_conformity'] = Conformity.objects.filter(responsible=user).order_by('status')[:50]

        return context


#
# Audit
#
class AuditIndexView(LoginRequiredMixin, ListView):
    model = Audit
    ordering = ['-start_date']


class AuditDetailView(LoginRequiredMixin, DetailView):
    model = Audit


class AuditUpdateView(LoginRequiredMixin, UpdateView):
    model = Audit
    form_class = AuditForm


class AuditCreateView(LoginRequiredMixin, CreateView):
    model = Audit
    form_class = AuditForm


#
# Findings
#


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
    ordering = ['name']


class OrganizationDetailView(LoginRequiredMixin, ListView):
    model = Conformity
    template = "conformity/template/conformity/conformity_list.html"

    def get_queryset(self, **kwargs):
        return Conformity.objects.filter(organization__id=self.kwargs['pk'])


class OrganizationUpdateView(LoginRequiredMixin, UpdateView):
    model = Organization
    form_class = OrganizationForm


class OrganizationCreateView(LoginRequiredMixin, CreateView):
    model = Organization
    form_class = OrganizationForm

#
# Policy
#


class PolicyIndexView(LoginRequiredMixin, ListView):
    model = Policy


class PolicyDetailView(LoginRequiredMixin, DetailView):
    model = Policy


#
# Conformity
#
class ConformityIndexView(LoginRequiredMixin, ListView):
    model = Conformity

    def get_queryset(self, **kwargs):
        return Conformity.objects.filter(measure__level=0)


class ConformityOrgPolIndexView(LoginRequiredMixin, ListView):
    model = Conformity
    template_name = 'conformity/conformity_orgpol_list.html'

    def get_queryset(self, **kwargs):
        return Conformity.objects.filter(organization__id=self.kwargs['org']) \
            .filter(measure__policy__id=self.kwargs['pol']) \
            .filter(measure__level=0) \
            .order_by('measure__order')


class ConformityUpdateView(LoginRequiredMixin, UpdateView):
    model = Conformity
    form_class = ConformityForm

    def form_valid(self, form):
        form.instance.set_status(form.cleaned_data['status'])
        return super().form_valid(form)


#
# Action
#


class ActionCreateView(LoginRequiredMixin, CreateView):
    model = Action
    form_class = ActionForm


class ActionIndexView(LoginRequiredMixin, FilterView):
    model = Action
    ordering = ['status', '-update_date']
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


class ControlUpdateView(LoginRequiredMixin, UpdateView):
    model = Control
    form_class = ControlForm


class ControlPointIndexView(LoginRequiredMixin, FilterView):
    model = ControlPoint
    filterset_class = ControlPointFilter
    template_name = 'conformity/controlpoint_list.html'


class ControlPointUpdateView(LoginRequiredMixin, UpdateView):
    model = ControlPoint
    form_class = ControlPointForm

#
# AuditLog
#


class AuditLogDetailView(LoginRequiredMixin, ListView):
    model = LogEntry

    def get_queryset(self, **kwargs):
        return LogEntry.objects.all().order_by('-timestamp')
