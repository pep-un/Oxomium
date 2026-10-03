from datetime import datetime, time

import django.db.models.deletion
from django.db import migrations, models
from django.utils import timezone


def _day_start(value):
    result = datetime.combine(value, time.min)
    return timezone.make_aware(result, timezone.get_current_timezone())


def _result_for_severity(severity):
    if severity == 'POS':
        return 'POS'
    if severity in {'CRT', 'MAJ', 'MIN'}:
        return 'NEG'
    return 'NEU'


def migrate_findings(apps, schema_editor):
    Finding = apps.get_model('conformity', 'Finding')
    FindingEvidence = apps.get_model('conformity', 'FindingEvidence')
    FindingRecord = apps.get_model('conformity', 'FindingRecord')
    Action = apps.get_model('conformity', 'Action')

    for finding in Finding.objects.select_related('audit').all().iterator():
        legacy_evidence = (
            FindingEvidence.objects
            .filter(finding_id=finding.pk)
            .first()
        )

        if legacy_evidence is not None:
            valid_from = legacy_evidence.valid_from
            valid_to = legacy_evidence.valid_to
            evaluated_at = legacy_evidence.evaluated_at
            evaluator_id = legacy_evidence.evaluator_id
            comment = legacy_evidence.comment
            conformity_ids = list(
                legacy_evidence.conformities.values_list('pk', flat=True)
            )
            attachment_ids = list(
                legacy_evidence.attachments.values_list('pk', flat=True)
            )
        else:
            source_date = (
                finding.audit.report_date
                or finding.audit.end_date
                or finding.audit.start_date
            )
            valid_from = _day_start(source_date) if source_date else timezone.now()
            valid_to = None
            evaluated_at = valid_from
            evaluator_id = None
            comment = ''
            conformity_ids = []
            attachment_ids = []

        if finding.archived and valid_to is None:
            valid_to = timezone.now()

        record = FindingRecord.objects.create(
            source_type='FIND',
            status='EVAL',
            result=_result_for_severity(finding.severity),
            valid_from=valid_from,
            valid_to=valid_to,
            evaluated_at=evaluated_at,
            evaluator_id=evaluator_id,
            comment=comment,
            name=finding.name,
            short_description=finding.short_description,
            description=finding.description,
            observation=finding.observation,
            recommendation=finding.recommendation,
            reference=finding.reference,
            audit_id=finding.audit_id,
            severity=finding.severity,
            cvss=finding.cvss,
            cvss_descriptor=finding.cvss_descriptor,
        )

        if conformity_ids:
            record.conformities.add(*conformity_ids)
        if attachment_ids:
            record.attachments.add(*attachment_ids)

        for action in Action.objects.filter(associated_findings=finding):
            action.migrated_findings.add(record)


class Migration(migrations.Migration):

    dependencies = [
        ('conformity', '0078_evidence_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='FindingRecord',
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
                ('name', models.CharField(blank=True, max_length=256)),
                ('short_description', models.CharField(max_length=256)),
                ('description', models.TextField(blank=True, max_length=4096)),
                ('observation', models.TextField(blank=True, max_length=4096)),
                ('recommendation', models.TextField(blank=True, max_length=4096)),
                ('reference', models.TextField(blank=True, max_length=4096)),
                (
                    'severity',
                    models.CharField(
                        choices=[
                            ('CRT', 'Critical non-conformity'),
                            ('MAJ', 'Major non-conformity'),
                            ('MIN', 'Minor non-conformity'),
                            ('OBS', 'Opportunity For Improvement'),
                            ('POS', 'Positive finding'),
                            ('OTHER', 'Other comment'),
                        ],
                        default='OBS',
                        max_length=5,
                    ),
                ),
                (
                    'cvss',
                    models.FloatField(
                        blank=True,
                        default=None,
                        null=True,
                        verbose_name='CVSS',
                    ),
                ),
                (
                    'cvss_descriptor',
                    models.CharField(
                        blank=True,
                        max_length=256,
                        verbose_name='CVSS Vector',
                    ),
                ),
                (
                    'audit',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to='conformity.audit',
                    ),
                ),
            ],
            options={
                'ordering': ['severity'],
            },
            bases=('conformity.evidence',),
        ),
        migrations.AddField(
            model_name='action',
            name='migrated_findings',
            field=models.ManyToManyField(
                blank=True,
                related_name='actions_migration',
                to='conformity.findingrecord',
            ),
        ),
        migrations.RunPython(
            migrate_findings,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name='action',
            name='associated_findings',
        ),
        migrations.DeleteModel(
            name='FindingEvidence',
        ),
        migrations.DeleteModel(
            name='Finding',
        ),
        migrations.RenameModel(
            old_name='FindingRecord',
            new_name='Finding',
        ),
        migrations.RenameField(
            model_name='action',
            old_name='migrated_findings',
            new_name='associated_findings',
        ),
        migrations.AlterField(
            model_name='action',
            name='associated_findings',
            field=models.ManyToManyField(
                blank=True,
                related_name='actions',
                to='conformity.finding',
            ),
        ),
    ]
