'''
Customize Django Admin Site to manage my Models instances
'''

from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from .models import Organization, Policy, Measure, Conformity

# Organization


class OrganizationResources(resources.ModelResource):
    class Meta:
        model = Organization


class OrganizationAdmin(ImportExportModelAdmin):
    ressource_class = Organization


admin.site.register(Organization, OrganizationAdmin)


# Policy


class PolicyResources(resources.ModelResource):
    class Meta:
        model = Policy


class PolicyAdmin(ImportExportModelAdmin):
    ressource_class = Policy


admin.site.register(Policy, PolicyAdmin)


# Measure

class MeasureResources(resources.ModelResource):
    class Meta:
        model = Measure


class MeasureAdmin(ImportExportModelAdmin):
    ressource_class = Measure


admin.site.register(Measure, MeasureAdmin)


# Conformity


class ConformityResources(resources.ModelResource):
    class Meta:
        model = Conformity


class ConformityAdmin(ImportExportModelAdmin):
    ressource_class = Conformity


admin.site.register(Conformity, ConformityAdmin)
