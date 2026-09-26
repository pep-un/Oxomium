import django_tables2 as tables

from .models import Action, Audit, Conformity, Control, ControlPoint, Finding, Framework, Organization


CENTER = {"cell": {"class": "text-center"}}


class BaseRichTable(tables.Table):
    """Shared presentation defaults for sortable, paginated list tables."""

    class Meta:
        attrs = {
            "class": "table table-striped table-hover align-middle",
            "thead": {"class": "table-light"},
        }
        empty_text = "No data to display"


class ActionTable(BaseRichTable):
    title = tables.Column(verbose_name="Title")
    owner = tables.Column(default="", attrs={"td": {"class": "text-nowrap"}})
    status = tables.TemplateColumn(
        template_code="""
            {% if record.status == "1" %}<i class="bi bi-hexagon-fill text-info"></i>{% endif %}
            {% if record.status == "2" %}<i class="bi bi-hexagon-fill text-primary"></i>{% endif %}
            {% if record.status == "3" %}<i class="bi bi-hexagon-fill text-warning"></i>{% endif %}
            {% if record.status == "4" %}<i class="bi bi-hexagon-fill text-success"></i>{% endif %}
            {% if record.status == "5" %}<i class="bi bi-hexagon-fill"></i>{% endif %}
            {% if record.status == "7" %}<i class="bi bi-hexagon text-danger"></i>{% endif %}
            {% if record.status == "9" %}<i class="bi bi-hexagon-fill text-danger"></i>{% endif %}
            {{ record.get_status_display }}
        """,
        order_by=("status",),
    )
    update_date = tables.DateColumn(verbose_name="Last update", format="d-M-Y")
    association = tables.TemplateColumn(
        verbose_name="Association",
        template_code="""
            {% with associated=record.get_associated %}
                {% if associated %}
                    <span class="badge text-bg-secondary">{{ associated|length }} associated</span>
                {% endif %}
            {% endwith %}
        """,
        orderable=False,
        attrs=CENTER,
    )
    actions = tables.TemplateColumn(
        template_code="""
            <div class="btn-group">
                <a href="{% url 'conformity:action_form' record.id %}"
                   class="btn btn-sm btn-warning bi bi-pencil-square" title="Edit">
                    <span class="visually-hidden">Edit action</span>
                </a>
                {% if record.reference %}
                    <a href="{{ record.reference }}"
                       class="btn btn-sm btn-secondary bi bi-box-arrow-up-right" title="ITSM Reference link">
                        <span class="visually-hidden">Open ITSM reference</span>
                    </a>
                {% endif %}
            </div>
        """,
        orderable=False,
        attrs=CENTER,
    )

    class Meta(BaseRichTable.Meta):
        model = Action
        fields = ("title", "owner", "status", "update_date")


class AuditTable(BaseRichTable):
    name = tables.Column()
    auditor = tables.Column()
    type = tables.Column(accessor="type", verbose_name="Type")
    start_date = tables.DateColumn(verbose_name="Start", format="d-M-Y")
    end_date = tables.DateColumn(verbose_name="End", format="d-M-Y")
    findings = tables.TemplateColumn(
        verbose_name="Findings",
        template_code="{{ record.get_findings_number }}",
        orderable=False,
        attrs=CENTER,
    )
    actions = tables.TemplateColumn(
        template_code="""
            <div class="btn-group">
                <a href="{% url 'conformity:audit_detail' record.id %}"
                   class="btn btn-sm btn-primary bi bi-eye" title="View">
                    <span class="visually-hidden">View audit</span>
                </a>
                <a href="{% url 'conformity:audit_form' record.id %}"
                   class="btn btn-sm btn-warning bi bi-pencil-square" title="Edit">
                    <span class="visually-hidden">Edit audit</span>
                </a>
            </div>
        """,
        orderable=False,
        attrs=CENTER,
    )

    def render_type(self, record):
        return record.get_type()

    class Meta(BaseRichTable.Meta):
        model = Audit
        fields = ("name", "auditor", "type", "start_date", "end_date")


class FindingTable(BaseRichTable):
    name = tables.Column(verbose_name="Finding", default="Unnamed finding", attrs=CENTER)
    short_description = tables.Column(verbose_name="Description")
    cvss = tables.TemplateColumn(
        verbose_name="CVSS",
        template_code="""
            {% if record.severity == "CRT" %}<span class="badge rounded-pill text-bg-dark">
            {% elif record.severity == "MAJ" %}<span class="badge rounded-pill text-bg-danger">
            {% elif record.severity == "MIN" %}<span class="badge rounded-pill text-bg-warning">
            {% elif record.severity == "OBS" %}<span class="badge rounded-pill text-bg-info">
            {% elif record.severity == "OTHER" %}<span class="badge rounded-pill text-bg-secondary">
            {% elif record.severity == "POS" %}<span class="badge rounded-pill text-bg-success">
            {% else %}<span class="badge rounded-pill text-bg-secondary">{% endif %}
                {{ record.cvss|default:"-" }}
            </span>
        """,
        order_by=("cvss",),
        attrs=CENTER,
    )
    audit = tables.TemplateColumn(
        verbose_name="Audit campaign",
        template_code="""
            <a href="{% url 'conformity:audit_detail' record.audit.id %}"
               class="btn btn-outline-primary btn-sm">{{ record.audit }}</a>
        """,
        order_by=("audit__name",),
        attrs=CENTER,
    )
    associated_actions = tables.TemplateColumn(
        verbose_name="Associated actions",
        template_code="""
            {% with actions=record.get_action %}
                {% if actions %}
                    <a href="{% url 'conformity:action_index' %}?associated_findings={{ record.id }}"
                       class="btn btn-outline-primary btn-sm">{{ actions|length }} associated actions</a>
                {% endif %}
            {% endwith %}
        """,
        orderable=False,
        attrs=CENTER,
    )
    actions = tables.TemplateColumn(
        verbose_name="Action",
        template_code="""
            <div class="btn-group">
                <a href="{% url 'conformity:finding_detail' record.id %}"
                   class="btn btn-sm btn-primary bi bi-eye" title="View">
                    <span class="visually-hidden">View finding</span>
                </a>
                <a href="{% url 'conformity:finding_form' record.id %}"
                   class="btn btn-sm btn-warning bi bi-pencil-square" title="Edit">
                    <span class="visually-hidden">Edit finding</span>
                </a>
            </div>
        """,
        orderable=False,
        attrs=CENTER,
    )

    class Meta(BaseRichTable.Meta):
        model = Finding
        fields = ("name", "short_description", "cvss", "audit")


class OrganizationTable(BaseRichTable):
    name = tables.Column(verbose_name="Organization")
    description = tables.TemplateColumn(
        template_code="""
            <p>{{ record.description|linebreaksbr }}</p>
            {% if record.administrative_id %}
                <p class="alert alert-info py-1 mb-0">Company identifier: {{ record.administrative_id }}</p>
            {% else %}
                <p class="alert alert-warning py-1 mb-0">No identifier</p>
            {% endif %}
        """,
        order_by=("description",),
    )
    frameworks = tables.TemplateColumn(
        verbose_name="Applicable frameworks",
        template_code="""
            {% for item in record.get_frameworks %}
                <a href="{% url 'conformity:conformity_detail_index' record.id item.id %}"
                   class="btn btn-outline-primary btn-sm my-1">{{ item }}</a>
            {% empty %}
                <span class="text-body-secondary">None</span>
            {% endfor %}
        """,
        orderable=False,
        attrs=CENTER,
    )
    actions = tables.TemplateColumn(
        template_code="""
            <div class="btn-group">
                <a href="{% url 'conformity:organization_detail' record.id %}"
                   class="btn btn-sm btn-primary bi bi-eye" title="View">
                    <span class="visually-hidden">View organization</span>
                </a>
                <a href="{% url 'conformity:organization_form' record.id %}"
                   class="btn btn-sm btn-warning bi bi-pencil-square" title="Edit">
                    <span class="visually-hidden">Edit organization</span>
                </a>
            </div>
        """,
        orderable=False,
        attrs=CENTER,
    )

    class Meta(BaseRichTable.Meta):
        model = Organization
        fields = ("name", "description")


class FrameworkTable(BaseRichTable):
    name = tables.Column(verbose_name="Framework")
    version = tables.Column(default="-", attrs=CENTER)
    language = tables.Column(attrs=CENTER)
    publish_by = tables.Column(verbose_name="Published by")
    type = tables.Column(verbose_name="Type")
    requirements = tables.TemplateColumn(
        template_code="""
            <a href="{% url 'conformity:framework_detail' record.id %}"
               class="btn btn-outline-primary btn-sm">
                {{ record.get_requirements_number }} requirements
            </a>
        """,
        orderable=False,
        attrs=CENTER,
    )

    def render_language(self, record):
        return record.get_language_display()

    def render_type(self, record):
        return record.get_type()

    class Meta(BaseRichTable.Meta):
        model = Framework
        fields = ("name", "version", "language", "publish_by", "type")


class ConformityTable(BaseRichTable):
    organization = tables.Column()
    framework = tables.Column(accessor="requirement__framework", order_by=("requirement__framework__name",))
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
        verbose_name="Conformity",
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
    actions = tables.TemplateColumn(
        template_code="""
            <a href="{% url 'conformity:conformity_detail_index' record.organization.id record.requirement.framework.id %}"
               class="btn btn-sm btn-primary bi bi-eye" title="Detail">
                <span class="visually-hidden">View conformity</span>
            </a>
        """,
        orderable=False,
        attrs=CENTER,
    )

    class Meta(BaseRichTable.Meta):
        model = Conformity
        fields = ("organization", "status")


class ControlTable(BaseRichTable):
    title = tables.Column(verbose_name="Title")
    level = tables.Column(attrs=CENTER)
    frequency = tables.Column(attrs=CENTER)
    requirements = tables.TemplateColumn(
        verbose_name="Associated requirements",
        template_code="""
            {% for conformity in record.conformity.all %}
                <span class="badge rounded-pill text-bg-secondary"
                      title="{{ conformity.requirement.title }}">{{ conformity.requirement.full_path }}</span>
            {% empty %}
                <span class="text-body-secondary">None</span>
            {% endfor %}
        """,
        orderable=False,
    )
    actions = tables.TemplateColumn(
        template_code="""
            <div class="btn-group">
                <a href="{% url 'conformity:controlpoint_index' %}?control={{ record.id }}"
                   class="btn btn-primary btn-sm bi bi-eye" title="View">
                    <span class="visually-hidden">View control points</span>
                </a>
                <a href="{% url 'conformity:control_form' record.id %}"
                   class="btn btn-sm btn-warning bi bi-pencil-square" title="Edit">
                    <span class="visually-hidden">Edit control</span>
                </a>
            </div>
        """,
        orderable=False,
        attrs=CENTER,
    )

    def render_level(self, record):
        return record.get_level_display()

    def render_frequency(self, record):
        return record.get_frequency_display()

    class Meta(BaseRichTable.Meta):
        model = Control
        fields = ("title", "level", "frequency")


class ControlPointTable(BaseRichTable):
    period_start_date = tables.DateColumn(verbose_name="Start date", format="d-M-Y")
    period_end_date = tables.DateColumn(verbose_name="End date", format="d-M-Y")
    control_user = tables.Column(verbose_name="Owner", default="")
    status = tables.TemplateColumn(
        template_code="""
            {% if record.status == "SCHD" %}<i class="bi bi-hexagon text-secondary"></i>{% endif %}
            {% if record.status == "TOBE" %}<i class="bi bi-hexagon-fill text-secondary"></i>{% endif %}
            {% if record.status == "NOK" %}<i class="bi bi-hexagon-fill text-danger"></i>{% endif %}
            {% if record.status == "OK" %}<i class="bi bi-hexagon-fill text-success"></i>{% endif %}
            {% if record.status == "MISS" %}<i class="bi bi-hexagon text-danger"></i>{% endif %}
            {{ record.get_status_display }}
        """,
        order_by=("status",),
    )
    actions = tables.TemplateColumn(
        verbose_name="Action",
        template_code="""
            <a href="{% url 'conformity:controlpoint_form' record.id %}"
               class="btn btn-sm {% if record.status == 'TOBE' %}btn-warning bi bi-pencil-square{% else %}btn-primary bi bi-eye{% endif %}"
               title="{% if record.status == 'TOBE' %}Edit{% else %}View{% endif %}">
                <span class="visually-hidden">{% if record.status == "TOBE" %}Edit{% else %}View{% endif %} control point</span>
            </a>
        """,
        orderable=False,
        attrs=CENTER,
    )

    class Meta(BaseRichTable.Meta):
        model = ControlPoint
        fields = ("period_start_date", "period_end_date", "control_user", "status")
