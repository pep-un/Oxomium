"""
Conformity module manage all the manual declarative aspect of conformity management.
It's Organized around Organization, Framework, Requirement and Conformity classes.
"""
from calendar import monthrange
from statistics import mean
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.signals import m2m_changed, pre_save, post_save, post_init
from django.core.validators import MaxValueValidator, MinValueValidator
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from auditlog.context import set_actor
import magic, pycountry
from mptt.models import MPTTModel, TreeForeignKey

User = get_user_model()


class FrameworkManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(name=name)


class Framework(models.Model):
    """
    Framework class represent the conformity framework you will apply on Organization.
    A Framework is simply a collections of Requirement with publication parameter.
    """

    class Type(models.TextChoices):
        """ List of the Type of framework """
        INTERNATIONAL = 'INT', _('International Standard')
        NATIONAL = 'NAT', _('National Standard')
        TECHNICAL = 'TECH', _('Technical Standard')
        RECOMMENDATION = 'RECO', _('Technical Recommendation')
        POLICY = 'POL', _('Internal Policy')
        OTHER = 'OTHER', _('Other')

    class Language():
        @classmethod
        def choices(cls):
            return[(lang.alpha_2, lang.name) for lang in pycountry.languages if hasattr(lang, 'alpha_2')]

    objects = FrameworkManager()
    name = models.CharField(max_length=256, unique=True)
    version = models.IntegerField(default=0)
    publish_by = models.CharField(max_length=256)
    type = models.CharField(max_length=5, choices=Type.choices, default=Type.OTHER)
    attachment = models.ManyToManyField('Attachment', blank=True, related_name='frameworks')
    language = models.CharField(max_length=2,choices=Language.choices(),default='en')

    class Meta:
        ordering = ['name']
        verbose_name = 'Framework'
        verbose_name_plural = 'Frameworks'

    def __str__(self):
        return str(self.name)

    def natural_key(self):
        return (self.name)

    def get_type(self):
        """return the readable version of the Framework Type"""
        return self.Type(self.type).label

    def get_requirements(self):
        """return all non-root requirements for this framework"""
        return (Requirement.objects
                .filter(framework=self)
                .exclude(parent__isnull=True)
                .order_by('tree_id', 'lft'))

    def get_requirements_number(self):
        """return the number of leaf Requirement related to the Framework"""
        from django.db.models import F
        return Requirement.objects.filter(framework=self, rght=F('lft') + 1).count()

    def get_root_requirement(self):
        """return the root Requirement of the Framework"""
        return Requirement.objects.filter(framework=self, parent__isnull=True)

    def get_first_requirements(self):
        """return the Requirement of the first hierarchical level of the Framework"""
        return Requirement.objects.filter(framework=self, parent__parent__isnull=True).order_by('order')


class Organization(models.Model):
    """
    Organization class is a representation of a company, a division of company, an administration...
    The Organization may answer to one or several Framework.
    """
    name = models.CharField(max_length=256, unique=True)
    administrative_id = models.CharField(max_length=256, blank=True)
    description = models.TextField(max_length=4096, blank=True)
    applicable_frameworks = models.ManyToManyField(Framework, blank=True)
    attachment = models.ManyToManyField('Attachment', blank=True, related_name='organizations')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return str(self.name)

    def natural_key(self):
        return (self.name)

    @staticmethod
    def get_absolute_url():
        """return the absolute URL for Forms, could probably do better"""
        return reverse('conformity:organization_index')

    def get_frameworks(self):
        """return all Framework applicable to the Organization"""
        return self.applicable_frameworks.all()

    def remove_conformity(self, pid):
        """Cascade deletion of conformity"""
        with set_actor('system'):
            requirement_set = Requirement.objects.filter(framework=pid).values_list('id', flat=True)
            Conformity.objects.filter(requirement__in=requirement_set, organization=self.id).delete()
    
    def add_conformity(self, pid):
        """Automatic creation of conformity"""
        with set_actor('system'):
            requirement_set = Requirement.objects.filter(framework=pid)
            conformities = [Conformity(organization=self, requirement=requirement) for requirement in requirement_set]
            Conformity.objects.bulk_create(conformities)


class RequirementManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(name=name)


class Requirement(MPTTModel):
    """
    A Requirement is a precise requirement.
    Requirement can be hierarchical in order to form a collection of Requirement, aka Framework.
    A Requirement is not representing the conformity level, see Conformity class.
    """
    objects = RequirementManager()
    code = models.CharField(max_length=5, blank=True)
    name = models.CharField(max_length=50, blank=True, unique=True)
    order = models.IntegerField(default=1)
    framework = models.ForeignKey(Framework, on_delete=models.CASCADE)
    parent = TreeForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    title = models.CharField(max_length=256, blank=True)
    description = models.TextField(blank=True)

    class MPTTMeta:
        order_insertion_by = ['order']

    def __str__(self):
        return str(self.name) + ": " + str(self.title)

    def natural_key(self):
        return (self.name)

    natural_key.dependencies = ['conformity.framework']


class Conformity(models.Model):
    """
    Conformity represent the conformity of an Organization to a Requirement.
    Value are automatically update for parent requirement conformity
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True)
    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE, null=True)
    applicable = models.BooleanField(default=True)
    status = models.IntegerField(default=None, validators=[MinValueValidator(0), MaxValueValidator(100)], null=True, blank=True)
    responsible = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    comment = models.TextField(max_length=4096, blank=True)

    class Meta:
        ordering = ['organization', 'requirement']
        verbose_name = 'Conformity'
        verbose_name_plural = 'Conformities'
        unique_together = (('organization', 'requirement'),)

    def __str__(self):
        return "[" + str(self.organization) + "] " + str(self.requirement)

    def natural_key(self):
        return self.organization, self.requirement

    natural_key.dependencies = ['conformity.framework', 'conformity.requirement', 'conformity.organization']

    def get_absolute_url(self):
        """Return the absolute URL of the class for Form, probably not the best way to do it"""
        return reverse('conformity:conformity_detail_index',
                       kwargs={'org': self.organization.id, 'pol': self.requirement.framework.id})

    def get_descendants(self):
        """Return all children Conformity based on Requirement hierarchy"""
        return (Conformity.objects
                .filter(organization=self.organization,
                        requirement__in=self.requirement.get_descendants())
                .order_by('requirement__order'))

    def get_parent(self):
        """Return the parent Conformity based on Requirement hierarchy"""
        req_parent = self.requirement.get_parent()
        if not req_parent:
            return None
        return (Conformity.objects
                .filter(organization=self.organization, requirement=req_parent)
                .first())

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
        for child in self.get_descendants():
            child.set_responsible(resp)

    def update(self):
        """Update conformity to recursivly update conformity when change"""
        with set_actor('system'):
            children = self.get_descendants().filter(applicable=True).filter(status__gte=0,status__lte=100)
            if children.exists():
                self.status = children.aggregate(mean_status=models.Avg('status'))['mean_status']
                self.applicable = True
            self.save()
            parent = self.get_parent()
            if parent:
                parent.update()


# Callback functions


@receiver(pre_save, sender=Requirement)
def post_init_callback(instance, **kwargs):
    """This function keep hierarchy of the Requirement working on each Requirement instantiation"""
    if instance.parent:
        instance.name = f"{instance.parent.name}-{instance.code}"
    else:
        instance.name = instance.code


@receiver(m2m_changed, sender=Organization.applicable_frameworks.through)
def change_framework(instance, action, pk_set, *args, **kwargs):
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

    name = models.CharField(max_length=256, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    description = models.TextField(max_length=4096, blank=True)
    conclusion = models.TextField(max_length=4096, blank=True)
    auditor = models.CharField(max_length=256)
    audited_frameworks = models.ManyToManyField(Framework, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    report_date = models.DateField(null=True, blank=True)
    type = models.CharField(
        max_length=5,
        choices=Type.choices,
        default=Type.OTHER,
    )
    attachment = models.ManyToManyField('Attachment', blank=True, related_name='audits')

    class Meta:
        ordering = ['-report_date','-start_date']

    def __str__(self):

        date_format='%b %Y'

        if self.report_date:
            display_date = self.report_date.strftime(date_format)
        elif self.start_date:
            display_date = self.start_date.strftime(date_format)
        elif self.end_date:
            display_date = self.end_date.strftime(date_format)
        else:
            display_date = ""

        if self.name :
            return self.name
        else :
            return str(self.auditor) + "/" + str(self.organization) + " (" + display_date + ")"

    @staticmethod
    def get_absolute_url():
        """return the absolute URL for Forms, could probably do better"""
        return reverse('conformity:audit_index')

    def get_frameworks(self):
        """return all Framework within the Audit scope"""
        return self.audited_frameworks.all()

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
        """ List of the Type of finding """
        CRITICAL = 'CRT', _('Critical non-conformity')
        MAJOR = 'MAJ', _('Major non-conformity')
        MINOR = 'MIN', _('Minor non-conformity')
        OBSERVATION = 'OBS', _('Opportunity For Improvement')
        POSITIVE = 'POS', _('Positive finding')
        OTHER = 'OTHER', _('Other comment')

    name = models.CharField(max_length=256, blank=True)
    short_description = models.CharField(max_length=256)
    description = models.TextField(max_length=4096, blank=True)
    observation = models.TextField(max_length=4096, blank=True)
    recommendation = models.TextField(max_length=4096, blank=True)
    reference = models.TextField(max_length=4096, blank=True)
    audit = models.ForeignKey(Audit, on_delete=models.CASCADE)
    severity = models.CharField(
        max_length=5,
        choices=Severity.choices,
        default=Severity.OBSERVATION,
    )
    archived = models.BooleanField(default=False)
    cvss = models.FloatField('CVSS', blank=True, null=True, default=None)
    cvss_descriptor = models.CharField('CVSS Vector',max_length=256, blank=True)

    class Meta:
        ordering = ['severity']

    def clean(self):
        if self.cvss is not None and (self.cvss < 0.1 or self.cvss > 10.0):
            raise ValidationError('CVSS must be between 0.1 and 10.0.')
        super().clean()

    def __str__(self):
        return str(self.short_description)

    def get_severity(self):
        """return the readable version of the Findings Severity"""
        return self.Severity(self.severity).label

    def get_absolute_url(self):
        """"return somewhere else when an edit has work"""
        return reverse('conformity:finding_detail', kwargs={'pk': self.id})

    def get_action(self):
        """Return the list of Action associated with this Findings"""
        return Action.objects.filter(associated_findings=self.id).filter(active=True)


class Control(models.Model):
    """
    Control class represent the periodic control needed to verify the security and the effectiveness of the security requirement.
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

    class Meta:
        ordering = ['level','frequency','title']

    def __str__(self):
        return "[" + str(self.organization) + "] " + str(self.title)

    @staticmethod
    def get_absolute_url():
        """return the absolute URL for Forms, could probably do better"""
        return reverse('conformity:control_index')

    @staticmethod
    def post_init_callback(instance, **kwargs):
        ControlPoint.objects.filter(control=instance.id).filter(Q(status='SCHD') | Q(status='TOBE')).delete()

        num_cp = instance.frequency
        today = date.today()
        start_date = date(today.year, 1, 1)
        delta = timedelta(days=365 // num_cp - 2)
        end_date = start_date + delta
        for _ in range(num_cp):
            period_start_date = date(start_date.year, start_date.month, 1)
            period_end_date = date(end_date.year, end_date.month, monthrange(end_date.year, end_date.month)[1])
            if not ControlPoint.objects.filter(control=instance.id).filter(period_start_date=period_start_date).filter(period_end_date=period_end_date) :
                ControlPoint.objects.create(
                    control=instance,
                    period_start_date=period_start_date,
                    period_end_date=period_end_date,
                )
            start_date = period_end_date + timedelta(days=1)
            end_date = start_date + delta - timedelta(days=1)


    def get_controlpoint(self):
        """Return all control point based on this control"""
        return ControlPoint.objects.filter(control=self.id).order_by('period_start_date')


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
    attachment = models.ManyToManyField('Attachment', blank=True, related_name='ControlPoint')

    class Meta:
        ordering = ['period_end_date']

    @staticmethod
    def get_absolute_url():
        """return the absolute URL for Forms, could probably do better"""
        return reverse('conformity:control_index')

    @staticmethod
    def pre_save(sender, instance, *args, **kwargs):
        if instance.status != ControlPoint.Status.COMPLIANT and instance.status != ControlPoint.Status.NONCOMPLIANT:
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

    class Meta :
        ordering = ['status', '-update_date']

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


class Attachment(models.Model):
    file = models.FileField(upload_to='attachments/')
    comment = models.TextField(max_length=4096, blank=True)
    mime_type = models.CharField(max_length=255, blank=True)
    create_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-create_date', 'file']

    def __str__(self):
        return self.file.name.split("/")[1]

    @staticmethod
    def pre_save(sender, instance, *args, **kwargs):
        # Read file and set mime_type
        file_content = instance.file.read()
        instance.file.seek(0)
        mime = magic.Magic(mime=True)
        instance.mime_type = mime.from_buffer(file_content)

        # TODO filter on mime type

#
# Signal
#


post_save.connect(Control.post_init_callback, sender=Control)
pre_save.connect(ControlPoint.pre_save, sender=ControlPoint)
pre_save.connect(Attachment.pre_save, sender=Attachment)
