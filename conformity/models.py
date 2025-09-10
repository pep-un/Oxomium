"""
Conformity module manage all the manual declarative aspect of conformity management.
It's Organized around Organization, Framework, Requirement and Conformity classes.
"""
# Standard library
from calendar import monthrange
from datetime import date, timedelta
from typing import List, Literal, Tuple

# Django (third-party)
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# Third-party
from auditlog.context import set_actor
from magic import Magic
from mptt.models import MPTTModel, TreeForeignKey
from pycountry import languages

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

    class Language:
        @classmethod
        def choices(cls):
            return[(lang.alpha_2, lang.name) for lang in languages if hasattr(lang, 'alpha_2')]

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
        return self.name

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
        return self.name

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
        return self.name

    natural_key.dependencies = ['conformity.framework']

    def get_parent(self):
        return self.get_ancestors().last()


class Conformity(models.Model):
    """
    Conformity represent the conformity of an Organization to a Requirement.
    Value are automatically update for parent requirement conformity
    """

    class StatusJustification(models.TextChoices):
        EXPERT = 'EXPT', _('From expert statement')
        CONTROL = 'CTRL', _('From successful control')
        ACTION = 'ACT', _('From completed action')
        FINDING = 'FIN', _('From an audit finding')
        CONFORMITY = 'CONF', _('From conformity aggregation')

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True)
    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE, null=True)
    applicable = models.BooleanField(default=True)
    responsible = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    comment = models.TextField(max_length=4096, blank=True)
    status = models.IntegerField(default=None, validators=[MinValueValidator(0), MaxValueValidator(100)], null=True, blank=True)
    status_last_update = models.DateTimeField(null=True, blank=True)
    status_justification = models.CharField(
        max_length=4,
        choices=StatusJustification.choices,
        default=StatusJustification.EXPERT,
        blank=True,
    )

    class Meta:
        ordering = ['organization', 'requirement__framework', 'requirement__tree_id', 'requirement__lft']
        verbose_name = 'Conformity'
        verbose_name_plural = 'Conformities'
        unique_together = (('organization', 'requirement'),)

    def __str__(self):
        return "[" + str(self.organization) + "] " + str(self.requirement)

    def natural_key(self):
        return self.organization, self.requirement

    natural_key.dependencies = ['conformity.framework', 'conformity.requirement', 'conformity.organization']

    def get_leaf(self):
        """Get all leaf from a node"""
        return [n for n in self.get_descendants() if n.requirement.is_leaf_node()]

    def get_completeness(self):
        leaves = self.get_leaf() or []
        total = len(self.get_leaf())
        if total ==0:
            return 0

        complete = sum(1 for n in leaves if n.status is not None)

        return round( (complete / total) * 100)

    def get_absolute_url(self):
        """Return the absolute URL of the class for Form, probably not the best way to do it"""
        return reverse('conformity:conformity_detail_index',
                       kwargs={'org': self.organization.id, 'pol': self.requirement.framework.id})

    def get_descendants(self):
        """Return all children Conformity based on Requirement hierarchy"""
        return (Conformity.objects
                .filter(organization=self.organization,
                        requirement__in=self.requirement.get_descendants()))

    def get_children(self):
        """Return all children Conformity based on Requirement hierarchy"""
        return (Conformity.objects
                .filter(organization=self.organization,
                        requirement__in=self.requirement.get_children()))
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

    def get_related(self,*,include_actions: bool = True,include_controls: bool = True,
            only_active: bool = False,negative_only: bool = False,
            sort: Literal["type_then_title", "recent_first", "alpha"] = "type_then_title",
            ) -> List[Tuple[Literal["action", "control", "controlpoint"], object]]:
        """
        Return a flat list of (kind, instance).

        Modes:
          - Default (negative_only=False):
              * 'action'  -> all actions (optionally filtered by only_active -> active=True)
              * 'control' -> Control objects (no 'active' notion)
          - Negative evidence (negative_only=True):
              * 'action'       -> actions IN PROGRESS (non-terminated)
              * 'controlpoint' -> current-period ControlPoints with NEGATIVE result (NONCOMPLIANT)
                (If you consider MISSED as negative too, add it in the status filter below.)

        Notes:
          - 'only_active' affects Actions only in the default mode.
          - Sorting tries to do something sensible across mixed kinds.
        """
        items: List[Tuple[Literal["action", "control", "controlpoint"], object]] = []

        if not negative_only:
            # ---------- default mode ----------
            if include_actions:
                actions_qs = self.actions.filter(active=True) if only_active else self.actions.all()
                for a in actions_qs:
                    items.append(("action", a))

            if include_controls:
                for c in self.get_control():
                    items.append(("control", c))

        else:
            # ---------- negative-only mode ----------
            if include_actions:
                actions_qs = self.actions.filter(
                    status__in=[
                        Action.Status.ANALYSING,
                        Action.Status.PLANNING,
                        Action.Status.IMPLEMENTING,
                        Action.Status.CONTROLLING,
                    ]
                )
                for a in actions_qs:
                    items.append(("action", a))

            if include_controls:
                today = date.today()
                cps = ControlPoint.objects.filter(
                    control__conformity=self,
                    period_start_date__lte=today,
                    period_end_date__gte=today,
                    status__in=[ControlPoint.Status.NONCOMPLIANT,ControlPoint.Status.MISSED,
                                ControlPoint.Status.SCHEDULED,ControlPoint.Status.TOBEEVALUATED],
                )

                for cp in cps:
                    items.append(("controlpoint", cp))

        # ---------- sorting ----------
        def _label(obj):
            # Try common fields, fallback to __str__
            return (
                    getattr(obj, "title", None)
                    or getattr(obj, "name", None)
                    or getattr(obj, "short_description", None)
                    or str(obj)
            )

        if sort == "type_then_title":
            order_kind = {"action": 0, "control": 1, "controlpoint": 2}
            items.sort(key=lambda t: (order_kind.get(t[0], 99), _label(t[1])))

        elif sort == "recent_first":
            # Use whatever "date-ish" we can find: update_date for Action, period_end_date for CP, fallback very old
            def _updated(obj):
                return (
                        getattr(obj, "update_date", None)
                        or getattr(obj, "period_end_date", None)
                        or date.min
                )

            items.sort(key=lambda t: (_updated(t[1]), _label(t[1])), reverse=True)

        elif sort == "alpha":
            items.sort(key=lambda t: _label(t[1]))

        return items

    def update_responsible(self):
        """Update the responsible in the descendants when added"""
        Conformity.objects.filter(
            organization=self.organization,
            requirement__in=self.requirement.get_descendants()
        ).update(responsible=self.responsible)

    def update_status(self):
        """Update this node's conformity status and propagate update to its parent."""
        with set_actor('system'):
            agg = (Conformity.objects.filter(
                    organization=self.organization,
                    requirement__parent=self.requirement,
                    applicable=True,
                    status__range=(0, 100),
                ).aggregate(mean_status=models.Avg("status"))
            )

            if agg["mean_status"] is not None:
                self.status = agg["mean_status"]
                self.status_justification = Conformity.StatusJustification.CONFORMITY
                self.status_last_update = timezone.now()
                self.save(update_fields=['status', 'status_justification', 'status_last_update'])

            parent = self.get_parent()
            if parent:
                parent.update_status()

    def update_applicable(self):
        """Update conformity to recursively apply the non-applicable flax to all descendant"""
        if not self.applicable and not self.requirement.is_leaf_node():
            descendants = Conformity.objects.filter(
                organization=self.organization,
                requirement__in=self.requirement.get_descendants()
            )
            descendants.update(applicable=False)

        elif self.applicable and self.requirement.is_child_node():
            ancestors = Conformity.objects.filter(
                organization=self.organization,
                requirement__in=self.requirement.get_ancestors()
            )
            ancestors.update(applicable=True)

    def set_status_from(self, value: int, justification: "Conformity.StatusJustification"):
        """Single point to update status + provenance + timestamp."""
        changed = (self.status != value) or (self.status_justification != justification)
        if not changed:
            return False

        if justification == Conformity.StatusJustification.EXPERT and not self.requirement.is_leaf_node():
            return False

        if justification in [Conformity.StatusJustification.ACTION, Conformity.StatusJustification.CONTROL]:
            negatives_exist = bool(self.get_related(negative_only=True))
            if value == 0 and not negatives_exist:
                return False
            if value == 100 and negatives_exist:
                return False

        self.applicable = True
        self.status = value
        self.status_justification = justification
        self.status_last_update = timezone.now()
        self.save()
        return True


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
        """return somewhere else when an edit has work"""
        return reverse('conformity:finding_detail', kwargs={'pk': self.id})

    def get_action(self):
        """Return the list of Action associated with this Findings"""
        return Action.objects.filter(associated_findings=self.id)

    def is_active(self) -> bool:
        return (not self.archived) and (self.severity != Finding.Severity.POSITIVE)

    def update_archived(self):
        """
        Keep `archived` consistent with linked Actions, using a single DB query:
        - If there are actions AND none is active -> archived = True
        - Otherwise (no actions OR at least one active) -> archived = False
        Idempotent: only writes when the value actually changes.
        """
        agg = self.actions.aggregate(
            total=Count("pk"),
            active=Count("pk", filter=Q(active=True)),
        )
        total = agg["total"] or 0
        active = agg["active"] or 0

        new_archived = (total > 0 and active == 0)

        if self.archived != new_archived:
            self.archived = new_archived
            self.save(update_fields=["archived"])


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
    def controlpoint_bootstrap(instance):
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
        return ControlPoint.objects.filter(control=self).order_by('period_start_date')


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
    def update_status(instance):
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
        return Action.objects.filter(associated_controlPoints=self)

    def is_current_period(self, when: date | None = None) -> bool:
        when = when or date.today()
        return self.period_start_date <= when <= self.period_end_date

    def is_final_status(self) -> bool:
        return self.status in (ControlPoint.Status.COMPLIANT, ControlPoint.Status.NONCOMPLIANT)


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
    associated_conformity = models.ManyToManyField(Conformity, blank=True, related_name='actions')
    associated_findings = models.ManyToManyField(Finding, blank=True, related_name='actions')
    associated_controlPoints = models.ManyToManyField(ControlPoint, blank=True, related_name='actions')
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

    def get_associated(self):
        conformities = list(self.associated_conformity.all())
        findings = list(self.associated_findings.all())
        control_points = list(self.associated_controlPoints.all())

        return conformities + findings + control_points


    def is_in_progress(self) -> bool:
        return self.status in (
            Action.Status.ANALYSING,
            Action.Status.PLANNING,
            Action.Status.IMPLEMENTING,
            Action.Status.CONTROLLING,
        )

    def is_completed(self) -> bool:
        return self.status == Action.Status.ENDED

    def save(self, *args, **kwargs):
        """ On save, update timestamps """
        if not self.id:
            self.create_date = timezone.now()
        self.update_date = timezone.now()

        """Update active flag depending on status."""
        if self.status in [Action.Status.FROZEN, Action.Status.ENDED, Action.Status.CANCELED]:
            self.active = False
        else :
            self.active = True

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
    def autoset_mimetype(instance):
        # Read file and set mime_type
        file_content = instance.file.read()
        instance.file.seek(0)
        mime = Magic(mime=True)
        instance.mime_type = mime.from_buffer(file_content)

        # TODO filter on mime type


class Indicator (models.Model):
    """ Indicator used to measure risk level or performance """

    class Frequency(models.IntegerChoices):
        """ List of frequency possible for a control or an indicator"""
        YEARLY = 1, _('Yearly')
        HALFYEARLY = 2, _('Half-Yearly')
        QUARTERLY = 4, _('Quarterly')
        BIMONTHLY = 6, _('Bimonthly')
        MONTHLY = 12, _('Monthly')

    name = models.CharField(max_length=256)
    goal = models.TextField(max_length=4096, blank=True)
    source = models.TextField(max_length=4096, blank=True)
    formula = models.TextField(max_length=4096, blank=True)
    worst = models.IntegerField(default=0)
    best = models.IntegerField(default=100)
    warning = models.IntegerField(default=80)
    critical = models.IntegerField(default=90)
    responsible = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, blank=True, null=True)
    conformity = models.ManyToManyField(Conformity, blank=True)
    frequency = models.IntegerField(
        choices=Frequency.choices,
        default=Frequency.QUARTERLY,
    )

    @staticmethod
    def get_absolute_url():
        """return the absolute URL for Forms, could probably do better"""
        return reverse('conformity:indicator_index')

    def indicator_point_init(self):
        IndicatorPoint.objects.filter(indicator=self).filter(Q(status='SCHD') | Q(status='TOBE')).delete()

        num_cp = self.frequency
        today = date.today()
        start_date = date(today.year, 1, 1)
        delta = timedelta(days=365 // num_cp - 2)
        end_date = start_date + delta
        for _ in range(num_cp):
            period_start_date = date(start_date.year, start_date.month, 1)
            period_end_date = date(end_date.year, end_date.month, monthrange(end_date.year, end_date.month)[1])
            if not IndicatorPoint.objects.filter(indicator=self, period_start_date=period_start_date, period_end_date=period_end_date).exists() :
                IndicatorPoint.objects.create(
                    indicator=self,
                    period_start_date=period_start_date,
                    period_end_date=period_end_date,
                )
            start_date = period_end_date + timedelta(days=1)
            end_date = start_date + delta - timedelta(days=1)

    def get_current_point(self):
        today = timezone.now().date()
        return (
            IndicatorPoint.objects
            .filter(indicator=self, period_start_date__lte=today, period_end_date__gte=today)
            .first()
        )


class IndicatorPoint(models.Model):
    """ Measurement point of an Indicator """

    class Status(models.TextChoices):
        """ List of status possible for a IndicatorPoint"""
        SCHEDULED = 'SCHD', _('Scheduled')
        TOBEEVALUATED = 'TOBE', _('To evaluate')
        COMPLIANT = 'OK', _('Compliant')
        WARNING = 'WARN', _('Warning')
        CRITICAL = 'CRIT', _('Critical')
        MISSED = 'MISS', _('Missed')

    indicator = models.ForeignKey(Indicator, on_delete=models.CASCADE, null=True, blank=True)
    control_date = models.DateTimeField(blank=True, null=True)
    control_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    period_start_date = models.DateField()
    period_end_date = models.DateField()
    status = models.CharField(choices=Status.choices, max_length=4, default=Status.SCHEDULED)
    comment = models.TextField(max_length=4096, blank=True)
    value = models.IntegerField(null=True)
    attachment = models.ManyToManyField('Attachment', blank=True, related_name='IndicatorPoint')

    @staticmethod
    def get_absolute_url():
        """return the absolute URL for Forms, could probably do better"""
        return reverse('conformity:indicator_index')

    def status_update(self):
        """ This function update the status depending on the value and the Indicator configuration """
        if not self.value:
            return

        if self.indicator.best > self.indicator.worst :
            if self.indicator.best >= self.value > self.indicator.warning :
                self.status = IndicatorPoint.Status.COMPLIANT
            elif self.indicator.warning >= self.value > self.indicator.critical :
                self.status = IndicatorPoint.Status.WARNING
            elif self.indicator.critical >= self.value >= self.indicator.worst :
                self.status = IndicatorPoint.Status.CRITICAL
            else:
                self.status = IndicatorPoint.Status.MISSED

        elif self.indicator.best < self.indicator.worst :
            if self.indicator.best <= self.value < self.indicator.warning :
                self.status = IndicatorPoint.Status.COMPLIANT
            elif self.indicator.warning <= self.value < self.indicator.critical :
                self.status = IndicatorPoint.Status.WARNING
            elif self.indicator.critical <= self.value <= self.indicator.worst :
                self.status = IndicatorPoint.Status.CRITICAL
            else:
                self.status = IndicatorPoint.Status.MISSED

        else:
            self.status = IndicatorPoint.Status.MISSED
