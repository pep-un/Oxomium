"""Enforce local Requirement codes after auditing production data."""

from django.db import migrations, models
from django.db.models import Count, Q


def validate_requirement_codes(apps, schema_editor):
    Requirement = apps.get_model('conformity', 'Requirement')
    rows = Requirement.objects.using(schema_editor.connection.alias)
    missing = list(rows.filter(code='').values_list('pk', flat=True)[:10])
    duplicates = list(
        rows.exclude(code='').values('framework_id', 'parent_id', 'code')
        .annotate(count=Count('pk')).filter(count__gt=1)[:10]
    )
    if missing or duplicates:
        raise RuntimeError(
            'Requirement code audit failed before adding unique constraints: '
            f'missing IDs={missing}; duplicate groups={duplicates}. '
            'Run python manage.py audit_requirement_codes and resolve collisions.'
        )


class Migration(migrations.Migration):
    dependencies = [('conformity', '0067_backfill_requirement_codes')]

    operations = [
        migrations.RunPython(validate_requirement_codes, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='requirement',
            constraint=models.UniqueConstraint(
                fields=('framework', 'code'),
                condition=Q(parent__isnull=True),
                name='uq_req_root_code',
            ),
        ),
        migrations.AddConstraint(
            model_name='requirement',
            constraint=models.UniqueConstraint(
                fields=('framework', 'parent', 'code'),
                condition=Q(parent__isnull=False),
                name='uq_req_sibling_code',
            ),
        ),
    ]
