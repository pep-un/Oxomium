from calendar import monthrange
from datetime import date

from django.db import transaction


def calendar_periods(year, frequency):
    """Return exact month-aligned periods, including leap-year February."""
    count = int(frequency)
    if count not in (1, 2, 4, 6, 12):
        raise ValueError(f'Unsupported control frequency: {frequency}')
    months_per_period = 12 // count
    for month in range(1, 13, months_per_period):
        end_month = month + months_per_period - 1
        yield date(year, month, 1), date(year, end_month, monthrange(year, end_month)[1])


def generate_controlpoints(control, year=None):
    """Reconcile open periods; retain completed evaluations and their evidence."""
    from conformity.models import Control, ControlPoint

    year = year or date.today().year
    desired = set(calendar_periods(year, control.frequency))
    with transaction.atomic():
        Control.objects.select_for_update().get(pk=control.pk)
        points = list(ControlPoint.objects.filter(
            control=control, period_start_date__year=year
        ))
        for point in points:
            pair = (point.period_start_date, point.period_end_date)
            if pair not in desired and point.status in (
                ControlPoint.Status.SCHEDULED, ControlPoint.Status.TOBEEVALUATED
            ) and not point.attachment.exists():
                point.delete()

        for start, end in sorted(desired):
            if not ControlPoint.objects.filter(
                control=control, period_start_date=start, period_end_date=end
            ).exists():
                ControlPoint.objects.create(
                    control=control, period_start_date=start, period_end_date=end
                )
