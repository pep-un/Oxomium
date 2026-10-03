from django.db import migrations, models


def convert_manual_to_expert(apps, schema_editor):
    Evidence = apps.get_model('conformity', 'Evidence')
    ManualEvidence = apps.get_model('conformity', 'ManualEvidence')
    HumanEvidence = apps.get_model('conformity', 'HumanEvidence')
    DocumentEvidence = apps.get_model('conformity', 'DocumentEvidence')

    quote = schema_editor.connection.ops.quote_name
    human_table = quote(HumanEvidence._meta.db_table)
    ptr_column = quote(HumanEvidence._meta.get_field('evidence_ptr').column)
    decision_column = quote(HumanEvidence._meta.get_field('decision').column)

    # ManualEvidence already owns an Evidence parent row. Insert only the
    # HumanEvidence child row so PKs and every Evidence relation stay intact.
    with schema_editor.connection.cursor() as cursor:
        for item in ManualEvidence.objects.all().iterator():
            Evidence.objects.filter(pk=item.pk).update(
                evidence_title=item.title,
                source_type='HUM',
            )
            cursor.execute(
                f'INSERT INTO {human_table} ({ptr_column}, {decision_column}) VALUES (%s, %s)',
                [item.pk, item.result],
            )

    for item in DocumentEvidence.objects.all().iterator():
        Evidence.objects.filter(pk=item.pk).update(evidence_title=item.title)


class Migration(migrations.Migration):

    dependencies = [
        ('conformity', '0080_finding_optional_audit'),
    ]

    operations = [
        migrations.AddField(
            model_name='evidence',
            name='evidence_title',
            field=models.CharField(blank=True, max_length=256),
        ),
        migrations.AlterField(
            model_name='humanevidence',
            name='decision',
            field=models.CharField(
                choices=[
                    ('POS', 'Compliant'),
                    ('PAR', 'Partially compliant'),
                    ('NEG', 'Non-compliant'),
                    ('NEU', 'Inconclusive'),
                ],
                max_length=3,
            ),
        ),
        migrations.RunPython(
            convert_manual_to_expert,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name='documentevidence',
            name='title',
        ),
        migrations.DeleteModel(
            name='ManualEvidence',
        ),
        migrations.RenameField(
            model_name='evidence',
            old_name='evidence_title',
            new_name='title',
        ),
        migrations.AlterField(
            model_name='evidence',
            name='source_type',
            field=models.CharField(
                choices=[
                    ('CTRL', 'Periodic control'),
                    ('IND', 'Periodic indicator'),
                    ('HUM', 'Expert assessment'),
                    ('FIND', 'Finding'),
                    ('DOC', 'Document'),
                ],
                max_length=4,
            ),
        ),
    ]
