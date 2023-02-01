"""
View of the Conformity Module
"""
from django.views.generic import DetailView, ListView
from django.views.generic.edit import UpdateView, CreateView, DeleteView
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .forms import *


#
# Home
#
@login_required
def home(request):
    """View function for home page"""
    organization_list = Organization.objects.all()
    policy_list = Policy.objects.all()
    conformity_list = Conformity.objects.filter(measure__level=0)
    audit_list = Audit.objects.all()

    context = {
        'organization_list': organization_list,
        'policy_list': policy_list,
        'conformity_list': conformity_list,
        'audit_list': audit_list,
    }

    return render(request, 'home.html', context=context)


#
# Audit
#
class AuditIndexView(LoginRequiredMixin, ListView):
    model = Audit
    ordering = ['start_date']


class AuditDetailView(LoginRequiredMixin, DetailView):
    model = Audit


class AuditUpdateView(UpdateView):
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


class FindingUpdateView(UpdateView):
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
