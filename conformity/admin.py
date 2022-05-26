from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from .models import *

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

class MesureResources(resources.ModelResource):
    class Meta:
        model = Mesure


class MeasureAdmin(ImportExportModelAdmin):
    ressource_class = Mesure


admin.site.register(Mesure, MeasureAdmin)


# Conformity


class ConformityResources(resources.ModelResource):
    class Meta:
        model = Conformity


class ConformityAdmin(ImportExportModelAdmin):
    ressource_class = Conformity


admin.site.register(Conformity, ConformityAdmin)