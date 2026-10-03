from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('conformity', '0076_remove_parent_evidence_links'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='control',
            name='organization',
        ),
        migrations.RemoveField(
            model_name='indicator',
            name='organization',
        ),
    ]
