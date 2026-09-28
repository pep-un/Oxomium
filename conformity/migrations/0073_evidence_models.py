# Generated for Evidence inheritance refactor.
from datetime import datetime, time, timedelta

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def _day_start(value):
    result = datetime.combine(value, time.min)
    return timezone.make_aware(result, timezone.get_current_timezone())


def _period_end(value):
    return _day_start(value + timedelta(days=1))


def migrate_evidence(apps, schema_editor):
    Evidence = apps.get_model('conformity', 'Evidence')
    ControlPoint = apps.get_model('conformity', 'ControlPoint')
    IndicatorPoint = apps.get_model('conformity', 'IndicatorPoint')
    LegacyControlPoint = apps.get_model('conformity', 'LegacyControlPoint')
    LegacyIndicatorPoint = apps.get_model('conformity', 'LegacyIndicatorPoint')
    HumanEvidence = apps.get_model('conformity', 'HumanEvidence')
    DocumentEvidence = apps.get_model('conformity', 'DocumentEvidence')
    FindingEvidence = apps.get_model('conformity', 'FindingEvidence')
    Control = apps.get_model('conformity', 'Control')
    Indicator = apps.get_model('conformity', 'Indicator')
    Conformity = apps.get_model('conformity', 'Conformity')
    Attachment = apps.get_model('conformity', 'Attachment')
    Finding = apps.get_model('conformity', 'Finding')
    Action = apps.get_model('conformity', 'Action')

    # Preserve target configuration without keeping Control/Indicator -> Conformity M2Ms.
    for control in Control.objects.all().iterator():
        control.requirements.add(*control.conformity.values_list('requirement_id', flat=True))
    for indicator in Indicator.objects.all().iterator():
        indicator.requirements.add(*indicator.conformity.values_list('requirement_id', flat=True))

    control_map = {}
    for old in LegacyControlPoint.objects.select_related('control').iterator():
        point = ControlPoint.objects.create(
            legacy_pk=old.pk,
            control_id=old.control_id,
            source_type='CTRL',
            result={'OK': 'POS', 'NOK': 'NEG'}.get(old.status, 'NEU'),
            valid_from=_day_start(old.period_start_date),
            valid_to=_period_end(old.period_end_date),
            evaluated_at=old.control_date,
            evaluator_id=old.control_user_id,
            comment=old.comment,
            status=old.status,
        )
        point.conformities.add(*old.control.conformity.all())
        point.attachments.add(*old.attachment.all())
        control_map[old.pk] = point.pk

    indicator_map = {}
    for old in LegacyIndicatorPoint.objects.select_related('indicator').iterator():
        point = IndicatorPoint.objects.create(
            legacy_pk=old.pk,
            indicator_id=old.indicator_id,
            source_type='IND',
            result={'OK': 'POS', 'CRIT': 'NEG'}.get(old.status, 'NEU'),
            valid_from=_day_start(old.period_start_date),
            valid_to=_period_end(old.period_end_date),
            evaluated_at=old.control_date,
            evaluator_id=old.control_user_id,
            comment=old.comment,
            status=old.status,
            value=old.value,
        )
        point.conformities.add(*old.indicator.conformity.all())
        point.attachments.add(*old.attachment.all())
        indicator_map[old.pk] = point.pk

    # Preserve Action <-> ControlPoint links while swapping the model/table.
    for action in Action.objects.all().iterator():
        new_ids = [
            control_map[old_id]
            for old_id in action.associated_controlPoints.values_list('pk', flat=True)
            if old_id in control_map
        ]
        if new_ids:
            action.evidence_control_points.add(*new_ids)

    for conformity in Conformity.objects.filter(
        status_justification='EXPT', status__isnull=False
    ).iterator():
        result = 'POS' if conformity.status == 100 else ('NEG' if conformity.status == 0 else 'PAR')
        human = HumanEvidence.objects.create(
            source_type='HUM',
            result=result,
            decision=result,
            valid_from=conformity.status_last_update or timezone.now(),
            evaluated_at=conformity.status_last_update,
            evaluator_id=conformity.responsible_id,
            comment=conformity.comment,
        )
        human.conformities.add(conformity)

    finding_results = {'POS': 'POS', 'CRT': 'NEG', 'MAJ': 'NEG', 'MIN': 'NEG'}
    for finding in Finding.objects.select_related('audit').iterator():
        valid_from = (
            finding.audit.report_date or finding.audit.end_date
            or finding.audit.start_date or timezone.now().date()
        )
        FindingEvidence.objects.create(
            source_type='FIND',
            result=finding_results.get(finding.severity, 'NEU'),
            valid_from=_day_start(valid_from),
            finding_id=finding.pk,
            comment=finding.observation or finding.description,
        )

    for attachment in Attachment.objects.iterator():
        DocumentEvidence.objects.create(
            source_type='DOC',
            result='NEU',
            valid_from=attachment.create_date or timezone.now(),
            document_id=attachment.pk,
        )


def reverse_evidence(apps, schema_editor):
    ControlPoint = apps.get_model('conformity', 'ControlPoint')
    IndicatorPoint = apps.get_model('conformity', 'IndicatorPoint')
    LegacyControlPoint = apps.get_model('conformity', 'LegacyControlPoint')
    LegacyIndicatorPoint = apps.get_model('conformity', 'LegacyIndicatorPoint')
    Control = apps.get_model('conformity', 'Control')
    Indicator = apps.get_model('conformity', 'Indicator')
    Conformity = apps.get_model('conformity', 'Conformity')
    Action = apps.get_model('conformity', 'Action')

    control_reverse = {}
    for point in ControlPoint.objects.select_related('control').iterator():
        if point.legacy_pk is None:
            continue
        old = LegacyControlPoint.objects.create(
            id=point.legacy_pk,
            control_id=point.control_id,
            control_date=point.evaluated_at,
            control_user_id=point.evaluator_id,
            period_start_date=timezone.localtime(point.valid_from).date(),
            period_end_date=(timezone.localtime(point.valid_to) - timedelta(microseconds=1)).date(),
            status=point.status,
            comment=point.comment,
        )
        old.attachment.add(*point.attachments.all())
        control_reverse[point.pk] = old.pk
        if point.control_id:
            point.control.conformity.add(*point.conformities.all())

    for point in IndicatorPoint.objects.select_related('indicator').iterator():
        if point.legacy_pk is None:
            continue
        old = LegacyIndicatorPoint.objects.create(
            id=point.legacy_pk,
            indicator_id=point.indicator_id,
            control_date=point.evaluated_at,
            control_user_id=point.evaluator_id,
            period_start_date=timezone.localtime(point.valid_from).date(),
            period_end_date=(timezone.localtime(point.valid_to) - timedelta(microseconds=1)).date(),
            status=point.status,
            comment=point.comment,
            value=point.value,
        )
        old.attachment.add(*point.attachments.all())
        if point.indicator_id:
            point.indicator.conformity.add(*point.conformities.all())

    for action in Action.objects.all().iterator():
        old_ids = [
            control_reverse[new_id]
            for new_id in action.evidence_control_points.values_list('pk', flat=True)
            if new_id in control_reverse
        ]
        if old_ids:
            action.associated_controlPoints.add(*old_ids)


class Migration(migrations.Migration):

    dependencies = [
        ('conformity', '0072_attachment_sha256'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameModel(old_name='ControlPoint', new_name='LegacyControlPoint'),
        migrations.RenameModel(old_name='IndicatorPoint', new_name='LegacyIndicatorPoint'),
        migrations.CreateModel(
            name='Evidence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_type', models.CharField(choices=[('CTRL', 'Control'), ('IND', 'Indicator'), ('HUM', 'Human assessment'), ('FIND', 'Audit finding'), ('DOC', 'Documentary proof'), ('MAN', 'Manual evidence')], max_length=4)),
                ('result', models.CharField(choices=[('POS', 'Positive'), ('NEG', 'Negative'), ('NEU', 'Neutral / inconclusive'), ('PAR', 'Partially compliant')], default='NEU', max_length=3)),
                ('valid_from', models.DateTimeField()),
                ('valid_to', models.DateTimeField(blank=True, null=True)),
                ('evaluated_at', models.DateTimeField(blank=True, null=True)),
                ('comment', models.TextField(blank=True, max_length=4096)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('result_updated_at', models.DateTimeField(default=timezone.now)),
                ('attachments', models.ManyToManyField(blank=True, related_name='evidence', to='conformity.attachment')),
                ('conformities', models.ManyToManyField(blank=True, related_name='evidence', to='conformity.conformity')),
                ('evaluator', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='evaluated_evidence', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-valid_from', '-pk']},
        ),
        migrations.AddField(
            model_name='conformity',
            name='evidence_state',
            field=models.CharField(choices=[('NONE', 'Not evaluated'), ('COMP', 'Compliant'), ('PART', 'Partially compliant'), ('NONC', 'Non-compliant'), ('INCO', 'Inconclusive')], default='NONE', max_length=4),
        ),
        migrations.AlterField(
            model_name='conformity',
            name='status_justification',
            field=models.CharField(blank=True, choices=[('EXPT', 'From expert statement'), ('CTRL', 'From successful control'), ('ACT', 'From completed action'), ('FIN', 'From an audit finding'), ('CONF', 'From conformity aggregation'), ('EVID', 'From evidence')], default='EXPT', max_length=4),
        ),
        migrations.AddField(
            model_name='control',
            name='requirements',
            field=models.ManyToManyField(blank=True, help_text='Requirements targeted by this control. Concrete Conformity links live on Evidence.', related_name='controls', to='conformity.requirement'),
        ),
        migrations.AddField(
            model_name='indicator',
            name='requirements',
            field=models.ManyToManyField(blank=True, help_text='Requirements targeted by this indicator. Concrete Conformity links live on Evidence.', related_name='indicators', to='conformity.requirement'),
        ),
        migrations.CreateModel(
            name='ControlPoint',
            fields=[
                ('evidence_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='conformity.evidence')),
                ('status', models.CharField(choices=[('SCHD', 'Scheduled'), ('TOBE', 'To evaluate'), ('OK', 'Compliant'), ('NOK', 'Non-Compliant'), ('MISS', 'Missed')], default='SCHD', max_length=4)),
                ('legacy_pk', models.BigIntegerField(blank=True, null=True)),
                ('control', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='conformity.control')),
            ],
            options={'ordering': ['valid_to']},
            bases=('conformity.evidence',),
        ),
        migrations.CreateModel(
            name='IndicatorPoint',
            fields=[
                ('evidence_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='conformity.evidence')),
                ('status', models.CharField(choices=[('SCHD', 'Scheduled'), ('TOBE', 'To evaluate'), ('OK', 'Compliant'), ('WARN', 'Warning'), ('CRIT', 'Critical'), ('MISS', 'Missed')], default='SCHD', max_length=4)),
                ('value', models.IntegerField(null=True)),
                ('legacy_pk', models.BigIntegerField(blank=True, null=True)),
                ('indicator', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='conformity.indicator')),
            ],
            bases=('conformity.evidence',),
        ),
        migrations.CreateModel(
            name='HumanEvidence',
            fields=[
                ('evidence_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='conformity.evidence')),
                ('decision', models.CharField(choices=[('POS', 'Compliant'), ('PAR', 'Partially compliant'), ('NEG', 'Non-compliant')], max_length=3)),
            ],
            bases=('conformity.evidence',),
        ),
        migrations.CreateModel(
            name='ManualEvidence',
            fields=[
                ('evidence_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='conformity.evidence')),
                ('title', models.CharField(max_length=256)),
            ],
            bases=('conformity.evidence',),
        ),
        migrations.CreateModel(
            name='DocumentEvidence',
            fields=[
                ('evidence_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='conformity.evidence')),
                ('title', models.CharField(blank=True, max_length=256)),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='document_evidence', to='conformity.attachment')),
            ],
            bases=('conformity.evidence',),
        ),
        migrations.CreateModel(
            name='FindingEvidence',
            fields=[
                ('evidence_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='conformity.evidence')),
                ('finding', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='evidence_record', to='conformity.finding')),
            ],
            bases=('conformity.evidence',),
        ),
        migrations.AddField(
            model_name='action',
            name='evidence_control_points',
            field=models.ManyToManyField(blank=True, related_name='actions_migration', to='conformity.controlpoint'),
        ),
        migrations.RunPython(migrate_evidence, reverse_evidence),
        migrations.RemoveField(model_name='action', name='associated_controlPoints'),
        migrations.RenameField(model_name='action', old_name='evidence_control_points', new_name='associated_controlPoints'),
        migrations.RemoveField(model_name='control', name='conformity'),
        migrations.RemoveField(model_name='indicator', name='conformity'),
        migrations.DeleteModel(name='LegacyControlPoint'),
        migrations.DeleteModel(name='LegacyIndicatorPoint'),
        migrations.RemoveField(model_name='controlpoint', name='legacy_pk'),
        migrations.RemoveField(model_name='indicatorpoint', name='legacy_pk'),
        migrations.AlterField(
            model_name='action',
            name='associated_controlPoints',
            field=models.ManyToManyField(blank=True, related_name='actions', to='conformity.controlpoint'),
        ),
        migrations.AddConstraint(
            model_name='evidence',
            constraint=models.CheckConstraint(condition=models.Q(('valid_to__isnull', True), ('valid_to__gt', models.F('valid_from')), _connector='OR'), name='chk_evidence_positive_validity'),
        ),
    ]
