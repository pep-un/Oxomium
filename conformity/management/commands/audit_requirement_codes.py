"""Report identifiers that prevent local-code uniqueness for requirements."""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from conformity.models import Requirement


class Command(BaseCommand):
    help = 'Audit missing requirement codes and duplicate codes among siblings.'

    def handle(self, *args, **options):
        missing = list(Requirement.objects.filter(code='').values_list('pk', flat=True))
        duplicate_groups = list(
            Requirement.objects.exclude(code='').values(
                'framework_id', 'parent_id', 'code'
            ).annotate(count=Count('pk')).filter(count__gt=1)
            .order_by('framework_id', 'parent_id', 'code')
        )
        self.stdout.write(f'Missing codes: {len(missing)}; IDs: {missing}')
        self.stdout.write(f'Duplicate sibling codes: {len(duplicate_groups)}')
        for group in duplicate_groups:
            self.stdout.write(
                f"framework={group['framework_id']} parent={group['parent_id']} "
                f"code={group['code']} count={group['count']}"
            )
        if missing or duplicate_groups:
            raise CommandError('Resolve requirement codes before adding uniqueness constraints.')
