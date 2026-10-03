"""
Conformity module manage all the manual declarative aspect of conformity management.
It's Organized around Organization, Framework, Requirement and Conformity classes.
"""
# Standard library
from calendar import monthrange
from datetime import date, datetime, time, timedelta
from typing import List, Literal, Tuple

# Django (third-party)
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# Third-party
from mptt.models import MPTTModel, TreeForeignKey
from pycountry import languages

User = get_user_model()


def language_choices():
    """Resolve language labels when the form is built, not in migration state."""
    return [(lang.alpha_2, lang.name) for lang in languages if hasattr(lang, 'alpha_2')]


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
            return language_choices()

    objects = FrameworkManager()
    name = models.CharField(max_length=256, unique=True)
    version = models.IntegerField(default=0)
    publish_by = models.CharField(max_length=256)
    type = models.CharField(max_length=5, choices=Type.choices, default=Type.OTHER)
    attachment = models.ManyToManyField('Attachment', blank=True, related_name='frameworks')
    language = models.CharField(max_length=2, choices=language_choices, default='en')

    class Meta:
        ordering = ['name']
        verbose_name = 'framework'
        verbose_name_plural = 'frameworks'

    def __str__(self):
        return str(self.name)

    def natural_key(self):
        return self.name

    def get_type(self):
        """return the readable version of the Framework Type"""
        return self.type_label

    @property
    def type_label(self):
        return self.get_type_display()

    def get_requirements(self):
        """return all non-root requirements for this framework"""
        return (Requirement.objects
                .filter(framework=self)
                .exclude(parent__isnull=True)
                .order_by('tree_id', 'lft'))

    def get_requirements_number(self):
        """Return the number of leaf requirements in this framework."""
        return sum(1 for requirement in self.requirements.all() if requirement.is_leaf_node())

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

    def remove_conformity(self, framework):
        """Explicitly remove a framework and its assessments."""
        from .services.conformities import unapply_framework
        unapply_framework(self, framework)

    def add_conformity(self, framework):
        """Explicitly apply a framework and create missing assessments."""
        from .services.conformities import apply_framework
        apply_framework(self, framework)


class RequirementQuerySet(models.QuerySet):
    """Common requirement queries used by framework views and services."""

    def for_framework(self, framework):
        return self.filter(framework=framework)

    def roots(self):
        return self.filter(parent__isnull=True)

    def in_tree_order(self):
        return self.order_by('tree_id', 'lft')

    def with_tree_relations(self):
        return self.select_related('framework').prefetch_related('children')


class RequirementManager(models.Manager.from_queryset(RequirementQuerySet)):
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
    framework = models.ForeignKey(Framework, on_delete=models.CASCADE, related_name='requirements')
    parent = TreeForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    title = models.CharField(max_length=256, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['framework', 'code'],
                condition=Q(parent__isnull=True),
                name='uq_req_root_code',
            ),
            models.UniqueConstraint(
                fields=['framework', 'parent', 'code'],
                condition=Q(parent__isnull=False),
                name='uq_req_sibling_code',
            ),
        ]

    class MPTTMeta:
        order_insertion_by = ['order']

    def __str__(self):
        return str(self.name) + ": " + str(self.title)

    def natural_key(self):
        return self.name

    natural_key.dependencies = ['conformity.framework']

    def get_parent(self):
        return self.get_ancestors().last()

    @property
    def full_path(self):
        """Display the path without relying on the stored hierarchical name."""
        return "-".join(node.code or node.name for node in (*self.get_ancestors(), self))

    @property
    def has_children(self):
        return self.children.exists()


class ConformityQuerySet(models.QuerySet):
    """Common conformity queries for the dashboard and framework views."""

    def applicable(self):
        return self.filter(applicable=True)

    def for_organization(self, organization):
        return self.filter(organization=organization)

    def for_framework(self, framework):
        return self.filter(requirement__framework=framework)

    def roots(self):
        return self.filter(requirement__level=0)

    def with_related(self):
        return self.select_related('organization', 'requirement__framework')


class EvidenceQuerySet(models.QuerySet):
    """Queries implementing Evidence validity plus temporary legacy period aliases."""

    @staticmethod
    def _rewrite_period_lookup(key, value):
        if key.startswith('period_start_date'):
            suffix = key[len('period_start_date'):]
            date_lookups = {'', '__lt', '__lte', '__gt', '__gte', '__range', '__in'}
            if suffix in date_lookups:
                return f'valid_from__date{suffix}', value
            return f'valid_from{suffix}', value

        if key.startswith('period_end_date'):
            suffix = key[len('period_end_date'):]
            if suffix == '':
                return 'valid_to__date', value + timedelta(days=1)
            if suffix == '__lt':
                return 'valid_to__date__lte', value
            if suffix == '__lte':
                return 'valid_to__date__lte', value + timedelta(days=1)
            if suffix == '__gt':
                return 'valid_to__date__gt', value + timedelta(days=1)
            if suffix == '__gte':
                return 'valid_to__date__gte', value + timedelta(days=1)
            return f'valid_to{suffix}', value
        return key, value

    @classmethod
    def _rewrite_period_kwargs(cls, kwargs):
        return dict(cls._rewrite_period_lookup(key, value) for key, value in kwargs.items())

    def _filter_or_exclude(self, negate, args, kwargs):
        return super()._filter_or_exclude(negate, args, self._rewrite_period_kwargs(kwargs))

    def order_by(self, *field_names):
        rewritten = []
        for field_name in field_names:
            prefix = '-' if field_name.startswith('-') else ''
            name = field_name[1:] if prefix else field_name
            if name == 'period_start_date':
                name = 'valid_from'
            elif name == 'period_end_date':
                name = 'valid_to'
            rewritten.append(prefix + name)
        return super().order_by(*rewritten)

    def values_list(self, *fields, **kwargs):
        """Expose legacy period names in projection queries during transition."""
        annotations = {}
        rewritten = []
        for index, field in enumerate(fields):
            if field == 'period_start_date':
                alias = f'_legacy_period_start_{index}'
                annotations[alias] = TruncDate('valid_from')
                rewritten.append(alias)
            elif field == 'period_end_date':
                alias = f'_legacy_period_end_{index}'
                annotations[alias] = TruncDate(
                    models.ExpressionWrapper(
                        models.F('valid_to') - timedelta(microseconds=1),
                        output_field=models.DateTimeField(),
                    )
                )
                rewritten.append(alias)
            else:
                rewritten.append(field)

        queryset = self.annotate(**annotations) if annotations else self
        return models.QuerySet.values_list(queryset, *rewritten, **kwargs)

    def valid_at(self, at=None):
        at = at or timezone.now()
        return self.filter(valid_from__lte=at).filter(
            Q(valid_to__isnull=True) | Q(valid_to__gt=at)
        )

    def current(self):
        return self.valid_at()

    def operational(self):
        return self.exclude(source_type=Evidence.SourceType.HUMAN)


class Evidence(models.Model):
    """A time-bound fact which can contribute to one or more assessments.

    Validity uses a half-open interval: ``valid_from <= at < valid_to``.
    A null ``valid_to`` means that no end of validity is currently known.
    Evidence never references other evidence.
    """

    class Result(models.TextChoices):
        POSITIVE = 'POS', _('Positive')
        NEGATIVE = 'NEG', _('Negative')
        NEUTRAL = 'NEU', _('Neutral / inconclusive')
        PARTIAL = 'PAR', _('Partially compliant')

    class SourceType(models.TextChoices):
        CONTROL = 'CTRL', _('Periodic control')
        INDICATOR = 'IND', _('Periodic indicator')
        HUMAN = 'HUM', _('Expert assessment')
        FINDING = 'FIND', _('Finding')
        DOCUMENT = 'DOC', _('Document')
        GENERIC = 'MAN', _('Evidence')

    class Status(models.TextChoices):
        SCHEDULED = 'SCHD', _('Scheduled')
        TOBEEVALUATED = 'TOBE', _('To evaluate')
        EVALUATED = 'EVAL', _('Evaluated')
        MISSED = 'MISS', _('Missed')

    source_type = models.CharField(
        max_length=4,
        choices=SourceType.choices,
        default=SourceType.GENERIC,
    )
    title = models.CharField(max_length=256, blank=True)
    status = models.CharField(choices=Status.choices, max_length=4, default=Status.SCHEDULED)
    result = models.CharField(max_length=3, choices=Result.choices, default=Result.NEUTRAL)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField(null=True, blank=True)
    evaluated_at = models.DateTimeField(null=True, blank=True)
    evaluator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='evaluated_evidence',
    )
    comment = models.TextField(max_length=4096, blank=True)
    conformities = models.ManyToManyField('Conformity', blank=True, related_name='evidence')
    attachments = models.ManyToManyField('Attachment', blank=True, related_name='evidence')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    result_updated_at = models.DateTimeField(default=timezone.now)

    objects = EvidenceQuerySet.as_manager()

    class Meta:
        ordering = ['-valid_from', '-pk']
        constraints = [
            models.CheckConstraint(
                condition=Q(valid_to__isnull=True) | Q(valid_to__gt=models.F('valid_from')),
                name='chk_evidence_positive_validity',
            ),
        ]

    @staticmethod
    def _day_start(value):
        naive = datetime.combine(value, time.min)
        return timezone.make_aware(naive, timezone.get_current_timezone())

    @property
    def period_start_date(self):
        return timezone.localtime(self.valid_from).date() if self.valid_from else None

    @period_start_date.setter
    def period_start_date(self, value):
        if value is not None:
            self.valid_from = self._day_start(value)

    @property
    def period_end_date(self):
        if not self.valid_to:
            return None
        return (timezone.localtime(self.valid_to) - timedelta(microseconds=1)).date()

    @period_end_date.setter
    def period_end_date(self, value):
        if value is not None:
            self.valid_to = self._day_start(value + timedelta(days=1))

    @property
    def control_date(self):
        return self.evaluated_at

    @control_date.setter
    def control_date(self, value):
        self.evaluated_at = value

    @property
    def control_user(self):
        return self.evaluator

    @control_user.setter
    def control_user(self, value):
        self.evaluator = value

    @property
    def attachment(self):
        return self.attachments

    def update_schedule_status(self):
        """Update the shared Evidence lifecycle from its validity window."""
        if self.status == self.Status.EVALUATED:
            return
        today = date.today()
        if self.period_end_date and self.period_end_date < today:
            self.status = self.Status.MISSED
        elif (
            self.period_start_date
            and self.period_end_date
            and self.period_start_date <= today <= self.period_end_date
        ):
            self.status = self.Status.TOBEEVALUATED
        else:
            self.status = self.Status.SCHEDULED

    def clean(self):
        super().clean()
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValidationError({'valid_to': _('Validity end must be after validity start.')})

    @property
    def periodic_point(self):
        """Return the concrete periodic Evidence subtype, when applicable."""
        accessor = {
            self.SourceType.CONTROL: 'controlpoint',
            self.SourceType.INDICATOR: 'indicatorpoint',
        }.get(self.source_type)
        if accessor is None:
            return None
        try:
            return getattr(self, accessor)
        except ObjectDoesNotExist:
            return None

    @property
    def periodic_name(self):
        point = self.periodic_point
        if isinstance(point, ControlPoint) and point.control_id:
            return point.control.title
        if isinstance(point, IndicatorPoint) and point.indicator_id:
            return point.indicator.name
        return ''

    @property
    def display_name(self):
        """Human-readable source name for Evidence list views."""
        if self.source_type == self.SourceType.CONTROL:
            point = self.periodic_point
            return point.control.title if point and point.control_id else _('Control evidence')
        if self.source_type == self.SourceType.INDICATOR:
            point = self.periodic_point
            return point.indicator.name if point and point.indicator_id else _('Indicator evidence')
        if self.source_type == self.SourceType.HUMAN:
            return _('Expert assessment')
        if self.source_type == self.SourceType.GENERIC:
            return self.title or _('Evidence')
        if self.source_type == self.SourceType.DOCUMENT:
            try:
                document = getattr(self, 'documentevidence')
                return document.title or str(document.document)
            except ObjectDoesNotExist:
                return _('Document')
        if self.source_type == self.SourceType.FINDING:
            try:
                return getattr(self, 'finding').short_description
            except ObjectDoesNotExist:
                return _('Audit finding')
        return self.get_source_type_display()

    @property
    def display_icon(self):
        return {
            self.SourceType.CONTROL: 'bi-clipboard2-check',
            self.SourceType.INDICATOR: 'bi-speedometer',
            self.SourceType.HUMAN: 'bi-person-check',
            self.SourceType.GENERIC: 'bi-pencil-square',
            self.SourceType.DOCUMENT: 'bi-file-earmark-check',
            self.SourceType.FINDING: 'bi-exclamation-diamond',
        }.get(self.source_type, 'bi-journal-check')

    @property
    def periodic_organization(self):
        point = self.periodic_point
        if isinstance(point, ControlPoint) and point.control_id:
            target = point.control.conformity.select_related('organization').first()
            return target.organization if target else None
        if isinstance(point, IndicatorPoint) and point.indicator_id:
            target = point.indicator.conformity.select_related('organization').first()
            return target.organization if target else None
        return None

    @property
    def periodic_level(self):
        point = self.periodic_point
        if isinstance(point, ControlPoint) and point.control_id:
            return point.control.get_level_display()
        return '—'

    @property
    def periodic_frequency(self):
        point = self.periodic_point
        if isinstance(point, ControlPoint) and point.control_id:
            return point.control.get_frequency_display()
        if isinstance(point, IndicatorPoint) and point.indicator_id:
            return point.indicator.get_frequency_display()
        return '—'

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        previous = None
        if self.pk:
            previous = Evidence.objects.filter(pk=self.pk).values(
                'result', 'valid_from', 'valid_to'
            ).first()

        self._evidence_semantic_change = previous is None or (
            previous['result'] != self.result
            or previous['valid_from'] != self.valid_from
            or previous['valid_to'] != self.valid_to
        )

        if previous is not None and previous['result'] != self.result:
            self.result_updated_at = timezone.now()
            if update_fields is not None:
                kwargs['update_fields'] = [*update_fields, 'result_updated_at']
        return super().save(*args, **kwargs)

    def is_valid_at(self, at=None):
        at = at or timezone.now()
        return self.valid_from <= at and (self.valid_to is None or at < self.valid_to)

    def __str__(self):
        return f'{self.get_source_type_display()}: {self.get_result_display()}'


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
        EVIDENCE = 'EVID', _('From evidence')

    class EvidenceState(models.TextChoices):
        NOT_EVALUATED = 'NONE', _('Not evaluated')
        COMPLIANT = 'COMP', _('Compliant')
        PARTIAL = 'PART', _('Partially compliant')
        NON_COMPLIANT = 'NONC', _('Non-compliant')
        INCONCLUSIVE = 'INCO', _('Inconclusive')

    objects = ConformityQuerySet.as_manager()
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, related_name='conformities')
    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE, null=True, related_name='conformities')
    applicable = models.BooleanField(default=True)
    responsible = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    comment = models.TextField(max_length=4096, blank=True)
    status = models.IntegerField(default=None, validators=[MinValueValidator(0), MaxValueValidator(100)], null=True, blank=True)
    status_last_update = models.DateTimeField(null=True, blank=True)
    status_justification = models.CharField(
        max_length=4,
        choices=StatusJustification.choices,
        default=StatusJustification.EXPERT,
        blank=True,
    )
    evidence_state = models.CharField(
        max_length=4, choices=EvidenceState.choices,
        default=EvidenceState.NOT_EVALUATED,
    )

    class Meta:
        ordering = ['organization', 'requirement__framework', 'requirement__tree_id', 'requirement__lft']
        verbose_name = 'conformity'
        verbose_name_plural = 'conformities'
        constraints = [
            models.UniqueConstraint(fields=['organization', 'requirement'], name='uq_conformity_org_req'),
            models.CheckConstraint(
                condition=Q(status__isnull=True) | (Q(status__gte=0) & Q(status__lte=100)),
                name='chk_conformity_status_0_100',
            ),
        ]

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
        total = len(leaves)
        if total == 0:
            return 0

        complete = sum(1 for conformity in leaves if conformity.status is not None)
        return round((complete / total) * 100)

    def get_evidence_state_distribution(self):
        """Return categorical leaf status counts and percentages for summary bars."""
        leaves = [item for item in self.get_leaf() if item.applicable]
        total = len(leaves)

        counts = {
            self.EvidenceState.COMPLIANT: 0,
            self.EvidenceState.PARTIAL: 0,
            self.EvidenceState.NON_COMPLIANT: 0,
            self.EvidenceState.INCONCLUSIVE: 0,
            self.EvidenceState.NOT_EVALUATED: 0,
        }
        for item in leaves:
            counts[item.evidence_state] = counts.get(item.evidence_state, 0) + 1

        def percentage(state):
            if total == 0:
                return 0
            return round((counts[state] / total) * 100, 2)

        return {
            'total': total,
            'compliant_count': counts[self.EvidenceState.COMPLIANT],
            'partial_count': counts[self.EvidenceState.PARTIAL],
            'non_compliant_count': counts[self.EvidenceState.NON_COMPLIANT],
            'inconclusive_count': counts[self.EvidenceState.INCONCLUSIVE],
            'not_evaluated_count': counts[self.EvidenceState.NOT_EVALUATED],
            'compliant_pct': percentage(self.EvidenceState.COMPLIANT),
            'partial_pct': percentage(self.EvidenceState.PARTIAL),
            'non_compliant_pct': percentage(self.EvidenceState.NON_COMPLIANT),
            'inconclusive_pct': percentage(self.EvidenceState.INCONCLUSIVE),
        }

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
        """Return controls configured to target this requirement."""
        return Control.objects.filter(conformity=self)

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
        if negative_only:
            items = self._get_negative_related(include_actions, include_controls)
        else:
            items = self._get_related(include_actions, include_controls, only_active)
        return self._sort_related(items, sort)

    def _get_related(self, include_actions, include_controls, only_active):
        items = []
        if include_actions:
            actions = self.actions.filter(active=True) if only_active else self.actions.all()
            items.extend(("action", action) for action in actions)
        if include_controls:
            items.extend(("control", control) for control in self.get_control())
        return items

    def _get_negative_related(self, include_actions, include_controls):
        items = []
        if include_actions:
            statuses = [
                Action.Status.ANALYSING, Action.Status.PLANNING,
                Action.Status.IMPLEMENTING, Action.Status.CONTROLLING,
            ]
            items.extend(("action", action) for action in self.actions.filter(status__in=statuses))
        if include_controls:
            today = date.today()
            points = ControlPoint.objects.filter(
                conformities=self,
                valid_from__date__lte=today,
                valid_to__date__gt=today,
            ).filter(
                Q(result=Evidence.Result.NEGATIVE)
                | Q(status__in=[Evidence.Status.MISSED, Evidence.Status.SCHEDULED, Evidence.Status.TOBEEVALUATED])
            )
            items.extend(("controlpoint", point) for point in points)
        return items

    @staticmethod
    def _related_label(obj):
        return (
            getattr(obj, "title", None)
            or getattr(obj, "name", None)
            or getattr(obj, "short_description", None)
            or str(obj)
        )

    @classmethod
    def _sort_related(cls, items, sort):
        if sort == "type_then_title":
            order_kind = {"action": 0, "control": 1, "controlpoint": 2}
            items.sort(key=lambda item: (order_kind.get(item[0], 99), cls._related_label(item[1])))
        elif sort == "recent_first":
            items.sort(
                key=lambda item: (
                    getattr(item[1], "update_date", None)
                    or getattr(item[1], "period_end_date", None)
                    or date.min,
                    cls._related_label(item[1]),
                ),
                reverse=True,
            )
        elif sort == "alpha":
            items.sort(key=lambda item: cls._related_label(item[1]))
        return items

    def update_responsible(self):
        """Update the responsible in the descendants when added"""
        from .services.audit import update_with_audit
        update_with_audit(Conformity.objects.filter(
            organization=self.organization,
            requirement__in=self.requirement.get_descendants()
        ), responsible=self.responsible)

    def update_status(self):
        """Update this node's conformity status and propagate update to its parent."""
        from .services.conformities import recompute_parent_chain
        recompute_parent_chain(self)

    def update_applicable(self):
        """Explicit API for callers that intentionally propagate applicability."""
        from .services.conformities import propagate_applicable_and_comment
        propagate_applicable_and_comment(self, self.applicable)

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

    def evaluate_evidence(self, at=None, *, persist=True):
        """Evaluate this Conformity through the shared Evidence engine."""
        from .services.evidence import evaluate_conformity
        return evaluate_conformity(self, at=at, persist=persist)

    def _persist_evidence_state(self, state, at):
        state_to_status = {
            self.EvidenceState.COMPLIANT: 100,
            self.EvidenceState.PARTIAL: 50,
            self.EvidenceState.NON_COMPLIANT: 0,
        }
        updates = []
        if self.evidence_state != state:
            self.evidence_state = state
            updates.append('evidence_state')
        if self.requirement.is_leaf_node() and state in state_to_status:
            value = state_to_status[state]
            if self.status != value or self.status_justification != self.StatusJustification.EVIDENCE:
                self.status = value
                self.status_justification = self.StatusJustification.EVIDENCE
                self.status_last_update = at
                updates.extend(['status', 'status_justification', 'status_last_update'])
        elif (
            self.requirement.is_leaf_node()
            and self.status_justification == self.StatusJustification.EVIDENCE
            and self.status is not None
        ):
            self.status = None
            self.status_last_update = at
            updates.extend(['status', 'status_last_update'])
        if updates:
            self.save(update_fields=list(dict.fromkeys(updates)))


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

    @property
    def type_label(self):
        """return the readable version of the Audit Type"""
        return self.Type(self.type).label

    def get_type(self):
        """Keep the existing template and Python API available."""
        return self.type_label

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


class Finding(Evidence):
    """An audit finding represented directly as Evidence."""

    class Severity(models.TextChoices):
        """Nature and gravity of an audit finding."""
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
    audit = models.ForeignKey(
        Audit, on_delete=models.SET_NULL, null=True, blank=True
    )
    severity = models.CharField(
        max_length=5,
        choices=Severity.choices,
        default=Severity.OBSERVATION,
    )
    cvss = models.FloatField('CVSS', blank=True, null=True, default=None)
    cvss_descriptor = models.CharField('CVSS Vector', max_length=256, blank=True)

    class Meta:
        ordering = ['severity']

    def clean(self):
        if self.cvss is not None and (self.cvss < 0.0 or self.cvss > 10.0):
            raise ValidationError('CVSS must be between 0 and 10.')
        super().clean()

    def result_from_severity(self):
        if self.severity == self.Severity.POSITIVE:
            return Evidence.Result.POSITIVE
        if self.severity in {
            self.Severity.CRITICAL,
            self.Severity.MAJOR,
            self.Severity.MINOR,
        }:
            return Evidence.Result.NEGATIVE
        return Evidence.Result.NEUTRAL

    @staticmethod
    def _plus_years(value, years):
        try:
            return value.replace(year=value.year + years)
        except ValueError:
            return value.replace(month=2, day=28, year=value.year + years)

    def _default_valid_from(self):
        return timezone.now()

    def save(self, *args, **kwargs):
        creating = self._state.adding
        if not self.valid_from:
            self.valid_from = self._default_valid_from()
        if creating and self.valid_to is None:
            self.valid_to = self._plus_years(self.valid_from, 3)
        self.source_type = Evidence.SourceType.FINDING
        self.status = Evidence.Status.EVALUATED
        self.result = self.result_from_severity()

        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.update({'source_type', 'status', 'result'})
            if 'audit' in update_fields or 'audit_id' in update_fields:
                update_fields.add('valid_from')
            kwargs['update_fields'] = update_fields

        return super().save(*args, **kwargs)

    def __str__(self):
        return str(self.short_description)

    def get_severity(self):
        return self.severity_label

    @property
    def severity_label(self):
        return self.get_severity_display()

    def get_absolute_url(self):
        return reverse('conformity:finding_detail', kwargs={'pk': self.id})

    def get_action(self):
        return Action.objects.filter(associated_findings=self.id)

    def is_active(self, at=None) -> bool:
        return (
            self.severity != self.Severity.POSITIVE
            and self.is_valid_at(at)
        )

    def close_if_actions_completed(self, at=None):
        """Invalidate the finding once it has actions and none remains active.

        This is intentionally monotone: reopening an Action does not erase an
        explicit/manual or previously recorded validity end.
        """
        at = at or timezone.now()
        if self.valid_to is not None and self.valid_to <= at:
            return False
        aggregate = self.actions.aggregate(
            total=Count('pk'),
            active=Count('pk', filter=Q(active=True)),
        )
        if (aggregate['total'] or 0) == 0 or (aggregate['active'] or 0) > 0:
            return False
        self.valid_to = at
        self.save(update_fields=['valid_to'])
        return True


class Control(models.Model):
    """
    Control class represent the periodic control needed to verify the security and the effectiveness of the security requirement.
    """

    class Frequency(models.IntegerChoices):
        """ List of frequency possible for a control"""
        YEARLY = 1, _('Yearly')
        HALFYEARLY = 2, _('Half-Yearly')
        QUARTERLY = 4, _('Quarterly')
        BIMONTHLY = 6, _('Bimonthly')
        MONTHLY = 12, _('Monthly')

    class Level(models.IntegerChoices):
        """ List of control level possible for a control """
        FIRST = 1, _('1st level')
        SECOND = 2, _('2nd level')

    title = models.CharField(max_length=256)
    description = models.TextField(max_length=4096, blank=True)
    conformity = models.ManyToManyField(Conformity, blank=True, related_name="controls")
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
        return self.title

    @staticmethod
    def get_absolute_url():
        """return the absolute URL for Forms, could probably do better"""
        return reverse('conformity:control_index')

    @staticmethod
    def controlpoint_bootstrap(instance):
        from .services.controls import generate_controlpoints
        generate_controlpoints(instance, year=date.today().year)


    def get_controlpoint(self):
        """Return all control point based on this control"""
        return ControlPoint.objects.filter(control=self).order_by('valid_from')


    @property
    def periodic_kind(self):
        return Evidence.SourceType.CONTROL

    @property
    def periodic_name(self):
        return self.title

    @property
    def periodic_type(self):
        return _('Control')

    @property
    def periodic_level(self):
        return self.get_level_display()

    @property
    def periodic_frequency(self):
        return self.get_frequency_display()

    @property
    def periodic_point(self):
        points = getattr(self, 'periodic_points', None)
        if points is None:
            points = list(
                self.get_controlpoint().order_by('-valid_from', '-pk')
            )
        today = timezone.localdate()
        return next(
            (point for point in points if point.period_start_date <= today <= point.period_end_date),
            points[0] if points else None,
        )

    @property
    def organization_sort(self):
        """Stable display/sort key derived from configured Conformities."""
        return ', '.join(sorted({
            str(conformity.organization)
            for conformity in self.conformity.select_related('organization').all()
        }))

    @property
    def periodic_result_sort(self):
        point = self.periodic_point
        return point.status if point is not None else ''

class ControlPoint(Evidence):
    """A periodic control result represented directly as Evidence."""

    control = models.ForeignKey(Control, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        ordering = ['valid_to']

    @staticmethod
    def get_absolute_url():
        return reverse('conformity:control_index')

    @staticmethod
    def update_status(instance):
        if instance.status != Evidence.Status.EVALUATED:
            instance.update_schedule_status()

    def save(self, *args, **kwargs):
        self.source_type = Evidence.SourceType.CONTROL
        if self.result != Evidence.Result.NEUTRAL:
            self.status = Evidence.Status.EVALUATED
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            update_fields = set(update_fields)
            if 'status' in update_fields:
                update_fields.update({'result', 'source_type'})
            kwargs['update_fields'] = update_fields
        return super().save(*args, **kwargs)

    def __str__(self):
        if not self.control:
            return super().__str__()
        start = self.period_start_date
        end = self.period_end_date
        return (
            f"{self.control.title} "
            f"({start.strftime('%b-%Y') if start else '?'}⇒{end.strftime('%b-%Y') if end else '?'})"
        )

    def get_action(self):
        return Action.objects.filter(associated_controlPoints=self)

    def is_current_period(self, when: date | None = None) -> bool:
        when = when or date.today()
        return bool(
            self.period_start_date
            and self.period_end_date
            and self.period_start_date <= when <= self.period_end_date
        )

    def is_final_status(self) -> bool:
        return self.status == Evidence.Status.EVALUATED


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

    class Priority(models.IntegerChoices):
        """Business priority, from most important (1) to least important (5)."""
        PRIORITY_1 = 1, _('Priority 1')
        PRIORITY_2 = 2, _('Priority 2')
        PRIORITY_3 = 3, _('Priority 3')
        PRIORITY_4 = 4, _('Priority 4')
        PRIORITY_5 = 5, _('Priority 5')

    PRIORITY_REQUIRED_STATUSES = frozenset({
        Status.PLANNING,
        Status.IMPLEMENTING,
        Status.CONTROLLING,
    })

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
    priority = models.PositiveSmallIntegerField(choices=Priority.choices, null=True, blank=True)
    description = models.TextField(max_length=4096, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, blank=True, null=True)
    associated_conformity = models.ManyToManyField(Conformity, blank=True, related_name='actions')
    associated_findings = models.ManyToManyField(Finding, blank=True, related_name='actions')
    associated_controlPoints = models.ManyToManyField(ControlPoint, blank=True, related_name='actions')

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

    def validate_priority_transition(self, update_fields=None):
        """Enforce priority when an Action leaves Analysis for the active workflow."""
        previous = None
        if self.pk:
            previous = (
                Action.objects
                .filter(pk=self.pk)
                .values('status', 'priority')
                .first()
            )

        effective_status = self.status
        effective_priority = self.priority
        if previous is not None and update_fields is not None:
            if 'status' not in update_fields:
                effective_status = previous['status']
            if 'priority' not in update_fields:
                effective_priority = previous['priority']

        try:
            cleaned_priority = self._meta.get_field('priority').clean(
                effective_priority,
                self,
            )
        except ValidationError as exc:
            raise ValidationError({'priority': exc}) from exc

        if update_fields is None or 'priority' in update_fields:
            self.priority = cleaned_priority

        # New objects have not transitioned from Analysis. This preserves
        # compatibility with existing paths that create non-Analysis Actions
        # directly, while transition validation still applies to persisted rows.
        if previous is None:
            return

        if (
            previous['status'] == Action.Status.ANALYSING
            and effective_status in Action.PRIORITY_REQUIRED_STATUSES
            and cleaned_priority is None
        ):
            raise ValidationError({
                'priority': _('Priority is required before leaving the Analysis phase.')
            })

        # Legacy rows that were already outside Analysis with NULL priority stay
        # editable. Once a priority has been established, it cannot be cleared
        # while the Action remains in an active post-Analysis workflow state.
        if (
            previous['priority'] is not None
            and cleaned_priority is None
            and effective_status in Action.PRIORITY_REQUIRED_STATUSES
        ):
            raise ValidationError({
                'priority': _('Priority is required in post-Analysis workflow states.')
            })

    def clean(self):
        super().clean()
        self.validate_priority_transition()

    def save(self, *args, **kwargs):
        """ On save, update timestamps """
        self.validate_priority_transition(update_fields=kwargs.get('update_fields'))
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
    sha256 = models.CharField(max_length=64, unique=True, null=True, blank=True, editable=False)
    create_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-create_date', 'file']

    def __str__(self):
        return self.file.name.split("/")[1]

    def clean(self):
        super().clean()
        if self.file and not self.sha256:
            from .validators import validate_attachment_once
            self.mime_type, self.sha256 = validate_attachment_once(self.file)

    def save(self, *args, **kwargs):
        # Enforce the upload policy for every Attachment persistence path,
        # including direct ORM creation outside ModelForms.
        self.full_clean()
        return super().save(*args, **kwargs)

    @classmethod
    def get_or_create_for_upload(cls, uploaded_file):
        """Validate an upload and reuse an existing identical attachment when possible."""
        from .validators import validate_attachment_once

        mime_type, checksum = validate_attachment_once(uploaded_file)
        existing = cls.objects.filter(sha256=checksum).first()
        if existing:
            return existing, False

        attachment = cls(file=uploaded_file, mime_type=mime_type, sha256=checksum)
        attachment.save()
        return attachment, True

    def calculate_checksum_and_merge(self):
        """Calculate a missing checksum and merge this attachment into an existing duplicate."""
        if self.sha256:
            return self, False

        from .validators import validate_attachment_once

        mime_type, checksum = validate_attachment_once(self.file)
        existing = type(self).objects.filter(sha256=checksum).exclude(pk=self.pk).first()
        if not existing:
            self.mime_type = mime_type
            self.sha256 = checksum
            self.save(update_fields=['mime_type', 'sha256'])
            return self, False

        for relation in self._meta.related_objects:
            if not relation.many_to_many:
                continue
            source_manager = getattr(self, relation.get_accessor_name())
            target_manager = getattr(existing, relation.get_accessor_name())
            target_manager.add(*source_manager.all())

        duplicate_file = self.file
        self.delete()
        duplicate_file.delete(save=False)
        return existing, True



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
    critical = models.IntegerField(default=20)
    responsible = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    conformity = models.ManyToManyField(Conformity, blank=True)
    frequency = models.IntegerField(
        choices=Frequency.choices,
        default=Frequency.QUARTERLY,
    )

    @staticmethod
    def get_absolute_url():
        """return the absolute URL for Forms, could probably do better"""
        return reverse('conformity:indicator_index')

    @property
    def value_bounds(self):
        """Inclusive numeric bounds, also for indicators where lower is better."""
        return min(self.worst, self.best), max(self.worst, self.best)

    @property
    def direction_label(self):
        """Human-readable direction of improvement for the indicator."""
        if self.best > self.worst:
            return _('Higher is better')
        if self.best < self.worst:
            return _('Lower is better')
        return _('Invalid scale')

    @property
    def threshold_ranges(self):
        """Inclusive integer ranges matching IndicatorPoint.status_update()."""
        ascending = self.worst < self.critical < self.warning < self.best
        descending = self.worst > self.critical > self.warning > self.best
        if ascending:
            ranges = (
                (_('Critical'), 'text-danger', self.worst, self.critical),
                (_('Warning'), 'text-warning', self.critical + 1, self.warning),
                (_('Compliant'), 'text-success', self.warning + 1, self.best),
            )
        elif descending:
            ranges = (
                (_('Critical'), 'text-danger', self.worst, self.critical),
                (_('Warning'), 'text-warning', self.critical - 1, self.warning),
                (_('Compliant'), 'text-success', self.warning - 1, self.best),
            )
        else:
            return ()

        return tuple(
            {'label': label, 'css_class': css_class, 'start': start, 'end': end}
            for label, css_class, start, end in ranges
        )

    def validate_thresholds(self):
        """Validate one monotonic threshold scale from worst to best.

        The outer bounds must differ so the scale has a direction. Thresholds
        are strictly ordered so every status band is reachable and the UI
        cannot display overlapping ranges.
        """
        field_names = ('worst', 'critical', 'warning', 'best')
        cleaned = {}
        field_errors = {}
        for field_name in field_names:
            try:
                cleaned[field_name] = self._meta.get_field(field_name).clean(
                    getattr(self, field_name), self
                )
            except ValidationError as exc:
                field_errors[field_name] = exc

        if field_errors:
            raise ValidationError(field_errors)

        for field_name, value in cleaned.items():
            setattr(self, field_name, value)

        if self.worst == self.best:
            raise ValidationError({
                'best': ValidationError(
                    _('Best must differ from worst to define the scale direction.'),
                    code='equal_bounds',
                ),
            })

        if self.best > self.worst:
            valid = self.worst < self.critical < self.warning < self.best
            expected = 'worst < critical < warning < best'
        else:
            valid = self.worst > self.critical > self.warning > self.best
            expected = 'worst > critical > warning > best'

        if not valid:
            error = ValidationError(
                _('Thresholds must follow %(expected)s.'),
                code='invalid_threshold_order',
                params={'expected': expected},
            )
            raise ValidationError({'critical': error, 'warning': error})

    def clean(self):
        super().clean()
        self.validate_thresholds()

    def save(self, *args, **kwargs):
        # ModelForm/admin call clean(); direct model writes need the same guard.
        self.validate_thresholds()
        return super().save(*args, **kwargs)

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
            if not IndicatorPoint.objects.filter(
                indicator=self,
                valid_from__date=period_start_date,
                valid_to__date=period_end_date + timedelta(days=1),
            ).exists():
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
            .filter(indicator=self, valid_from__date__lte=today, valid_to__date__gt=today)
            .first()
        )


    @property
    def periodic_kind(self):
        return Evidence.SourceType.INDICATOR

    @property
    def periodic_name(self):
        return self.name

    @property
    def periodic_type(self):
        return _('Indicator')

    @property
    def periodic_level(self):
        return '—'

    @property
    def periodic_frequency(self):
        return self.get_frequency_display()

    @property
    def periodic_point(self):
        points = getattr(self, 'periodic_points', None)
        if points is None:
            points = list(
                IndicatorPoint.objects
                .filter(indicator=self)
                .order_by('-valid_from', '-pk')
            )
        today = timezone.localdate()
        return next(
            (point for point in points if point.period_start_date <= today <= point.period_end_date),
            points[0] if points else None,
        )


    @property
    def organization_sort(self):
        """Stable display/sort key derived from configured Conformities."""
        return ', '.join(sorted({
            str(conformity.organization)
            for conformity in self.conformity.select_related('organization').all()
        }))

    @property
    def periodic_result_sort(self):
        point = self.periodic_point
        return point.status if point is not None else ''


class IndicatorPoint(Evidence):
    """An Indicator measurement represented directly as Evidence."""

    indicator = models.ForeignKey(Indicator, on_delete=models.CASCADE, null=True, blank=True)
    value = models.IntegerField(null=True)

    @staticmethod
    def get_absolute_url():
        return reverse('conformity:indicator_index')

    def validate_value_bounds(self):
        if self.value is None:
            return
        try:
            self.value = self._meta.get_field('value').clean(self.value, self)
        except ValidationError as exc:
            raise ValidationError({'value': exc}) from exc
        if self.indicator_id is None:
            raise ValidationError({'value': _('A measurement requires an indicator.')})
        lower, upper = self.indicator.value_bounds
        if not lower <= self.value <= upper:
            raise ValidationError({'value': ValidationError(
                _('Enter a value between %(lower)s and %(upper)s (inclusive).'),
                code='out_of_bounds', params={'lower': lower, 'upper': upper},
            )})

    def clean(self):
        super().clean()
        self.validate_value_bounds()

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        self.validate_value_bounds()
        self.result_update()
        self.source_type = Evidence.SourceType.INDICATOR
        if self.value is not None:
            self.status = Evidence.Status.EVALUATED
        if update_fields is not None:
            update_fields = set(update_fields)
            if update_fields & {'value', 'indicator', 'indicator_id'}:
                update_fields.update({'status', 'result'})
            if 'status' in update_fields:
                update_fields.update({'result', 'source_type'})
        return super().save(
            force_insert=force_insert, force_update=force_update,
            using=using, update_fields=update_fields,
        )

    def result_update(self):
        if self.value is None:
            self.update_schedule_status()
            self.result = Evidence.Result.NEUTRAL
            return

        if self.indicator_id is None:
            return

        if self.indicator.best > self.indicator.worst:
            if self.indicator.best >= self.value > self.indicator.warning:
                self.result = Evidence.Result.POSITIVE
            elif self.indicator.warning >= self.value > self.indicator.critical:
                self.result = Evidence.Result.NEUTRAL
            elif self.indicator.critical >= self.value >= self.indicator.worst:
                self.result = Evidence.Result.NEGATIVE
            else:
                self.result = Evidence.Result.NEUTRAL
        elif self.indicator.best < self.indicator.worst:
            if self.indicator.best <= self.value < self.indicator.warning:
                self.result = Evidence.Result.POSITIVE
            elif self.indicator.warning <= self.value < self.indicator.critical:
                self.result = Evidence.Result.NEUTRAL
            elif self.indicator.critical <= self.value <= self.indicator.worst:
                self.result = Evidence.Result.NEGATIVE
            else:
                self.result = Evidence.Result.NEUTRAL
        else:
            self.result = Evidence.Result.NEUTRAL


class HumanEvidence(Evidence):
    """An auditable human arbitration for a Conformity assessment."""

    class Decision(models.TextChoices):
        COMPLIANT = Evidence.Result.POSITIVE, _('Compliant')
        PARTIAL = Evidence.Result.PARTIAL, _('Partially compliant')
        NON_COMPLIANT = Evidence.Result.NEGATIVE, _('Non-compliant')

    decision = models.CharField(max_length=3, choices=Decision.choices)

    def save(self, *args, **kwargs):
        self.source_type = Evidence.SourceType.HUMAN
        self.result = self.decision
        return super().save(*args, **kwargs)


class DocumentEvidence(Evidence):
    """Evidence whose source is an existing documentary attachment."""

    document = models.ForeignKey(
        Attachment, on_delete=models.PROTECT, related_name='document_evidence'
    )
    def save(self, *args, **kwargs):
        self.source_type = Evidence.SourceType.DOCUMENT
        return super().save(*args, **kwargs)
