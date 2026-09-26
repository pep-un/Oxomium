import django_tables2 as tables
from django.utils.html import format_html
from django_tables2.utils import A

from .models import Action, Audit, Conformity, Control, ControlPoint, Finding, Framework, Organization


CENTER = {"cell": {"class": "text-center"}}
PRIMARY_COLUMN = {
    "th": {"class": "col-2 text-start"},
    "td": {"class": "col-2 text-start"},
    "a": {"class": "table-primary-link"},
}


class StatusColumn(tables.Column):
    """Render a model choice status with a Bootstrap icon and contextual color."""

    def __init__(self, styles, **kwargs):
        self.styles = styles
        kwargs.setdefault("order_by", ("status",))
        super().__init__(empty_values=(), **kwargs)

    def render(self, value, record):
        # django-tables2 resolves model choice fields to their display label
        # before calling render(); use the raw model value for style lookup.
        status = record.status
        icon, color = self.styles.get(status, ("bi-hexagon", "text-dark"))
        return format_html(
            '<i class="bi {} {}"></i> {}',
            icon,
            color,
            record.get_status_display(),
        )


class BadgeColumn(tables.Column):
    """Render a value as a Bootstrap badge using a record attribute for styling."""

    def __init__(self, styles, style_accessor, **kwargs):
        self.styles = styles
        self.style_accessor = style_accessor
        super().__init__(empty_values=(), **kwargs)

    def render(self, value, record):
        style = self.styles.get(
            getattr(record, self.style_accessor),
            "text-bg-dark",
        )
        display = value if value not in (None, "") else self.default
        return format_html(
            '<span class="badge rounded-pill {}">{}</span>',
            style,
            display,
        )


class EditColumn(tables.Column):
    """Compact, consistent edit action used by rich tables."""

    def __init__(self, viewname, label, **kwargs):
        self.label = label
        attrs = {
            "cell": {"class": "text-center"},
            "a": {
                "class": "btn btn-sm btn-warning bi bi-pencil-square",
                "title": f"Edit {label}",
            },
        }
        super().__init__(
            accessor="pk",
            empty_values=(),
            orderable=False,
            linkify=(viewname, [A("pk")]),
            attrs=attrs,
            **kwargs,
        )

    def render(self, value):
        return format_html(
            '<span class="visually-hidden">Edit {}</span>',
            self.label,
        )


ACTION_STATUS_STYLES = {
    Action.Status.ANALYSING: ("bi-hexagon-fill", "text-info"),
    Action.Status.PLANNING: ("bi-hexagon-fill", "text-info"),
    Action.Status.IMPLEMENTING: ("bi-hexagon-fill", "text-warning"),
    Action.Status.CONTROLLING: ("bi-hexagon-fill", "text-success"),
    Action.Status.ENDED: ("bi-hexagon-fill", ""),
    Action.Status.FROZEN: ("bi-hexagon", "text-danger"),
    Action.Status.CANCELED: ("bi-hexagon-fill", "text-danger"),
}

CONTROL_POINT_STATUS_STYLES = {
    ControlPoint.Status.SCHEDULED: ("bi-hexagon", "text-dark"),
    ControlPoint.Status.TOBEEVALUATED: ("bi-hexagon-fill", "text-info"),
    ControlPoint.Status.NONCOMPLIANT: ("bi-hexagon-fill", "text-danger"),
    ControlPoint.Status.COMPLIANT: ("bi-hexagon-fill", "text-success"),
    ControlPoint.Status.MISSED: ("bi-hexagon", "text-danger"),
}

FINDING_SEVERITY_STYLES = {
    "CRT": "text-bg-dark",
    "MAJ": "text-bg-danger",
    "MIN": "text-bg-warning",
    "OBS": "text-bg-info",
    "OTHER": "text-bg-dark",
    "POS": "text-bg-success",
}


class BaseRichTable(tables.Table):
    """Shared presentation defaults for sortable, paginated list tables."""

    class Meta:
        attrs = {
            "class": "table table-striped table-hover align-middle",
            "thead": {"class": "table-light"},
        }
        empty_text = "No data to display"


class ActionTable(BaseRichTable):
    title = tables.Column(
        verbose_name="Name",
        linkify=("conformity:action_form", [A("pk")]),
        attrs=PRIMARY_COLUMN,
    )
    owner = tables.Column(default="", attrs={"td": {"class": "text-nowrap"}})
    status = StatusColumn(ACTION_STATUS_STYLES)
    update_date = tables.DateColumn(verbose_name="Last update", format="d-M-Y")
    associations = tables.TemplateColumn(
        verbose_name="Associations",
        template_code="""
            <div class="d-grid gap-1">
                {% if record.conformities_count %}
                    <a href="{% url 'conformity:conformity_index' %}?action={{ record.pk }}"
                       class="btn btn-sm btn-outline-secondary w-75 mx-auto">
                        {{ record.conformities_count }} conformit{{ record.conformities_count|pluralize:"y,ies" }}
                    </a>
                {% endif %}
                {% if record.findings_count %}
                    <a href="{% url 'conformity:finding_index' %}?action={{ record.pk }}"
                       class="btn btn-sm btn-outline-secondary w-75 mx-auto">
                        {{ record.findings_count }} finding{{ record.findings_count|pluralize }}
                    </a>
                {% endif %}
                {% if record.controlpoints_count %}
                    <a href="{% url 'conformity:controlpoint_index' %}?action={{ record.pk }}"
                       class="btn btn-sm btn-outline-secondary w-75 mx-auto">
                        {{ record.controlpoints_count }} control point{{ record.controlpoints_count|pluralize }}
                    </a>
                {% endif %}
            </div>
        """,
        orderable=False,
        attrs=CENTER,
    )

    actions = tables.TemplateColumn(
        verbose_name="Reference",
        template_code="""
            {% if record.reference %}
                <a href="{{ record.reference }}" target="_blank" rel="noopener"
                   class="btn btn-sm btn-secondary bi bi-box-arrow-up-right" title="ITSM Reference link">
                    <span class="visually-hidden">Open ITSM reference</span>
                </a>
            {% endif %}
        """,
        orderable=False,
        attrs=CENTER,
    )

    class Meta(BaseRichTable.Meta):
        model = Action
        fields = ("title", "owner", "status", "update_date")


class AuditTable(BaseRichTable):
    name = tables.Column(
        verbose_name="Name",
        linkify=("conformity:audit_detail", [A("pk")]),
        attrs=PRIMARY_COLUMN,
    )
    auditor = tables.Column()
    type = tables.Column(accessor="get_type_display", verbose_name="Type", order_by=("type",))
    start_date = tables.DateColumn(verbose_name="Start", format="d-M-Y")
    end_date = tables.DateColumn(verbose_name="End", format="d-M-Y")
    findings = tables.TemplateColumn(
        verbose_name="Findings",
        template_code="""
            {% if record.findings_count %}
                <a href="{% url 'conformity:finding_index' %}?audit={{ record.pk }}"
                   class="btn btn-sm btn-outline-secondary w-75 mx-auto">
                    {{ record.findings_count }} finding{{ record.findings_count|pluralize }}
                </a>
            {% endif %}
        """,
        order_by=("findings_count",),
        attrs=CENTER,
    )
    actions = EditColumn("conformity:audit_form", "audit")

    class Meta(BaseRichTable.Meta):
        model = Audit
        fields = ("name", "auditor", "type", "start_date", "end_date")


class FindingTable(BaseRichTable):
    name = tables.Column(
        verbose_name="Name",
        default="Unnamed finding",
        linkify=("conformity:finding_detail", [A("pk")]),
        attrs=PRIMARY_COLUMN,
    )
    short_description = tables.Column(verbose_name="Description")
    cvss = BadgeColumn(
        FINDING_SEVERITY_STYLES,
        style_accessor="severity",
        verbose_name="CVSS",
        default="-",
        order_by=("cvss",),
        attrs=CENTER,
    )
    audit = tables.Column(
        verbose_name="Audit campaign",
        linkify=("conformity:audit_detail", [A("audit__pk")]),
        order_by=("audit__name",),
        attrs={
            "th": {"class": "text-center"},
            "td": {"class": "text-center"},
            "a": {"class": "btn btn-sm btn-outline-secondary w-75 mx-auto"},
        },
    )
    associated_actions = tables.TemplateColumn(
        verbose_name="Associated actions",
        template_code="""
            {% if record.actions_count %}
                <a href="{% url 'conformity:action_index' %}?associated_findings={{ record.pk }}"
                   class="btn btn-sm btn-outline-secondary w-75 mx-auto">
                    {{ record.actions_count }} action{{ record.actions_count|pluralize }}
                </a>
            {% endif %}
        """,
        order_by=("actions_count",),
        attrs=CENTER,
    )

    actions = EditColumn("conformity:finding_form", "finding")

    class Meta(BaseRichTable.Meta):
        model = Finding
        fields = ("name", "short_description", "cvss", "audit")


class OrganizationTable(BaseRichTable):
    name = tables.Column(
        verbose_name="Name",
        linkify=("conformity:organization_detail", [A("pk")]),
        attrs=PRIMARY_COLUMN,
    )
    administrative_id = tables.Column(
        verbose_name="Identifier",
        default="—",
        attrs={"cell": {"class": "text-nowrap"}},
    )
    description = tables.Column()
    frameworks = tables.TemplateColumn(
        verbose_name="Applicable frameworks",
        template_code="""
            <div class="d-grid gap-1">
                {% for item in record.get_frameworks %}
                    <a href="{% url 'conformity:conformity_detail_index' record.id item.id %}"
                       class="btn btn-sm btn-outline-secondary w-75 mx-auto">{{ item }}</a>
                {% endfor %}
            </div>
        """,
        orderable=False,
        attrs=CENTER,
    )

    actions = EditColumn("conformity:organization_form", "organization")

    class Meta(BaseRichTable.Meta):
        model = Organization
        fields = ("name", "administrative_id", "description")


class FrameworkTable(BaseRichTable):
    name = tables.Column(
        verbose_name="Name",
        linkify=("conformity:framework_detail", [A("pk")]),
        attrs=PRIMARY_COLUMN,
    )
    version = tables.Column(default="-", attrs=CENTER)
    language = tables.Column(accessor="get_language_display", order_by=("language",), attrs=CENTER)
    publish_by = tables.Column(verbose_name="Published by")
    type = tables.Column(accessor="get_type_display", verbose_name="Type", order_by=("type",))
    requirements = tables.Column(
        accessor="get_requirements_number",
        verbose_name="Requirements",
        orderable=False,
        attrs=CENTER,
    )

    class Meta(BaseRichTable.Meta):
        model = Framework
        fields = ("name", "version", "language", "publish_by", "type")


class ConformityTable(BaseRichTable):
    conformity = tables.TemplateColumn(
        verbose_name="Name",
        template_code="""
            <a href="{% url 'conformity:conformity_detail_index' record.organization.id record.requirement.framework.id %}"
               class="table-primary-link">
                {{ record.organization }} / {{ record.requirement.framework }}
            </a>
        """,
        order_by=("organization__name", "requirement__framework__name"),
        attrs=PRIMARY_COLUMN,
    )
    requirements = tables.TemplateColumn(
        verbose_name="Requirements",
        template_code="{{ record.get_leaf|length }}",
        orderable=False,
        attrs=CENTER,
    )
    completeness = tables.TemplateColumn(
        template_code="{{ record.get_completeness }} %",
        orderable=False,
        attrs=CENTER,
    )
    status = tables.TemplateColumn(
        verbose_name="Status",
        template_code="""
            <div class="progress" role="progressbar" aria-valuenow="{{ record.status|default_if_none:'0' }}"
                 aria-valuemin="0" aria-valuemax="100">
                <div class="progress-bar" style="width: {{ record.status|default_if_none:'0' }}%">
                    {{ record.status|default_if_none:"0" }}%
                </div>
            </div>
        """,
        order_by=("status",),
        attrs=CENTER,
    )
    class Meta(BaseRichTable.Meta):
        model = Conformity
        fields = ("status",)
        sequence = ("conformity", "requirements", "completeness", "status")


class ControlTable(BaseRichTable):
    title = tables.Column(
        verbose_name="Name",
        linkify=("conformity:control_detail", [A("pk")]),
        attrs=PRIMARY_COLUMN,
    )
    level = tables.Column(accessor="get_level_display", order_by=("level",), attrs=CENTER)
    frequency = tables.Column(accessor="get_frequency_display", order_by=("frequency",), attrs=CENTER)
    requirements = tables.TemplateColumn(
        verbose_name="Associated requirements",
        template_code="""
            <div class="d-grid gap-1">
                {% for conformity in record.conformity.all %}
                    <a href="{% url 'conformity:conformity_detail_index' conformity.organization.id conformity.requirement.framework.id %}#requirement-{{ conformity.requirement.id }}"
                       class="btn btn-sm btn-outline-secondary w-75 mx-auto"
                       title="{{ conformity.requirement.title }}">{{ conformity.requirement.full_path }}</a>
                {% endfor %}
            </div>
        """,
        orderable=False,
    )

    actions = EditColumn("conformity:control_form", "control")

    class Meta(BaseRichTable.Meta):
        model = Control
        fields = ("title", "level", "frequency")


class ControlPointTable(BaseRichTable):
    period_start_date = tables.DateColumn(
        verbose_name="Start date",
        format="d-M-Y",
        linkify=("conformity:controlpoint_form", [A("pk")]),
        attrs=PRIMARY_COLUMN,
    )
    period_end_date = tables.DateColumn(verbose_name="End date", format="d-M-Y")
    control_user = tables.Column(verbose_name="Owner", default="")
    status = StatusColumn(CONTROL_POINT_STATUS_STYLES)
    class Meta(BaseRichTable.Meta):
        model = ControlPoint
        fields = ("period_start_date", "period_end_date", "control_user", "status")
