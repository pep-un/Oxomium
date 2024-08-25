[1mdiff --git a/conformity/admin.py b/conformity/admin.py[m
[1mindex 8196b68..27dad88 100644[m
[1m--- a/conformity/admin.py[m
[1m+++ b/conformity/admin.py[m
[36m@@ -5,7 +5,7 @@[m [mCustomize Django Admin Site to manage my Models instances[m
 from django.contrib import admin[m
 from import_export import resources[m
 from import_export.admin import ImportExportModelAdmin[m
[31m-from .models import Organization, Policy, Measure, Conformity, Audit, Finding, Action, Control, ControlPoint[m
[32m+[m[32mfrom .models import Organization, Framework, Measure, Conformity, Audit, Finding, Action, Control, ControlPoint[m
 [m
 [m
 class OrganizationResources(resources.ModelResource):[m
[36m@@ -17,13 +17,13 @@[m [mclass OrganizationAdmin(ImportExportModelAdmin):[m
     ressource_class = Organization[m
 [m
 [m
[31m-class PolicyResources(resources.ModelResource):[m
[32m+[m[32mclass FrameworkResources(resources.ModelResource):[m
     class Meta:[m
[31m-        model = Policy[m
[32m+[m[32m        model = Framework[m
 [m
 [m
[31m-class PolicyAdmin(ImportExportModelAdmin):[m
[31m-    ressource_class = Policy[m
[32m+[m[32mclass FrameworkAdmin(ImportExportModelAdmin):[m
[32m+[m[32m    ressource_class = Framework[m
 [m
 [m
 class MeasureResources(resources.ModelResource):[m
[36m@@ -55,7 +55,7 @@[m [mclass ActionAdmin(ImportExportModelAdmin):[m
 [m
 [m
 # Registration[m
[31m-admin.site.register(Policy, PolicyAdmin)[m
[32m+[m[32madmin.site.register(Framework, FrameworkAdmin)[m
 admin.site.register(Measure, MeasureAdmin)[m
 admin.site.register(Conformity, ConformityAdmin)[m
 admin.site.register(Action, ActionAdmin)[m
[1mdiff --git a/conformity/migrations/0001_squashed_0014_mesure_is_parent.py b/conformity/migrations/0001_squashed_0014_mesure_is_parent.py[m
[1mindex f7c8759..ea1c41b 100644[m
[1m--- a/conformity/migrations/0001_squashed_0014_mesure_is_parent.py[m
[1m+++ b/conformity/migrations/0001_squashed_0014_mesure_is_parent.py[m
[36m@@ -47,7 +47,7 @@[m [mclass Migration(migrations.Migration):[m
                 ('name', models.CharField(max_length=256)),[m
                 ('administrative_id', models.CharField(blank=True, max_length=256)),[m
                 ('description', models.CharField(blank=True, max_length=256)),[m
[31m-                ('applicable_policies', models.ManyToManyField(blank=True, to='conformity.policy')),[m
[32m+[m[32m                ('applicable_frameworks', models.ManyToManyField(blank=True, to='conformity.policy')),[m
             ],[m
         ),[m
         migrations.CreateModel([m
[1mdiff --git a/conformity/migrations/0001_squashed_0029_alter_action_control_comment_and_more.py b/conformity/migrations/0001_squashed_0029_alter_action_control_comment_and_more.py[m
[1mindex 670c280..efe0eed 100644[m
[1m--- a/conformity/migrations/0001_squashed_0029_alter_action_control_comment_and_more.py[m
[1m+++ b/conformity/migrations/0001_squashed_0029_alter_action_control_comment_and_more.py[m
[36m@@ -40,7 +40,7 @@[m [mclass Migration(migrations.Migration):[m
                 ('name', models.CharField(max_length=256, unique=True)),[m
                 ('administrative_id', models.CharField(blank=True, max_length=256)),[m
                 ('description', models.TextField(blank=True, max_length=4096)),[m
[31m-                ('applicable_policies', models.ManyToManyField(blank=True, to='conformity.policy')),[m
[32m+[m[32m                ('applicable_frameworks', models.ManyToManyField(blank=True, to='conformity.policy')),[m
             ],[m
             options={[m
                 'ordering': ['name'],[m
[1mdiff --git a/conformity/migrations/0041_rename_policy_framework_alter_framework_options_and_more.py b/conformity/migrations/0041_rename_policy_framework_alter_framework_options_and_more.py[m
[1mindex 03d4015..067c37d 100644[m
[1m--- a/conformity/migrations/0041_rename_policy_framework_alter_framework_options_and_more.py[m
[1m+++ b/conformity/migrations/0041_rename_policy_framework_alter_framework_options_and_more.py[m
[36m@@ -23,4 +23,9 @@[m [mclass Migration(migrations.Migration):[m
             old_name='policy',[m
             new_name='framework',[m
         ),[m
[32m+[m[32m        migrations.RenameField([m
[32m+[m[32m            model_name='organization',[m
[32m+[m[32m            old_name='applicable_policies',[m
[32m+[m[32m            new_name='applicable_frameworks',[m
[32m+[m[32m        ),[m
     ][m
[1mdiff --git a/conformity/models.py b/conformity/models.py[m
[1mindex e255c84..7de3cb4 100644[m
[1m--- a/conformity/models.py[m
[1m+++ b/conformity/models.py[m
[36m@@ -1,6 +1,6 @@[m
 """[m
 Conformity module manage all the manual declarative aspect of conformity management.[m
[31m-It's Organized around Organization, Policy, Measure and Conformity classes.[m
[32m+[m[32mIt's Organized around Organization, Framework, Measure and Conformity classes.[m
 """[m
 from calendar import monthrange[m
 from statistics import mean[m
[36m@@ -20,19 +20,19 @@[m [mfrom auditlog.context import set_actor[m
 User = get_user_model()[m
 [m
 [m
[31m-class PolicyManager(models.Manager):[m
[32m+[m[32mclass FrameworkManager(models.Manager):[m
     def get_by_natural_key(self, name):[m
         return self.get(name=name)[m
 [m
 [m
[31m-class Policy(models.Model):[m
[32m+[m[32mclass Framework(models.Model):[m
     """[m
[31m-    Policy class represent the conformity policy you will apply on Organization.[m
[31m-    A Policy is simply a collections of Measure with publication parameter.[m
[32m+[m[32m    Framework class represent the conformity framework you will apply on Organization.[m
[32m+[m[32m    A Framework is simply a collections of Measure with publication parameter.[m
     """[m
 [m
     class Type(models.TextChoices):[m
[31m-        """ List of the Type of policy """[m
[32m+[m[32m        """ List of the Type of framework """[m
         INTERNATIONAL = 'INT', _('International Standard')[m
         NATIONAL = 'NAT', _('National Standard')[m
         TECHNICAL = 'TECH', _('Technical Standard')[m
[36m@@ -40,7 +40,7 @@[m [mclass Policy(models.Model):[m
         POLICY = 'POL', _('Internal Policy')[m
         OTHER = 'OTHER', _('Other')[m
 [m
[31m-    objects = PolicyManager()[m
[32m+[m[32m    objects = FrameworkManager()[m
     name = models.CharField(max_length=256, unique=True)[m
     version = models.IntegerField(default=0)[m
     publish_by = models.CharField(max_length=256)[m
[36m@@ -62,35 +62,35 @@[m [mclass Policy(models.Model):[m
         return (self.name)[m
 [m
     def get_type(self):[m
[31m-        """return the readable version of the Policy Type"""[m
[32m+[m[32m        """return the readable version of the Framework Type"""[m
         return self.Type(self.type).label[m
 [m
     def get_measures(self):[m
[31m-        """return all Measure related to the Policy"""[m
[31m-        return Measure.objects.filter(policy=self.id)[m
[32m+[m[32m        """return all Measure related to the Framework"""[m
[32m+[m[32m        return Measure.objects.filter(framework=self.id)[m
 [m
     def get_measures_number(self):[m
[31m-        """return the number of leaf Measure related to the Policy"""[m
[31m-        return Measure.objects.filter(policy=self.id).filter(measure__is_parent=False).count()[m
[32m+[m[32m        """return the number of leaf Measure related to the Framework"""[m
[32m+[m[32m        return Measure.objects.filter(framework=self.id).filter(measure__is_parent=False).count()[m
 [m
     def get_root_measure(self):[m
[31m-        """return the root Measure of the Policy"""[m
[31m-        return Measure.objects.filter(policy=self.id).filter(level=0).order_by('order')[m
[32m+[m[32m        """return the root Measure of the Framework"""[m
[32m+[m[32m        return Measure.objects.filter(framework=self.id).filter(level=0).order_by('order')[m
 [m
     def get_first_measures(self):[m
[31m-        """return the Measure of the first hierarchical level of the Policy"""[m
[31m-        return Measure.objects.filter(policy=self.id).filter(level=1).order_by('order')[m
[32m+[m[32m        """return the Measure of the first hierarchical level of the Framework"""[m
[32m+[m[32m        return Measure.objects.filter(framework=self.id).filter(level=1).order_by('order')[m
 [m
 [m
 class Organization(models.Model):[m
     """[m
     Organization class is a representation of a company, a division of company, an administration...[m
[31m-    The Organization may answer to one or several Policy.[m
[32m+[m[32m    The Organization may answer to one or several Framework.[m
     """[m
     name = models.CharField(max_length=256, unique=True)[m
     administrative_id = models.CharField(max_length=256, blank=True)[m
     description = models.TextField(max_length=4096, blank=True)[m
[31m-    applicable_policies = models.ManyToManyField(Policy, blank=True)[m
[32m+[m[32m    applicable_frameworks = models.ManyToManyField(Framework, blank=True)[m
 [m
     class Meta:[m
         ordering = ['name'][m
[36m@@ -106,21 +106,21 @@[m [mclass Organization(models.Model):[m
         """return the absolute URL for Forms, could probably do better"""[m
         return reverse('conformity:organization_index')[m
 [m
[31m-    def get_policies(self):[m
[31m-        """return all Policy applicable to the Organization"""[m
[31m-        return self.applicable_policies.all()[m
[32m+[m[32m    def get_frameworks(self):[m
[32m+[m[32m        """return all Framework applicable to the Organization"""[m
[32m+[m[32m        return self.applicable_frameworks.all()[m
 [m
     def remove_conformity(self, pid):[m
         """Cascade deletion of conformity"""[m
         with set_actor('system'):[m
[31m-            measure_set = Measure.objects.filter(policy=pid)[m
[32m+[m[32m            measure_set = Measure.objects.filter(framework=pid)[m
             for measure in measure_set:[m
                 Conformity.objects.filter(measure=measure.id).filter(organization=self.id).delete()[m
 [m
     def add_conformity(self, pid):[m
         """Automatic creation of conformity"""[m
         with set_actor('system'):[m
[31m-            measure_set = Measure.objects.filter(policy=pid)[m
[32m+[m[32m            measure_set = Measure.objects.filter(framework=pid)[m
             for measure in measure_set:[m
                 conformity = Conformity(organization=self, measure=measure)[m
                 conformity.save()[m
[36m@@ -134,7 +134,7 @@[m [mclass MeasureManager(models.Manager):[m
 class Measure(models.Model):[m
     """[m
     A Measure is a precise requirement.[m
[31m-    Measure can be hierarchical in order to form a collection of Measure, aka Policy.[m
[32m+[m[32m    Measure can be hierarchical in order to form a collection of Measure, aka Framework.[m
     A Measure is not representing the conformity level, see Conformity class.[m
     """[m
     objects = MeasureManager()[m
[36m@@ -142,7 +142,7 @@[m [mclass Measure(models.Model):[m
     name = models.CharField(max_length=50, blank=True, unique=True)[m
     level = models.IntegerField(default=0)[m
     order = models.IntegerField(default=1)[m
[31m-    policy = models.ForeignKey(Policy, on_delete=models.CASCADE)[m
[32m+[m[32m    framework = models.ForeignKey(Framework, on_delete=models.CASCADE)[m
     parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)[m
     title = models.CharField(max_length=256, blank=True)[m
     description = models.TextField(blank=True)[m
[36m@@ -157,7 +157,7 @@[m [mclass Measure(models.Model):[m
     def natural_key(self):[m
         return (self.name)[m
 [m
[31m-    natural_key.dependencies = ['conformity.policy'][m
[32m+[m[32m    natural_key.dependencies = ['conformity.framework'][m
 [m
     def get_children(self):[m
         """Return all children of the measure"""[m
[36m@@ -188,12 +188,12 @@[m [mclass Conformity(models.Model):[m
     def natural_key(self):[m
         return self.organization, self.measure[m
 [m
[31m-    natural_key.dependencies = ['conformity.policy', 'conformity.measure', 'conformity.organization'][m
[32m+[m[32m    natural_key.dependencies = ['conformity.framework', 'conformity.measure', 'conformity.organization'][m
 [m
     def get_absolute_url(self):[m
         """Return the absolute URL of the class for Form, probably not the best way to do it"""[m
         return reverse('conformity:conformity_orgpol_index',[m
[31m-                       kwargs={'org': self.organization.id, 'pol': self.measure.policy.id})[m
[32m+[m[32m                       kwargs={'org': self.organization.id, 'pol': self.measure.framework.id})[m
 [m
     def get_children(self):[m
         """Return all children Conformity based on Measure hierarchy"""[m
[36m@@ -259,8 +259,8 @@[m [mdef post_init_callback(instance, **kwargs):[m
         instance.name = instance.code[m
 [m
 [m
[31m-@receiver(m2m_changed, sender=Organization.applicable_policies.through)[m
[31m-def change_policy(instance, action, pk_set, *args, **kwargs):[m
[32m+[m[32m@receiver(m2m_changed, sender=Organization.applicable_frameworks.through)[m
[32m+[m[32mdef change_framework(instance, action, pk_set, *args, **kwargs):[m
     if action == "post_add":[m
         for pk in pk_set:[m
             instance.add_conformity(pk)[m
[36m@@ -288,7 +288,7 @@[m [mclass Audit(models.Model):[m
     description = models.TextField(max_length=4096, blank=True)[m
     conclusion = models.TextField(max_length=4096, blank=True)[m
     auditor = models.CharField(max_length=256)[m
[31m-    audited_policies = models.ManyToManyField(Policy, blank=True)[m
[32m+[m[32m    audited_policies = models.ManyToManyField(Framework, blank=True)[m
     start_date = models.DateField(null=True, blank=True)[m
     end_date = models.DateField(null=True, blank=True)[m
     report_date = models.DateField(null=True, blank=True)[m
[36m@@ -320,7 +320,7 @@[m [mclass Audit(models.Model):[m
         return reverse('conformity:audit_index')[m
 [m
     def get_policies(self):[m
[31m-        """return all Policy within the Audit scope"""[m
[32m+[m[32m        """return all Framework within the Audit scope"""[m
         return self.audited_policies.all()[m
 [m
     def get_type(self):[m
[1mdiff --git a/conformity/templates/conformity/audit_detail.html b/conformity/templates/conformity/audit_detail.html[m
[1mindex 5d1bd8c..ba97035 100644[m
[1m--- a/conformity/templates/conformity/audit_detail.html[m
[1m+++ b/conformity/templates/conformity/audit_detail.html[m
[36m@@ -9,7 +9,7 @@[m
     <p>{{ audit.get_type }} realized by {{ audit.auditor }} from {{ audit.start_date }} to {{ audit.end_date }}.</p>[m
     <p>The following policies were within the audit scope : </p>[m
     <ul>[m
[31m-        {% for policy in audit.get_policies %}[m
[32m+[m[32m        {% for policy in audit.get_frameworks %}[m
             <li>{{ policy }}</li>[m
         {% empty %}[m
             <li>No policy within the audit scope.</li>[m
[1mdiff --git a/conformity/templates/conformity/finding_detail.html b/conformity/templates/conformity/finding_detail.html[m
[1mindex c3e46ff..a75f81e 100644[m
[1m--- a/conformity/templates/conformity/finding_detail.html[m
[1m+++ b/conformity/templates/conformity/finding_detail.html[m
[36m@@ -27,10 +27,10 @@[m
 {% block content %}[m
     <h2 class="h4">Audit information</h2>[m
     <p>{{ finding.audit.get_type }} realized by {{ finding.audit.auditor }} on {{ finding.audit.organization }} from {{ finding.audit.start_date }} to {{ finding.audit.end_date }}.</p>[m
[31m-    {% if finding.audit.get_policies %}[m
[32m+[m[32m    {% if finding.audit.get_frameworks %}[m
     <p>The following policies were within the audit scope : </p>[m
     <ul>[m
[31m-        {% for policy in finding.audit.get_policies %}[m
[32m+[m[32m        {% for policy in finding.audit.get_frameworks %}[m
             <li>{{ policy }}</li>[m
         {% endfor %}[m
     </ul>[m
[1mdiff --git a/conformity/templates/conformity/organization_list.html b/conformity/templates/conformity/organization_list.html[m
[1mindex b9c1588..85eec52 100644[m
[1m--- a/conformity/templates/conformity/organization_list.html[m
[1m+++ b/conformity/templates/conformity/organization_list.html[m
[36m@@ -26,7 +26,7 @@[m
                     <p>{{ org.administrative_id }}</p>[m
                 </td>[m
                 <td class="text-center">[m
[31m-                    {% for item in org.get_policies %}[m
[32m+[m[32m                    {% for item in org.get_frameworks %}[m
                         <a href="{% url 'conformity:conformity_orgpol_index' org.id item.id %}">[m
                            <div class="btn btn-primary my-1" style="width:15em;">[m
                             {{ item }}[m
[1mdiff --git a/conformity/tests.py b/conformity/tests.py[m
[1mindex bca136e..460b8d2 100644[m
[1m--- a/conformity/tests.py[m
[1m+++ b/conformity/tests.py[m
[36m@@ -126,9 +126,9 @@[m [mclass OrganizationModelTest(TestCase):[m
         self.assertEqual(conformities.count(), 1)[m
 [m
     def test_get_policies(self):[m
[31m-        self.organization.applicable_policies.add(self.policy1)[m
[31m-        self.organization.applicable_policies.add(self.policy2)[m
[31m-        policies = self.organization.get_policies()[m
[32m+[m[32m        self.organization.applicable_frameworks.add(self.policy1)[m
[32m+[m[32m        self.organization.applicable_frameworks.add(self.policy2)[m
[32m+[m[32m        policies = self.organization.get_frameworks()[m
         self.assertIn(self.policy1, policies)[m
         self.assertIn(self.policy2, policies)[m
 [m
[36m@@ -154,7 +154,7 @@[m [mclass AuditModelTests(TestCase):[m
 [m
     def test_policies(self):[m
         audit = Audit.objects.get(id=1)[m
[31m-        self.assertEqual(audit.get_policies().count(), 1)[m
[32m+[m[32m        self.assertEqual(audit.get_frameworks().count(), 1)[m
 [m
     def test_type(self):[m
         audit = Audit.objects.get(id=1)[m
[1mdiff --git a/conformity/urls.py b/conformity/urls.py[m
[1mindex e68154c..8bd82b7 100644[m
[1m--- a/conformity/urls.py[m
[1m+++ b/conformity/urls.py[m
[36m@@ -29,8 +29,8 @@[m [murlpatterns = [[m
     path('organization/create', views.OrganizationCreateView.as_view(), name='organization_create'),[m
     path('organization/update/<int:pk>', views.OrganizationUpdateView.as_view(), name='organization_form'),[m
 [m
[31m-    path('framework/', views.PolicyIndexView.as_view(), name='policy_index'),[m
[31m-    path('framework/<int:pk>/', views.PolicyDetailView.as_view(), name='policy_detail'),[m
[32m+[m[32m    path('framework/', views.FrameworkIndexView.as_view(), name='framework_index'),[m
[32m+[m[32m    path('framework/<int:pk>/', views.FrameworkDetailView.as_view(), name='framework_detail'),[m
 [m
     path('action/', views.ActionIndexView.as_view(), name='action_index'),[m
     path('action/create', views.ActionCreateView.as_view(), name='action_create'),[m
[1mdiff --git a/conformity/views.py b/conformity/views.py[m
[1mindex b54d9bd..273e5bb 100644[m
[1m--- a/conformity/views.py[m
[1m+++ b/conformity/views.py[m
[36m@@ -11,7 +11,7 @@[m [mfrom auditlog.models import LogEntry[m
 [m
 from .filterset import ActionFilter, ControlFilter, ControlPointFilter[m
 from .forms import ConformityForm, AuditForm, FindingForm, ActionForm, OrganizationForm, ControlForm, ControlPointForm[m
[31m-from .models import Organization, Policy, Conformity, Audit, Action, Finding, Control, ControlPoint[m
[32m+[m[32mfrom .models import Organization, Framework, Conformity, Audit, Action, Finding, Control, ControlPoint[m
 [m
 [m
 #[m
[36m@@ -26,7 +26,7 @@[m [mclass HomeView(LoginRequiredMixin, TemplateView):[m
         context = super().get_context_data(**kwargs)[m
         user = self.request.user[m
         context['organization_list'] = Organization.objects.all()[m
[31m-        context['policy_list'] = Policy.objects.all()[m
[32m+[m[32m        context['framework_list'] = Framework.objects.all()[m
         context['conformity_list'] = Conformity.objects.filter(measure__level=0)[m
         context['audit_list'] = Audit.objects.all()[m
         context['action_list'] = Action.objects.all()[m
[36m@@ -105,16 +105,16 @@[m [mclass OrganizationCreateView(LoginRequiredMixin, CreateView):[m
     form_class = OrganizationForm[m
 [m
 #[m
[31m-# Policy[m
[32m+[m[32m# Framework[m
 #[m
 [m
 [m
[31m-class PolicyIndexView(LoginRequiredMixin, ListView):[m
[31m-    model = Policy[m
[32m+[m[32mclass FrameworkIndexView(LoginRequiredMixin, ListView):[m
[32m+[m[32m    model = Framework[m
 [m
 [m
[31m-class PolicyDetailView(LoginRequiredMixin, DetailView):[m
[31m-    model = Policy[m
[32m+[m[32mclass FrameworkDetailView(LoginRequiredMixin, DetailView):[m
[32m+[m[32m    model = Framework[m
 [m
 [m
 #[m
[36m@@ -133,7 +133,7 @@[m [mclass ConformityOrgPolIndexView(LoginRequiredMixin, ListView):[m
 [m
     def get_queryset(self, **kwargs):[m
         return Conformity.objects.filter(organization__id=self.kwargs['org']) \[m
[31m-            .filter(measure__policy__id=self.kwargs['pol']) \[m
[32m+[m[32m            .filter(measure__framework__id=self.kwargs['pol']) \[m
             .filter(measure__level=0) \[m
             .order_by('measure__order')[m
 [m
[1mdiff --git a/oxomium/settings.py b/oxomium/settings.py[m
[1mindex cb0962a..688c10c 100644[m
[1m--- a/oxomium/settings.py[m
[1m+++ b/oxomium/settings.py[m
[36m@@ -145,7 +145,7 @@[m [mLOGOUT_REDIRECT_URL = "/"[m
 # AuditLog configuration[m
 AUDITLOG_INCLUDE_ALL_MODELS = True[m
 AUDITLOG_INCLUDE_TRACKING_MODELS = ([m
[31m-    "conformity.Organization", {"model": "conformity.Organization", "m2m_fields": ["applicable_policies"], },[m
[32m+[m[32m    "conformity.Organization", {"model": "conformity.Organization", "m2m_fields": ["applicable_frameworks"], },[m
     "conformity.Action", {"model": "conformity.Action", "m2m_fields": ["associated_conformity", "associated_findings"], },[m
     "conformity.Audit", {"model": "conformity.Audit", "m2m_fields": ["audited_policies"], }[m
 )[m
