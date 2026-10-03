from django.db import migrations, models


def move_titles_to_evidence(apps, schema_editor):
    Evidence = apps.get_model('conformity', 'Evidence')
    ManualEvidence = apps.get_model('conformity', 'ManualEvidence')
    DocumentEvidence = apps.get_model('conformity', 'DocumentEvidence')

    for item in ManualEvidence.objects.all().iterator():
        Evidence.objects.filter(pk=item.pk).update(title=item.title)

    for item in DocumentEvidence.objects.all().iterator():
        Evidence.objects.filter(pk=item.pk).update(title=item.title)


class Migration(migrations.Migration):

    dependencies = [
        ('conformity', '0080_finding_optional_audit'),
    ]

    operations = [
        migrations.AddField(
            model_name='evidence',
            name='title',
            field=models.CharField(blank=True, max_length=256),
        ),
        migrations.RunPython(
            move_titles_to_evidence,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name='documentevidence',
            name='title',
        ),
        migrations.DeleteModel(
            name='ManualEvidence',
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
                    ('MAN', 'Evidence'),
                ],
                default='MAN',
                max_length=4,
            ),
        ),
    ]
