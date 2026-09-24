"""Backfill unambiguous local codes while keeping legacy natural keys intact."""

from django.db import migrations


def backfill_requirement_codes(apps, schema_editor):
    Requirement = apps.get_model('conformity', 'Requirement')
    alias = schema_editor.connection.alias
    for requirement in Requirement.objects.using(alias).filter(code='').iterator():
        candidate = (requirement.name or '').rsplit('-', 1)[-1]
        # A long or empty segment cannot fit code (max_length=5); preserve it
        # for manual review instead of truncating or changing the natural key.
        if candidate and len(candidate) <= 5:
            Requirement.objects.using(alias).filter(pk=requirement.pk).update(code=candidate)


class Migration(migrations.Migration):
    dependencies = [('conformity', '0066_issue_103_model_safety')]

    operations = [
        migrations.RunPython(backfill_requirement_codes, migrations.RunPython.noop),
    ]
