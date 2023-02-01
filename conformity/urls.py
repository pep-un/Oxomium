'''
Conformity module URL router
'''
from django.urls import path

from . import views

app_name = 'conformity'
urlpatterns = [
    path('', views.home, name='home'),

    path('audit/', views.AuditIndexView.as_view(), name='audit_index'),
    path('audit/<int:pk>', views.AuditDetailView.as_view(), name='audit_detail'),
    path('audit/create', views.AuditCreateView.as_view(), name='audit_create'),
    path('audit/update/<int:pk>', views.AuditUpdateView.as_view(), name='audit_form'),

    path('conformity/', views.ConformityIndexView.as_view(), name='conformity_index'),
    path('conformity/org/<int:org>/pol/<int:pol>/', views.ConformityOrgPolIndexView.as_view(),
         name='conformity_orgpol_index'),
    path('conformity/update/<int:pk>', views.ConformityUpdateView.as_view(), name='conformity_form'),

    path('finding/create', views.FindingCreateView.as_view(), name='finding_create'),
    path('finding/<int:pk>', views.FindingDetailView.as_view(), name='finding_detail'),
    path('finding/update/<int:pk>', views.FindingUpdateView.as_view(), name='finding_edit'),

    path('organization/', views.OrganizationIndexView.as_view(), name='organization_index'),
    path('organization/<int:pk>', views.OrganizationDetailView.as_view(), name='organization_detail'),
    path('organization/create', views.OrganizationCreateView.as_view(), name='organization_create'),
    path('organization/update/<int:pk>', views.OrganizationUpdateView.as_view(), name='organization_form'),

    path('policy/', views.PolicyIndexView.as_view(), name='policy_index'),
    path('policy/<int:pk>/', views.PolicyDetailView.as_view(), name='policy_detail'),

]
