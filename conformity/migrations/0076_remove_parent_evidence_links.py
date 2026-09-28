from django.db import migrations
from django.db.models import F


def remove_parent_evidence_links(apps, schema_editor):
    Conformity = apps.get_model('conformity', 'Conformity')
    Evidence = apps.get_model('conformity', 'Evidence')

    parent_ids = Conformity.objects.exclude(
        requirement__rght=F('requirement__lft') + 1,
    ).values_list('pk', flat=True)

    Evidence.conformities.through.objects.filter(
        conformity_id__in=parent_ids,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('conformity', '0075_backfill_evidence_state'),
    ]

    operations = [
        migrations.RunPython(
            remove_parent_evidence_links,
            migrations.RunPython.noop,
        ),
    ]
