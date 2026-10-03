from django.db import migrations, models


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
        migrations.RemoveField(
            model_name='controlpoint',
            name='status',
        ),
        migrations.RemoveField(
            model_name='indicatorpoint',
            name='status',
        ),
    ]
