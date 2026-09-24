from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from datetime import datetime
from .models import ControlPoint, IndicatorPoint
from .services.audit import update_with_audit


class SanityCheckMiddleware:
    last_checked = None

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        self.run_daily_checks()
        return response

    def run_daily_checks(self):
        """Performs the daily integrity checks."""
        today = datetime.today().date()

        if SanityCheckMiddleware.last_checked != today:
            self.check_control_points(today)
            self.check_indicator_points(today)
            SanityCheckMiddleware.last_checked = today

    @staticmethod
    def check_control_points(today):
        """Checks and updates the status of ControlPoint."""

        """Update SCHD to TOBE when period start"""
        scheduled_controls = ControlPoint.objects.filter(period_start_date__lte=today,
                                                         period_end_date__gte=today,
                                                         status="SCHD")
        update_with_audit(scheduled_controls, status='TOBE')

        """Update expired TOBE to MISS """
        missed_controls = ControlPoint.objects.filter(period_start_date__lt=today,
                                                      period_end_date__lt=today,
                                                      status__in=["TOBE","SCHD"])
        update_with_audit(missed_controls, status='MISS')

    @staticmethod
    def check_indicator_points(today):
        """Checks and updates the status of IndicatorPoint."""

        """Update SCHD to TOBE when period start"""
        scheduled_indicators = IndicatorPoint.objects.filter(period_start_date__lte=today,
                                                         period_end_date__gte=today,
                                                         status="SCHD")
        update_with_audit(scheduled_indicators, status='TOBE')

        """Update expired TOBE to MISS """
        missed_indicators = IndicatorPoint.objects.filter(period_start_date__lt=today,
                                                      period_end_date__lt=today,
                                                      status__in=["TOBE","SCHD"])
        update_with_audit(missed_indicators, status='MISS')

# Connect the user login signal
@receiver(user_logged_in)
def update_on_login(sender, user, request, **kwargs):
    middleware = SanityCheckMiddleware(None)
    middleware.run_daily_checks()