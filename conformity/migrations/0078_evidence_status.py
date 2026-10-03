from django.db import migrations, models


def copy_point_status_to_evidence(apps, schema_editor):
    Evidence = apps.get_model('conformity', 'Evidence')
    for model_name in ('ControlPoint', 'IndicatorPoint'):
        Point = apps.get_model('conformity', model_name)
        for point in Point.objects.all().only('pk', 'status').iterator():
            Evidence.objects.filter(pk=point.pk).update(status=point.status)


class Migration(migrations.Migration):

    dependencies = [
        ('conformity', '0077_remove_periodic_source_organization'),
    ]

    operations = [
        migrations.AddField(
            model_name='evidence',
            name='status',
            field=models.CharField(
                choices=[
                    ('SCHD', 'Scheduled'),
                    ('TOBE', 'To evaluate'),
                    ('EVAL', 'Evaluated'),
                    ('OK', 'Compliant'),
                    ('NOK', 'Non-Compliant'),
                    ('WARN', 'Warning'),
                    ('CRIT', 'Critical'),
                    ('MISS', 'Missed'),
                ],
                default='SCHD',
                max_length=4,
            ),
        ),
        migrations.RunPython(
            copy_point_status_to_evidence,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name='controlpoint',
            name='status',
        ),
        migrations.RemoveField(
            model_name='indicatorpoint',
            name='status',
        ),
    ]
