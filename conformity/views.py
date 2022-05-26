'''
View of the Conformity Module
'''
from django.views import generic
from django.views.generic.edit import UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from .forms import *


#
# Organizations
#
class OrganizationIndexView(LoginRequiredMixin, generic.ListView):
    model = Organization
    ordering = ['name']


class OrganizationDetailView(LoginRequiredMixin, generic.ListView):
    model = Conformity
    template = "conformity/template/conformity/conformity_list.html"

    def get_queryset(self, **kwargs):
        return Conformity.objects.filter(organization__id=self.kwargs['pk'])


#
# Policy
#
class PolicyIndexView(LoginRequiredMixin, generic.ListView):
    model = Policy


class PolicyDetailView(LoginRequiredMixin, generic.DetailView):
    model = Policy


#
# Conformity
#
class ConformityIndexView(LoginRequiredMixin, generic.ListView):
    model = Conformity

    def get_queryset(self, **kwargs):
        return Conformity.objects.filter(measure__level=0).order_by('measure__order')


class ConformityOrgPolIndexView(LoginRequiredMixin, generic.ListView):
    model = Conformity
    template_name = 'conformity/conformity_orgpol_list.html'

    def get_queryset(self, **kwargs):
        return Conformity.objects.filter(organization__id=self.kwargs['org']) \
            .filter(measure__policy__id=self.kwargs['pol']) \
            .filter(measure__level=0) \
            .order_by('measure__order')


class ConformityUpdateView(UpdateView):
    model = Conformity
    form_class = ConformityForm

    def form_valid(self, form):
        form.instance.set_status(form.cleaned_data['status'])
        return super().form_valid(form)


class OrganizationView(UpdateView):
    model = Organization
    form_class = OrganizationForm
