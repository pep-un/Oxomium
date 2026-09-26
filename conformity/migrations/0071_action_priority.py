# Generated for issue #99: add nullable action priority without backfilling existing rows.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conformity', '0070_alter_indicator_critical_default'),
    ]

    operations = [
        migrations.AddField(
            model_name='action',
            name='priority',
            field=models.PositiveSmallIntegerField(
                blank=True,
                choices=[
                    (1, 'Priority 1'),
                    (2, 'Priority 2'),
                    (3, 'Priority 3'),
                    (4, 'Priority 4'),
                    (5, 'Priority 5'),
                ],
                null=True,
            ),
        ),
    ]
