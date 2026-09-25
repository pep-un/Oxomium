# Generated for issue #146: keep the default Indicator scale coherent.

from django.db import migrations, models


def normalize_legacy_default_thresholds(apps, schema_editor):
    """Fix indicators that still use the historical inconsistent defaults."""
    Indicator = apps.get_model('conformity', 'Indicator')
    Indicator.objects.filter(
        worst=0,
        critical=90,
        warning=80,
        best=100,
    ).update(critical=20)


class Migration(migrations.Migration):

    dependencies = [
        ('conformity', '0069_alter_conformity_options_alter_framework_options'),
    ]

    operations = [
        migrations.RunPython(
            normalize_legacy_default_thresholds,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name='indicator',
            name='critical',
            field=models.IntegerField(default=20),
        ),
    ]
