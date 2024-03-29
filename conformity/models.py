"""
Conformity module manage all the manual declarative aspect of conformity management.
It's Organized around Organization, Policy, Measure and Conformity classes.
"""
from calendar import monthrange
from statistics import mean
from datetime import date, timedelta
from django.db import models
from django.db.models.signals import m2m_changed, pre_save, post_save, post_init
from django.core.validators import MaxValueValidator, MinValueValidator
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from auditlog.context import set_actor

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
        """return the Measure of the first hierarchical level of the Policy"""
        return Measure.objects.filter(policy=self.id).filter(level=1).order_by('order')


class Organization(models.Model):
    """
    Organization class is a representation of a company, a division of company, a administration...
    The Organization may answer to one or several Policy.
    """
    name = models.CharField(max_length=256, unique=True)
    administrative_id = models.CharField(max_length=256, blank=True)
    description = models.TextField(max_length=4096, blank=True)
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
        with set_actor('system'):
            measure_set = Measure.objects.filter(policy=pid)
            for measure in measure_set:
                Conformity.objects.filter(measure=measure.id).filter(organization=self.id).delete()

    def add_conformity(self, pid):
        """Automatic creation of conformity"""
        with set_actor('system'):
            measure_set = Measure.objects.filter(policy=pid)
            for measure in measure_set:
                conformity = Conformity(organization=self, measure=measure)
                conformity.save()


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
        return str(self.name + ": " + self.title)

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
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True)
    measure = models.ForeignKey(Measure, on_delete=models.CASCADE, null=True)
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
        p = Conformity.objects.filter(organization=self.organization).filter(measure=self.measure.parent)
        if len(p) == 1:
            return p[0]
        else:
            return None

    def get_action(self):
        """Return the list of Action associated with this Conformity"""
        return Action.objects.filter(associated_conformity=self.id).filter(active=True)

    def get_control(self):
        """Return the list of Control associated with this Conformity"""
        return Control.objects.filter(conformity=self.id)

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
        with set_actor('system'):
            children = self.get_children().filter(applicable=True)

            if children.exists():
                children_stat = [child.status for child in children]
                self.status = mean(children_stat)
                self.applicable = True

            self.save()

            parent = self.get_parent()
            if parent:
                parent.update()


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
    description = models.TextField(max_length=4096, blank=True)
    conclusion = models.TextField(max_length=4096, blank=True)
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
        if self.report_date:
            date = self.report_date.strftime('%b %Y')
        elif self.start_date:
            date = self.start_date.strftime('%b %Y')
        elif self.end_date:
            date = self.end_date.strftime('%b %Y')
        else:
            date = "xx-xxxx"
            
        return "[" + str(self.organization) + "] " + str(self.auditor) + " (" + date + ")"

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
    description = models.TextField(max_length=4096, blank=True)
    reference = models.TextField(max_length=4096, blank=True)
    audit = models.ForeignKey(Audit, on_delete=models.CASCADE)
    severity = models.CharField(
        max_length=5,
        choices=Severity.choices,
        default=Severity.OBSERVATION,
    )

    def __str__(self):
        return str(self.short_description)

    def get_severity(self):
        """return the readable version of the Findings Severity"""
        return self.Severity(self.severity).label

    def get_absolute_url(self):
        """"return somewhere else when a edit has work """
        return reverse('conformity:audit_detail', kwargs={'pk': self.audit_id})

    def get_action(self):
        """Return the list of Action associated with this Findings"""
        return Action.objects.filter(associated_findings=self.id).filter(active=True)


class Control(models.Model):
    """
    Control class represent the periodic control needed to verify the security and the effectiveness of the security measure.
    """

    class Frequency(models.IntegerChoices):
        """ List of frequency possible for a control"""
        YEARLY = '1', _('Yearly')
        HALFYEARLY = '2', _('Half-Yearly')
        QUARTERLY = '4', _('Quarterly')
        BIMONTHLY = '6', _('Bimonthly')
        MONTHLY = '12', _('Monthly')

    class Level(models.IntegerChoices):
        """ List of control level possible for a control """
        FIRST = '1', _('1st level')
        SECOND = '2', _('2nd level')

    title = models.CharField(max_length=256)
    description = models.TextField(max_length=4096, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, blank=True, null=True)
    conformity = models.ManyToManyField(Conformity, blank=True)
    control = models.ManyToManyField('self', blank=True)
    frequency = models.IntegerField(
        choices=Frequency.choices,
        default=Frequency.YEARLY,
    )
    level = models.IntegerField(
        choices=Level.choices,
        default=Level.FIRST,
    )

    def __str__(self):
        return "[" + str(self.organization) + "] " + self.title

    @staticmethod
    def get_absolute_url():
        """return the absolute URL for Forms, could probably do better"""
        return reverse('conformity:control_index')

    @staticmethod
    def post_init_callback(instance, **kwargs):
        num_cp = instance.frequency
        today = date.today()
        start_date = date(today.year, 1, 1)
        delta = timedelta(days=365 // num_cp - 2)
        end_date = start_date + delta
        for _ in range(num_cp):
            period_start_date = date(start_date.year, start_date.month, 1)
            period_end_date = date(end_date.year, end_date.month, monthrange(end_date.year, end_date.month)[1])
            ControlPoint.objects.create(
                control=instance,
                period_start_date=period_start_date,
                period_end_date=period_end_date,
            )
            start_date = period_end_date + timedelta(days=1)
            end_date = start_date + delta - timedelta(days=1)


class ControlPoint(models.Model):
    """
    A control point is a specific point of verification of a periodic Control.
    """

    class Status(models.TextChoices):
        """ List of status possible for a ControlPoint"""
        SCHEDULED = 'SCHD', _('Scheduled')
        TOBEEVALUATED = 'TOBE', _('To evaluate')
        COMPLIANT = 'OK', _('Compliant')
        NONCOMPLIANT = 'NOK', _('Non-Compliant')
        MISSED = 'MISS', _('Missed')

    control = models.ForeignKey(Control, on_delete=models.CASCADE, null=True, blank=True)
    control_date = models.DateTimeField(blank=True, null=True)
    control_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    period_start_date = models.DateField()
    period_end_date = models.DateField()
    status = models.CharField(choices=Status.choices, max_length=4, default=Status.SCHEDULED)
    comment = models.TextField(max_length=4096, blank=True)

    @staticmethod
    def get_absolute_url():
        """return the absolute URL for Forms, could probably do better"""
        return reverse('conformity:control_index')

    @staticmethod
    def pre_save(sender, instance, *args, **kwargs):
        today = date.today()
        if instance.period_end_date < today:
            instance.status = ControlPoint.Status.MISSED
        elif instance.period_start_date <= today <= instance.period_end_date:
            instance.status = ControlPoint.Status.TOBEEVALUATED
        else:
            instance.status = ControlPoint.Status.SCHEDULED


    def __str__(self):
        return "[" + str(self.control.organization) + "] " + self.control.title + " (" \
            + self.period_start_date.strftime('%b-%Y') + "⇒" \
            + self.period_end_date.strftime('%b-%Y') + ")"


    def get_action(self):
        """Return the list of Action associated with this Findings"""
        return Action.objects.filter(associated_controlPoints=self.id)

class Action(models.Model):
    """
    Action class represent the actions taken by the Organization to improve security.
    """

    class Status(models.TextChoices):
        """ List of possible Status for an action """
        ANALYSING = '1', _('Analysing')
        PLANNING = '2', _('Planning')
        IMPLEMENTING = '3', _('Implementing')
        CONTROLLING = '4', _('Controlling')
        ENDED = '5', _('Closed')
        """MISC status"""
        FROZEN = '7', _('Frozen')
        CANCELED = '9', _('Canceled')

    ' Generic'
    title = models.CharField(max_length=256)
    create_date = models.DateField(default=timezone.now)
    update_date = models.DateField(default=timezone.now)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    status = models.CharField(
        max_length=5,
        choices=Status.choices,
        default=Status.ANALYSING,
    )
    status_comment = models.TextField(max_length=4096, blank=True)
    reference = models.URLField(blank=True)
    active = models.BooleanField(default=True)

    ' Analyse Phase'
    description = models.TextField(max_length=4096, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, blank=True, null=True)
    associated_conformity = models.ManyToManyField(Conformity, blank=True)
    associated_findings = models.ManyToManyField(Finding, blank=True)
    associated_controlPoints = models.ManyToManyField(ControlPoint, blank=True)
    #TODO associated_risks = models.ManyToManyField(Risk, blank=True)

    ' PLAN phase'
    plan_start_date = models.DateField(null=True, blank=True)
    plan_end_date = models.DateField(null=True, blank=True)
    plan_comment = models.TextField(max_length=4096, blank=True)

    ' IMPLEMENT Phase'
    implement_start_date = models.DateField(null=True, blank=True)
    implement_end_date = models.DateField(null=True, blank=True)
    implement_status = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    implement_comment = models.TextField(max_length=4096, blank=True)

    ' CONTROL Phase'
    control_date = models.DateField(null=True, blank=True)
    control_comment = models.TextField(max_length=4096, blank=True)
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

        if self.status in [Action.Status.FROZEN, Action.Status.ENDED, Action.Status.CANCELED]:
            self.active = False

        return super(Action, self).save(*args, **kwargs)


#
# Signal
#


post_save.connect(Control.post_init_callback, sender=Control)
pre_save.connect(ControlPoint.pre_save, sender=ControlPoint)
