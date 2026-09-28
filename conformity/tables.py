import django_tables2 as tables
from auditlog.models import LogEntry
from django.utils.html import format_html
from django_tables2.utils import A, OrderByTuple

from .models import Action, Attachment, Audit, Conformity, Control, ControlPoint, Finding, Framework, Organization


CENTER = {"cell": {"class": "text-center"}}
PRIMARY_COLUMN = {
    "th": {"class": "col-2 text-start"},
    "td": {"class": "col-2 text-start"},
    "a": {"class": "table-primary-link"},
}


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



class BaseRichTable(tables.Table):
    """Shared presentation defaults for sortable, paginated list tables."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active_order = self.order_by
        for bound_column in self.columns.iterorderable():
            order_by = bound_column.column.order_by or OrderByTuple(
                (bound_column.accessor,)
            )
            if not any(str(item).lstrip("-") == "pk" for item in order_by):
                bound_column.column.order_by = OrderByTuple((*order_by, "pk"))
        if active_order:
            self.order_by = active_order

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
    priority = tables.TemplateColumn(
        template_code="""
            {% include 'conformity/includes/action_priority.html' with action=record %}
        """,
        order_by=("priority",),
        attrs=CENTER,
    )
    status = tables.TemplateColumn(
        template_code="""
            {% include 'conformity/includes/action_status.html' with action=record %}
        """,
        order_by=("status",),
    )
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
                {% if record.reference %}
                    <a href="{{ record.reference }}" target="_blank" rel="noopener"
                       class="btn btn-sm btn-outline-secondary w-75 mx-auto"
                       title="ITSM Reference link">
                        ITSM Ticket <i class="bi bi-box-arrow-up-right ms-1" aria-hidden="true"></i>
                    </a>
                {% endif %}
            </div>
        """,
        orderable=False,
        attrs=CENTER,
    )

    class Meta(BaseRichTable.Meta):
        model = Action
        fields = ("title", "owner", "priority", "status", "update_date")


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
    cvss = tables.TemplateColumn(
        verbose_name="CVSS",
        template_code="""
            {% include 'conformity/includes/finding_cvss_badge.html' with finding=record %}
        """,
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
    organization = tables.TemplateColumn(
        verbose_name="Organization",
        template_code="""
            {% if record.organization %}
                <a href="{% url 'conformity:organization_detail' record.organization.pk %}"
                   class="btn btn-sm btn-outline-secondary w-75 mx-auto">
                    {{ record.organization }}
                </a>
            {% endif %}
        """,
        order_by=("organization__name",),
        attrs=CENTER,
    )
    level = tables.Column(accessor="get_level_display", order_by=("level",), attrs=CENTER)
    frequency = tables.Column(accessor="get_frequency_display", order_by=("frequency",), attrs=CENTER)
    last_result = tables.TemplateColumn(
        verbose_name="Last result",
        template_code="""
            {% with point=record.current_controlpoints.0 %}
                {% if point %}
                    {% if point.is_final_status %}
                        {% include 'conformity/includes/controlpoint_status.html' with controlpoint=point %}
                    {% else %}
                        <a href="{% url 'conformity:controlpoint_form' point.pk %}"
                           class="btn btn-sm btn-outline-primary w-75 mx-auto bi bi-pencil-square">
                            Evaluate
                        </a>
                    {% endif %}
                {% else %}
                    <a href="{% url 'conformity:control_form' record.pk %}"
                       class="btn btn-sm btn-outline-secondary w-75 mx-auto bi bi-arrow-repeat">
                        Update control
                    </a>
                {% endif %}
            {% endwith %}
        """,
        orderable=False,
        attrs=CENTER,
    )
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
        fields = ("title", "organization", "level", "frequency")
        sequence = (
            "title",
            "organization",
            "level",
            "frequency",
            "last_result",
            "requirements",
            "actions",
        )

class ControlPointTable(BaseRichTable):
    name = tables.Column(
        accessor="control__title",
        verbose_name="Name",
        default="",
        linkify=("conformity:controlpoint_form", [A("pk")]),
        order_by=("control__title",),
        attrs=PRIMARY_COLUMN,
    )
    valid_from = tables.DateTimeColumn(verbose_name="Start date", format="d-M-Y")
    valid_to = tables.DateTimeColumn(verbose_name="End date", format="d-M-Y")
    evaluator = tables.Column(verbose_name="Owner", default="")
    status = tables.TemplateColumn(
        template_code="""
            {% include 'conformity/includes/controlpoint_status.html' with controlpoint=record %}
        """,
        order_by=("status",),
    )

    class Meta(BaseRichTable.Meta):
        model = ControlPoint
        fields = ("valid_from", "valid_to", "evaluator", "status")
        sequence = ("name", "valid_from", "valid_to", "evaluator", "status")


class AttachmentTable(BaseRichTable):
    attachment = tables.TemplateColumn(
        verbose_name="Attachment",
        accessor="file",
        template_code="""
            {% include "includes/attachment_link.html" with attachment=record %}
        """,
        order_by=("file",),
        attrs=PRIMARY_COLUMN,
    )
    sha256 = tables.TemplateColumn(
        verbose_name="SHA-256",
        template_code="""
            {% if record.sha256 %}
                <div class="btn-group btn-group-sm" role="group" aria-label="SHA-256 checksum">
                    <span class="btn btn-outline-secondary disabled font-monospace"
                          title="{{ record.sha256 }}"
                          aria-disabled="true">
                        {{ record.sha256|slice:":16" }}…
                    </span>
                    <button type="button"
                            class="btn btn-outline-secondary js-copy-sha256"
                            title="Copy SHA-256"
                            aria-label="Copy SHA-256"
                            data-copy-value="{{ record.sha256 }}">
                        <i class="bi bi-clipboard" aria-hidden="true"></i>
                    </button>
                </div>
            {% else %}
                <form method="post" action="{% url 'conformity:attachment_checksum' record.id %}" class="d-inline">
                    {% csrf_token %}
                    <button type="submit" class="btn btn-sm btn-outline-secondary" title="Calculate SHA-256">
                        <i class="bi bi-calculator me-1" aria-hidden="true"></i>
                        Calculate
                    </button>
                </form>
            {% endif %}
        """,
        order_by=("sha256",),
    )
    create_date = tables.DateTimeColumn(
        verbose_name="Creation date",
        format="d-M-Y H:i",
        attrs=CENTER,
    )
    references = tables.TemplateColumn(
        accessor="pk",
        verbose_name="References",
        template_code="""
            <div class="d-flex flex-wrap gap-1 justify-content-center">
                {% for org in record.organizations.all %}
                    <a href="{% url 'conformity:organization_detail' org.id %}">
                        <span class="badge text-bg-dark px-3">
                            <i class="bi bi-building pe-2"></i>{{ org }}
                        </span>
                    </a>
                {% endfor %}
                {% for framework in record.frameworks.all %}
                    <a href="{% url 'conformity:framework_detail' framework.id %}#attachments">
                        <span class="badge text-bg-primary px-3">
                            <i class="bi bi-card-checklist pe-2"></i>{{ framework }}
                        </span>
                    </a>
                {% endfor %}
                {% for cp in record.ControlPoint.all %}
                    <a href="{% url 'conformity:controlpoint_form' cp.id %}">
                        <span class="badge text-bg-secondary px-3">
                            <i class="bi bi-clipboard2-check pe-2"></i>{{ cp }}
                        </span>
                    </a>
                {% endfor %}
                {% for audit in record.audits.all %}
                    <a href="{% url 'conformity:audit_detail' audit.id %}">
                        <span class="badge text-bg-success px-3">
                            <i class="bi bi-ui-checks-grid pe-2"></i>{{ audit }}
                        </span>
                    </a>
                {% endfor %}
                {% for point in record.IndicatorPoint.all %}
                    <a href="{% url 'conformity:indicatorpoint_form' point.id %}">
                        <span class="badge text-bg-info px-3">
                            <i class="bi bi-speedometer pe-2"></i>
                            {{ point.indicator.name }} · {{ point.period_start_date|date:"d-M-Y" }} – {{ point.period_end_date|date:"d-M-Y" }}
                        </span>
                    </a>
                {% endfor %}
            </div>
        """,
        orderable=False,
        attrs=CENTER,
    )

    class Meta(BaseRichTable.Meta):
        model = Attachment
        fields = ("sha256", "create_date")
        sequence = ("attachment", "sha256", "create_date", "references")


class AuditLogTable(BaseRichTable):
    timestamp = tables.DateTimeColumn(
        verbose_name="Date",
        format="d-M-Y H:i T",
        attrs={"cell": {"class": "text-nowrap"}},
    )
    actor = tables.TemplateColumn(
        template_code="""
            {{ record.actor|default_if_none:"Oxomium" }}
            <span class="badge rounded-pill text-bg-secondary">
                {{ record.remote_addr|default_if_none:"" }}
            </span>
        """,
        order_by=("actor",),
        attrs=CENTER,
    )
    action = tables.TemplateColumn(
        template_code="""
            {% if record.action is 0 %}
                <span class="badge rounded-pill text-bg-success">CREATE</span>
            {% elif record.action is 1 %}
                <span class="badge rounded-pill text-bg-primary">UPDATE</span>
            {% elif record.action is 2 %}
                <span class="badge rounded-pill text-bg-danger">DELETE</span>
            {% elif record.action is 3 %}
                <span class="badge rounded-pill text-bg-secondary">ACCESS</span>
            {% endif %}
        """,
        order_by=("action",),
        attrs=CENTER,
    )
    resource = tables.TemplateColumn(
        accessor="object_repr",
        verbose_name="Resource",
        template_code="""
            {{ record.object_repr|truncatechars:30 }}
            <span class="badge rounded-pill text-bg-secondary">{{ record.content_type|lower }}</span>
        """,
        order_by=("object_repr",),
    )
    changes = tables.TemplateColumn(
        accessor="pk",
        verbose_name="Change",
        template_code="""
            <ul class="mb-0">
                {% for change in record.m2m_changes %}
                    <li class="text-wrap">
                        {{ change.field }}:
                        <span class="badge rounded-pill text-bg-secondary">
                            {{ change.operation }}: {{ change.objects|join:", " }}
                        </span>
                    </li>
                {% endfor %}
                {% for key, value in record.standard_changes.items %}
                    {% if record.action is 0 %}
                        <li class="text-wrap">
                            {{ key }}:
                            <span class="badge rounded-pill text-bg-success" title="{{ value.1 }}">
                                {{ value.1|truncatechars:40 }}
                            </span>
                        </li>
                    {% elif record.action is 1 %}
                        <li class="text-wrap">
                            {{ key }}:
                            <span class="badge rounded-pill text-bg-secondary" title="{{ value.0 }}">
                                {{ value.0|truncatechars:20 }}
                            </span>
                            ⇒
                            <span class="badge rounded-pill text-bg-primary" title="{{ value.1 }}">
                                {{ value.1|truncatechars:20 }}
                            </span>
                        </li>
                    {% elif record.action is 2 %}
                        <li class="text-wrap">
                            {{ key }}:
                            <span class="badge rounded-pill text-bg-danger" title="{{ value.0 }}">
                                {{ value.0|truncatechars:40 }}
                            </span>
                        </li>
                    {% endif %}
                {% endfor %}
            </ul>
        """,
        orderable=False,
    )

    class Meta(BaseRichTable.Meta):
        model = LogEntry
        fields = ("timestamp", "actor", "action")
        sequence = ("timestamp", "actor", "action", "resource", "changes")
