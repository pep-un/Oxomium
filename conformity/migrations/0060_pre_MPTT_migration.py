# migration 0060_pre_mptt.py
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('conformity', '0059_alter_finding_cvss_alter_finding_cvss_descriptor_and_more'),
    ]
    operations = [
        migrations.RenameField(
            model_name='requirement',
            old_name='level',
            new_name='legacy_level',
        ),
        migrations.RenameField(
            model_name='requirement',
            old_name='is_parent',
            new_name='legacy_is_parent',
        ),
    ]
