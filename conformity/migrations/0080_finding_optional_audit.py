import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conformity', '0079_merge_finding_into_evidence'),
    ]

    operations = [
        migrations.AlterField(
            model_name='finding',
            name='audit',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='conformity.audit',
            ),
        ),
    ]
