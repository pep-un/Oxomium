from django.db import migrations


def backfill_evidence_state(apps, schema_editor):
    Conformity = apps.get_model('conformity', 'Conformity')

    # Preserve states already produced by the new Evidence engine.
    queryset = Conformity.objects.filter(evidence_state='NONE').exclude(status__isnull=True)

    queryset.filter(status__gte=100).update(evidence_state='COMP')
    queryset.filter(status__lte=0).update(evidence_state='NONC')
    queryset.filter(status__gt=0, status__lt=100).update(evidence_state='PART')


def reverse_backfill(apps, schema_editor):
    Conformity = apps.get_model('conformity', 'Conformity')
    Conformity.objects.filter(
        evidence_state__in=['COMP', 'NONC', 'PART'],
    ).update(evidence_state='NONE')


class Migration(migrations.Migration):

    dependencies = [
        ('conformity', '0074_evidence_point_inheritance'),
    ]

    operations = [
        migrations.RunPython(backfill_evidence_state, reverse_backfill),
    ]
