"""
Conformity module manage all the manual declarative aspect of conformity management.
It's Organized around Organization, Policy, Measure and Conformity classes.
"""

from statistics import mean
from django.db import models
from django.db.models.signals import m2m_changed, pre_save
from django.core.validators import MaxValueValidator, MinValueValidator
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.urls import reverse

User = get_user_model()


class PolicyManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(name=name)


class Policy(models.Model):
    """
    Policy class represent the conformity policy you will apply on Organization.
    A Policy is simply a collections of Measure with publication parameter.
    """

    class Type(models.TextChoices):
        """ List of the Type of policy """
        INTERNATIONAL = 'INT', _('International Standard')
        NATIONAL = 'NAT', _('National Standard')
        TECHNICAL = 'TECH', _('Technical Standard')
        RECOMMENDATION = 'RECO', _('Technical Recommendation')
        POLICY = 'POL', _('Internal Policy')
        OTHER = 'OTHER', _('Other')

    objects = PolicyManager()
    name = models.CharField(max_length=256, unique=True)
    version = models.IntegerField(default=0)
    publish_by = models.CharField(max_length=256)
    type = models.CharField(
        max_length=5,
        choices=Type.choices,
        default=Type.OTHER,
    )

    class Meta:
        ordering = ['name']
        verbose_name = 'Policy'
        verbose_name_plural = 'Policies'

    def __str__(self):
        return str(self.name)

    def natural_key(self):
        return self.name

    def get_type(self):
        """return the readable version of the Policy Type"""
        return self.Type(self.type).label

    def get_measures(self):
        """return all Measure related to the Policy"""
        return Measure.objects.filter(policy=self.id)

    def get_measures_number(self):
        """return the number of leaf Measure related to the Policy"""
        return Measure.objects.filter(policy=self.id).filter(measure__is_parent=False).count()

    def get_root_measure(self):
        """return the root Measure of the Policy"""
        return Measure.objects.filter(policy=self.id).filter(level=0).order_by('order')

    def get_first_measures(self):
        """return the root Measure of the Policy"""
        return Measure.objects.filter(policy=self.id).filter(level=1).order_by('order')


class Organization(models.Model):
    """
    Organization class is a representation of a company, a division of company, a administration...
    The Organization may answer to one or several Policy.
    """
    name = models.CharField(max_length=256, unique=True)
    administrative_id = models.CharField(max_length=256, blank=True)
    description = models.CharField(max_length=256, blank=True)
    applicable_policies = models.ManyToManyField(Policy, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return str(self.name)

    def natural_key(self):
        return self.name

    @staticmethod
    def get_absolute_url():
        """return the absolute URL for Forms, could probably do better"""
        return reverse('conformity:organization_index')

    def get_policies(self):
        """return all Policy applicable to the Organization"""
        return self.applicable_policies.all()

    def remove_conformity(self, pid):
        """Cascade deletion of conformity"""
        measure_set = Measure.objects.filter(policy=pid)
        for measure in measure_set:
            Conformity.objects.filter(measure=measure.id).filter(organization=self.id).delete()

    def add_conformity(self, pid):
        """Automatic creation of conformity"""
        measure_set = Measure.objects.filter(policy=pid)
        for measure in measure_set:
            conformity = Conformity(organization=self, measure=measure)
            conformity.save()

    def get_policy_status(self, pid):
        """Return the conformity level of the Policy on the Organisation"""
        conformities = Conformity.objects.filter(policy=pid).filter(organization=self.id) \
            .filter(measure__level=0)
        conf_stat = []
        for conf in conformities:
            conf_stat.append(conf.status)
        return mean(conf_stat)


class MeasureManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(name=name)


class Measure(models.Model):
    """
    A Measure is a precise requirement.
    Measure can be hierarchical in order to form a collection of Measure, aka Policy.
    A Measure is not representing the conformity level, see Conformity class.
    """
    objects = MeasureManager()
    code = models.CharField(max_length=5, blank=True)
    name = models.CharField(max_length=50, blank=True, unique=True)
    level = models.IntegerField(default=0)
    order = models.IntegerField(default=1)
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=256, blank=True)
    description = models.TextField(blank=True)
    is_parent = models.BooleanField(default=False)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return str(self.name)

    def natural_key(self):
        return self.name

    natural_key.dependencies = ['conformity.policy']

    def get_children(self):
        """Return all children of the measure"""
        return Measure.objects.filter(parent=self.id).order_by('order')


class Conformity(models.Model):
    """
    Conformity represent the conformity of an Organization to a Measure.
    Value are automatically update for parent measure conformity
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    measure = models.ForeignKey(Measure, on_delete=models.CASCADE)
    applicable = models.BooleanField(default=True)
    status = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)], null=True, blank=True)
    responsible = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    comment = models.TextField(max_length=4096, blank=True)

    class Meta:
        ordering = ['organization', 'measure']
        verbose_name = 'Conformity'
        verbose_name_plural = 'Conformities'
        unique_together = (('organization', 'measure'),)

    def __str__(self):
        return "[" + str(self.organization) + "] " + str(self.measure)

    def natural_key(self):
        return self.organization, self.measure

    natural_key.dependencies = ['conformity.policy', 'conformity.measure', 'conformity.organization']

    def get_absolute_url(self):
        """Return the absolute URL of the class for Form, probably not the best way to do it"""
        return reverse('conformity:conformity_orgpol_index',
                       kwargs={'org': self.organization.id, 'pol': self.measure.policy.id})

    def get_children(self):
        """Return all children Conformity based on Measure hierarchy"""
        return Conformity.objects.filter(organization=self.organization) \
            .filter(measure__parent=self.measure.id).order_by('measure__order')

    def get_parent(self):
        """Return the parent Conformity based on Measure hierarchy"""
        return Conformity.objects.filter(organization=self.organization) \
            .filter(measure=self.measure.parent).order_by('measure__order')

    def set_status(self, i):
        """Update the status and call recursive update function"""
        self.status = i
        self.save()
        self.update()

    def set_responsible(self, resp):
        """Update the responsible and apply to child"""
        self.responsible = resp
        self.save()
        for child in self.get_children():
            child.set_responsible(resp)

    def update(self):
        """Recursive function to crawl up the Measure tree and update all status"""
        children_list = self.get_children()
        children_stat = []
        if children_list.exists():
            for child in children_list:
                if child.applicable:
                    children_stat.append(child.status)

            if len(children_stat):
                self.status = mean(children_stat)
                self.applicable = True
            else:
                self.status = 0
                self.applicable = False
        #       else:
        #           this is a leaf of the tree, no action to do other than save teh data
        self.save()

        if not self.measure.level == 0:
            self.get_parent()[0].update()


# Callback functions


@receiver(pre_save, sender=Measure)
def post_init_callback(instance, **kwargs):
    """This function keep hierarchy of the Measure working on each Measure instantiation"""
    if instance.parent:
        instance.name = instance.parent.name + "-" + instance.code
        instance.level = instance.parent.level + 1
        instance.parent.is_parent = 1
    else:
        instance.name = instance.code


@receiver(m2m_changed, sender=Organization.applicable_policies.through)
def change_policy(instance, action, pk_set, *args, **kwargs):
    if action == "post_add":
        for pk in pk_set:
            instance.add_conformity(pk)

    if action == "post_remove":
        for pk in pk_set:
            instance.remove_conformity(pk)


class Audit(models.Model):
    """
    Audit class represent the auditing event, on an Organization.
    An Audit is a collections of findings.
    """

    class Type(models.TextChoices):
        """ List of the Type of audit """
        INTERNAL = 'INT', _('Internal Audit')
        CUSTOMER = 'CUS', _('Customer Audit')
        AUTHORITY = 'NAT', _('National Authority')
        AUDITOR = 'AUD', _('3rd party auditor')
        OTHER = 'OTHER', _('Other')

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    description = models.CharField(max_length=4096, blank=True)
    conclusion = models.CharField(max_length=4096, blank=True)
    auditor = models.CharField(max_length=256)
    audited_policies = models.ManyToManyField(Policy, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    report_date = models.DateField(null=True, blank=True)
    type = models.CharField(
        max_length=5,
        choices=Type.choices,
        default=Type.OTHER,
    )

    class Meta:
        ordering = ['report_date']

    def __str__(self):
        return "[" + str(self.organization) + "] " + str(self.auditor) + " (" + self.report_date.strftime('%b %Y') + ")"

    @staticmethod
    def get_absolute_url():
        """return the absolute URL for Forms, could probably do better"""
        return reverse('conformity:audit_index')

    def get_policies(self):
        """return all Policy within the Audit scope"""
        return self.audited_policies.all()

    def get_type(self):
        """return the readable version of the Audit Type"""
        return self.Type(self.type).label

    def get_findings(self):
        """return all the findings associated to an Audit"""
        return Finding.objects.filter(audit=self.id)

    def get_findings_number(self):
        """return the number of findings associated to an Audit"""
        return Finding.objects.filter(audit=self.id).count()

    def get_critical_findings(self):
        """return critical findings associated to an Audit"""
        return Finding.objects.filter(audit=self.id).filter(severity=Finding.Severity.CRITICAL)

    def get_major_findings(self):
        """return major findings associated to an Audit"""
        return Finding.objects.filter(audit=self.id).filter(severity=Finding.Severity.MAJOR)

    def get_minor_findings(self):
        """return minor findings associated to an Audit"""
        return Finding.objects.filter(audit=self.id).filter(severity=Finding.Severity.MINOR)

    def get_observation_findings(self):
        """return observational findings associated to an Audit"""
        return Finding.objects.filter(audit=self.id).filter(severity=Finding.Severity.OBSERVATION)

    def get_positive_findings(self):
        """return positive findings associated to an Audit"""
        return Finding.objects.filter(audit=self.id).filter(severity=Finding.Severity.POSITIVE)

    def get_other_findings(self):
        """return other findings associated to an Audit"""
        return Finding.objects.filter(audit=self.id).filter(severity=Finding.Severity.OTHER)


class Finding(models.Model):
    """
    Finding class represent the element discover during and Audit.
    """

    class Severity(models.TextChoices):
        """ List of the Type of audit """
        CRITICAL = 'CRT', _('Critical non-conformity')
        MAJOR = 'MAJ', _('Major non-conformity')
        MINOR = 'MIN', _('Minor non-conformity')
        OBSERVATION = 'OBS', _('Opportunity For Improvement')
        POSITIVE = 'POS', _('Positive finding')
        OTHER = 'OTHER', _('Other remark')

    short_description = models.CharField(max_length=256)
    description = models.CharField(max_length=4096, blank=True)
    reference = models.CharField(max_length=4096, blank=True)
    audit = models.ForeignKey(Audit, on_delete=models.CASCADE)
    severity = models.CharField(
        max_length=5,
        choices=Severity.choices,
        default=Severity.OBSERVATION,
    )

    def get_severity(self):
        """return the readable version of the Findings Severity"""
        return self.Severity(self.severity).label

    @staticmethod
    def get_absolute_url():
        """return the absolute URL for Forms, could probably do better"""
        return reverse('conformity:audit_index')


class Action(models.Model):
    """
    Action class represent the actions taken by the Organization to improve security.
    """

    class Status(models.TextChoices):
        """ List of possible Status for an action """
        ' ANALYSE (ACT) Phase'
        ANALYSING = 'A', _('Action under analyse')
        ' PLAN Phase'
        PLANNING = 'P', _('Action analysed, waiting to be plan')
        QUEUED = 'Q', _('Action planned, waiting for implementation')
        ' IMPLEMENT (DO) Phase'
        IMPLEMENTING = 'I', _('Implementation in progress')
        IMPLEMENTED = 'C', _('Implemented, to bo controlled')
        ' CHECK Phase'
        SUCCESS = 'S', _('Control successfully')
        UNSUCCESS = 'U', _('control unsuccessfully')
        ' MISC'
        FROZEN = 'F', _('Frozen')
        CANCELED = 'X', _('Canceled')

    ' Analyse Phase'
    title = models.CharField(max_length=256)
    description = models.CharField(max_length=4096, blank=True)
    create_date = models.DateField(default=timezone.now)
    update_date = models.DateField(default=timezone.now)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    associated_conformity = models.ManyToManyField(Conformity, blank=True)
    associated_findings = models.ManyToManyField(Finding, blank=True)
    #TODO associated_risks = models.ManyToManyField(Risk, blank=True)
    status = models.CharField(
        max_length=5,
        choices=Status.choices,
        default=Status.ANALYSING,
    )

    ' PLAN phase'
    plan_start_date = models.DateField(null=True, blank=True)
    plan_end_date = models.DateField(null=True, blank=True)
    plan_comment = models.CharField(max_length=4096, blank=True)

    ' IMPLEMENT Phase'
    implement_start_date = models.DateField(null=True, blank=True)
    implement_end_date = models.DateField(null=True, blank=True)
    implement_status = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    implement_comment = models.CharField(max_length=4096, blank=True)

    ' CONTROL Phase'
    control_date = models.DateField(null=True, blank=True)
    control_comment = models.CharField(max_length=4096, blank=True)
    control_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                     null=True, blank=True, related_name='controller')

    def __str__(self):
        return "[" + str(self.organization) + "] " + str(self.title)

    @staticmethod
    def get_absolute_url():
        """return the absolute URL for Forms, could probably do better"""
        return reverse('conformity:action_index')

    def save(self, *args, **kwargs):
        """ On save, update timestamps """
        if not self.id:
            self.create_date = timezone.now()
        self.update_date = timezone.now()
        return super(Action, self).save(*args, **kwargs)