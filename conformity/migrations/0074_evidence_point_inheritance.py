from datetime import datetime, time, timedelta

import django.db.models.deletion
from django.db import migrations, models
from django.utils import timezone


def _day_start(value):
    result = datetime.combine(value, time.min)
    return timezone.make_aware(result, timezone.get_current_timezone())


def _ensure_parent_evidence(apps, old, source_type, result):
    Evidence = apps.get_model('conformity', 'Evidence')
    if old.evidence_id:
        return old.evidence_id

    evidence = Evidence.objects.create(
        source_type=source_type,
        result=result,
        valid_from=_day_start(old.period_start_date),
        valid_to=_day_start(old.period_end_date + timedelta(days=1)),
        evaluated_at=old.control_date,
        evaluator_id=old.control_user_id,
        comment=old.comment,
    )
    evidence.attachments.add(*old.attachment.all())
    parent = old.control if source_type == 'CTRL' else old.indicator
    evidence.conformities.add(*parent.conformity.all())
    return evidence.pk


def migrate_points_to_inheritance(apps, schema_editor):
    LegacyControlPoint = apps.get_model('conformity', 'LegacyControlPoint')
    LegacyIndicatorPoint = apps.get_model('conformity', 'LegacyIndicatorPoint')
    ControlPoint = apps.get_model('conformity', 'ControlPoint')
    IndicatorPoint = apps.get_model('conformity', 'IndicatorPoint')
    Control = apps.get_model('conformity', 'Control')
    Indicator = apps.get_model('conformity', 'Indicator')
    Action = apps.get_model('conformity', 'Action')

    for control in Control.objects.all().iterator():
        control.requirements.add(
            *control.conformity.values_list('requirement_id', flat=True)
        )
    for indicator in Indicator.objects.all().iterator():
        indicator.requirements.add(
            *indicator.conformity.values_list('requirement_id', flat=True)
        )

    connection = schema_editor.connection
    qn = connection.ops.quote_name
    cp_table = qn(ControlPoint._meta.db_table)
    ip_table = qn(IndicatorPoint._meta.db_table)

    control_map = {}
    with connection.cursor() as cursor:
        for old in LegacyControlPoint.objects.select_related('control').iterator():
            evidence_id = _ensure_parent_evidence(
                apps, old, 'CTRL',
                {'OK': 'POS', 'NOK': 'NEG'}.get(old.status, 'NEU'),
            )
            cursor.execute(
                f"INSERT INTO {cp_table} "
                f"({qn('evidence_ptr_id')}, {qn('status')}, {qn('control_id')}) "
                "VALUES (%s, %s, %s)",
                [evidence_id, old.status, old.control_id],
            )
            control_map[old.pk] = evidence_id

        for old in LegacyIndicatorPoint.objects.select_related('indicator').iterator():
            evidence_id = _ensure_parent_evidence(
                apps, old, 'IND',
                {'OK': 'POS', 'CRIT': 'NEG'}.get(old.status, 'NEU'),
            )
            cursor.execute(
                f"INSERT INTO {ip_table} "
                f"({qn('evidence_ptr_id')}, {qn('status')}, {qn('value')}, {qn('indicator_id')}) "
                "VALUES (%s, %s, %s, %s)",
                [evidence_id, old.status, old.value, old.indicator_id],
            )

    for action in Action.objects.all().iterator():
        new_ids = [
            control_map[old_id]
            for old_id in action.associated_controlPoints.values_list('pk', flat=True)
            if old_id in control_map
        ]
        if new_ids:
            action.evidence_control_points.add(*new_ids)


def restore_legacy_points(apps, schema_editor):
    ControlPoint = apps.get_model('conformity', 'ControlPoint')
    IndicatorPoint = apps.get_model('conformity', 'IndicatorPoint')
    LegacyControlPoint = apps.get_model('conformity', 'LegacyControlPoint')
    LegacyIndicatorPoint = apps.get_model('conformity', 'LegacyIndicatorPoint')
    Control = apps.get_model('conformity', 'Control')
    Indicator = apps.get_model('conformity', 'Indicator')
    Action = apps.get_model('conformity', 'Action')

    control_map = {}
    for point in ControlPoint.objects.select_related('control').iterator():
        old = LegacyControlPoint.objects.create(
            id=point.pk,
            evidence_id=point.pk,
            control_id=point.control_id,
            control_date=point.evaluated_at,
            control_user_id=point.evaluator_id,
            period_start_date=timezone.localtime(point.valid_from).date(),
            period_end_date=(
                timezone.localtime(point.valid_to) - timedelta(microseconds=1)
            ).date(),
            status=point.status,
            comment=point.comment,
        )
        old.attachment.add(*point.attachments.all())
        control_map[point.pk] = old.pk
        if point.control_id:
            point.control.conformity.add(*point.conformities.all())

    for point in IndicatorPoint.objects.select_related('indicator').iterator():
        old = LegacyIndicatorPoint.objects.create(
            id=point.pk,
            evidence_id=point.pk,
            indicator_id=point.indicator_id,
            control_date=point.evaluated_at,
            control_user_id=point.evaluator_id,
            period_start_date=timezone.localtime(point.valid_from).date(),
            period_end_date=(
                timezone.localtime(point.valid_to) - timedelta(microseconds=1)
            ).date(),
            status=point.status,
            comment=point.comment,
            value=point.value,
        )
        old.attachment.add(*point.attachments.all())
        if point.indicator_id:
            point.indicator.conformity.add(*point.conformities.all())

    for action in Action.objects.all().iterator():
        old_ids = [
            control_map[new_id]
            for new_id in action.evidence_control_points.values_list('pk', flat=True)
            if new_id in control_map
        ]
        if old_ids:
            action.associated_controlPoints.add(*old_ids)


class Migration(migrations.Migration):

    dependencies = [
        ('conformity', '0073_evidence_models'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='ControlPoint',
            new_name='LegacyControlPoint',
        ),
        migrations.RenameModel(
            old_name='IndicatorPoint',
            new_name='LegacyIndicatorPoint',
        ),
        migrations.AddField(
            model_name='control',
            name='requirements',
            field=models.ManyToManyField(
                blank=True,
                help_text='Requirements targeted by this control. Concrete Conformity links live on Evidence.',
                related_name='controls',
                to='conformity.requirement',
            ),
        ),
        migrations.AddField(
            model_name='indicator',
            name='requirements',
            field=models.ManyToManyField(
                blank=True,
                help_text='Requirements targeted by this indicator. Concrete Conformity links live on Evidence.',
                related_name='indicators',
                to='conformity.requirement',
            ),
        ),
        migrations.CreateModel(
            name='ControlPoint',
            fields=[
                (
                    'evidence_ptr',
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to='conformity.evidence',
                    ),
                ),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('SCHD', 'Scheduled'),
                            ('TOBE', 'To evaluate'),
                            ('OK', 'Compliant'),
                            ('NOK', 'Non-Compliant'),
                            ('MISS', 'Missed'),
                        ],
                        default='SCHD',
                        max_length=4,
                    ),
                ),
                (
                    'control',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to='conformity.control',
                    ),
                ),
            ],
            options={'ordering': ['valid_to']},
            bases=('conformity.evidence',),
        ),
        migrations.CreateModel(
            name='IndicatorPoint',
            fields=[
                (
                    'evidence_ptr',
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to='conformity.evidence',
                    ),
                ),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('SCHD', 'Scheduled'),
                            ('TOBE', 'To evaluate'),
                            ('OK', 'Compliant'),
                            ('WARN', 'Warning'),
                            ('CRIT', 'Critical'),
                            ('MISS', 'Missed'),
                        ],
                        default='SCHD',
                        max_length=4,
                    ),
                ),
                ('value', models.IntegerField(null=True)),
                (
                    'indicator',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to='conformity.indicator',
                    ),
                ),
            ],
            bases=('conformity.evidence',),
        ),
        migrations.AddField(
            model_name='action',
            name='evidence_control_points',
            field=models.ManyToManyField(
                blank=True,
                related_name='actions_migration',
                to='conformity.controlpoint',
            ),
        ),
        migrations.RunPython(
            migrate_points_to_inheritance,
            restore_legacy_points,
        ),
        migrations.RemoveField(
            model_name='action',
            name='associated_controlPoints',
        ),
        migrations.RenameField(
            model_name='action',
            old_name='evidence_control_points',
            new_name='associated_controlPoints',
        ),
        migrations.AlterField(
            model_name='action',
            name='associated_controlPoints',
            field=models.ManyToManyField(
                blank=True,
                related_name='actions',
                to='conformity.controlpoint',
            ),
        ),
        migrations.RemoveField(
            model_name='control',
            name='conformity',
        ),
        migrations.RemoveField(
            model_name='indicator',
            name='conformity',
        ),
        migrations.DeleteModel(
            name='LegacyControlPoint',
        ),
        migrations.DeleteModel(
            name='LegacyIndicatorPoint',
        ),
    ]
