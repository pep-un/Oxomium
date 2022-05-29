'''
Conformity module URL router
'''
from django.urls import path

from . import views

app_name = 'conformity'
urlpatterns = [
    path('', views.home, name='home'),
    path('organization/', views.OrganizationIndexView.as_view(), name='organization_index'),
    path('organization/<int:pk>', views.OrganizationDetailView.as_view(), name='organization_detail'),
    path('policy/', views.PolicyIndexView.as_view(), name='policy_index'),
    path('policy/<int:pk>/', views.PolicyDetailView.as_view(), name='policy_detail'),
    path('conformity/', views.ConformityIndexView.as_view(), name='conformity_index'),
    path('conformity/org/<int:org>/pol/<int:pol>/', views.ConformityOrgPolIndexView.as_view(), name='conformity_orgpol_index'),
    path('conformity/update/<int:pk>', views.ConformityUpdateView.as_view(), name='conformity_form' ),
    path('organization/update/<int:pk>', views.OrganizationView.as_view(), name='organization_form'),
]
