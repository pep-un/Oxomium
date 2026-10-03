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
                    ('MISS', 'Missed'),
                ],
                default='SCHD',
                max_length=4,
            ),
        ),
    ]
