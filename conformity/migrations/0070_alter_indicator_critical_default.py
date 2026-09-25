# Generated for issue #146: keep the default Indicator scale coherent.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conformity', '0069_alter_conformity_options_alter_framework_options'),
    ]

    operations = [
        migrations.AlterField(
            model_name='indicator',
            name='critical',
            field=models.IntegerField(default=20),
        ),
    ]
