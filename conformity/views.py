from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import generic
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.edit import CreateView, UpdateView
from django.urls import reverse, reverse_lazy

from .models import *
from .forms import *

##
## Organizations 
##
class OrganizationIndexView(LoginRequiredMixin, generic.ListView):
    model = Organization
    ordering = ['name']

class OrganizationDetailView(LoginRequiredMixin, generic.ListView):
    model = Conformity
    template = "conformity/template/conformity/conformity_list.html"

    def get_queryset(self,**kwargs):
        return Conformity.objects.filter(organization__id=self.kwargs['pk'])

##
## Policy 
##
class PolicyIndexView(LoginRequiredMixin, generic.ListView):
    model = Policy

class PolicyDetailView(LoginRequiredMixin, generic.DetailView):
    model = Policy

##
## Conformity
##
class ConformityIndexView(LoginRequiredMixin, generic.ListView):
    model = Conformity

    def get_queryset(self, **kwargs):
        return Conformity.objects.filter(mesure__level=0).order_by('mesure__order')

class ConformityOrgPolIndexView(LoginRequiredMixin, generic.ListView):
    model = Conformity
    template_name = 'conformity/conformity_orgpol_list.html'

    def get_queryset(self, **kwargs):
        return Conformity.objects.filter(organization__id=self.kwargs['org']).filter(mesure__policy__id=self.kwargs['pol']).filter(mesure__level=0).order_by('mesure__order')

#def conformityUpdate(request):
#    data = request.POST.items()
#    for conformity in data:
#        if not conformity[0] == 'csrfmiddlewaretoken' and not conformity[0] == 'path':
#            c = Conformity.objects.get(id=conformity[0])
#            c.status_set(conformity[1])
#
#      return HttpResponseRedirect(request.POST['path'])

class ConformityUpdateView(UpdateView):
    model = Conformity
    form_class = ConformityForm

    def form_valid(self, form):
        form.instance.set_status(form.cleaned_data['status'])
        return super().form_valid(form)

class OrganizationView(UpdateView):
    model = Organization
    form_class = OrganizationForm

#    def form_valid(selfself, form):
#        form.instance.add_policy(Policy.objects.get('form.cleaned_data.applicable_policies'))