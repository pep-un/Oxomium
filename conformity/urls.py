"""
Conformity module URL router
"""
from django.urls import path
from django.views.generic import TemplateView

from . import views

app_name = 'conformity'
urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),

    path('audit/', views.AuditIndexView.as_view(), name='audit_index'),
    path('audit/<int:pk>', views.AuditDetailView.as_view(), name='audit_detail'),
    path('audit/create', views.AuditCreateView.as_view(), name='audit_create'),
    path('audit/update/<int:pk>', views.AuditUpdateView.as_view(), name='audit_form'),

    path('conformity/', views.ConformityIndexView.as_view(), name='conformity_index'),
    path('conformity/organization/<int:org>/framework/<int:pol>/', views.ConformityDetailIndexView.as_view(),
         name='conformity_detail_index'),
    path('conformity/update/<int:pk>', views.ConformityUpdateView.as_view(), name='conformity_form'),

    path('finding/create', views.FindingCreateView.as_view(), name='finding_create'),
    path('finding/<int:pk>', views.FindingDetailView.as_view(), name='finding_detail'),
    path('finding/update/<int:pk>', views.FindingUpdateView.as_view(), name='finding_edit'),

    path('organization/', views.OrganizationIndexView.as_view(), name='organization_index'),
    path('organization/<int:pk>', views.OrganizationDetailView.as_view(), name='organization_detail'),
    path('organization/create', views.OrganizationCreateView.as_view(), name='organization_create'),
    path('organization/update/<int:pk>', views.OrganizationUpdateView.as_view(), name='organization_form'),

    path('framework/', views.FrameworkIndexView.as_view(), name='framework_index'),
    path('framework/<int:pk>/', views.FrameworkDetailView.as_view(), name='framework_detail'),

    path('action/', views.ActionIndexView.as_view(), name='action_index'),
    path('action/create', views.ActionCreateView.as_view(), name='action_create'),
    path('action/update/<int:pk>', views.ActionUpdateView.as_view(), name='action_form'),

    path('control/', views.ControlIndexView.as_view(), name='control_index'),
    path('control/create', views.ControlCreateView.as_view(), name='control_create'),
    path('control/update/<int:pk>', views.ControlUpdateView.as_view(), name='control_form'),
    path('control/<int:pk>', views.ControlDetailView.as_view(), name='control_detail'),

    path('controlpoint/', views.ControlPointIndexView.as_view(), name='controlpoint_index'),
    path('controlpoint/update/<int:pk>', views.ControlPointUpdateView.as_view(), name='controlpoint_form'),

    path('help/', TemplateView.as_view(template_name='help.html'), name='help'),
    path('auditlog/', views.AuditLogDetailView.as_view(), name='auditlog_index'),
]
