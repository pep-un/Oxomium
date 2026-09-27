from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conformity', '0071_action_priority'),
    ]

    operations = [
        migrations.AddField(
            model_name='attachment',
            name='sha256',
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=64,
                null=True,
                unique=True,
            ),
        ),
    ]
