from datetime import datetime
from dateutil.relativedelta import relativedelta
from django.test import TestCase

from conformity.models import User, Control, ControlPoint
from conformity.middleware import SanityCheckMiddleware

class SanityCheckMiddlewareTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        """Set up test data for all tests."""
        today = datetime.today().date()

        # Create a user and a control instance as they are foreign keys in ControlPoint
        cls.user = User.objects.create_user(username='testuser', password='password')
        cls.control = Control.objects.create(title="Test Control")

        # Control points that should be marked as 'MISS'
        cls.missed_control_1 = ControlPoint.objects.create(
            control=cls.control,
            control_user=cls.user,
            period_start_date=today - relativedelta(days=10),
            period_end_date=today - relativedelta(days=1),  # missed yesterday
            status="TOBE"
        )
        cls.missed_control_3 = ControlPoint.objects.create(
            control=cls.control,
            control_user=cls.user,
            period_start_date=today - relativedelta(days=10),
            period_end_date=today - relativedelta(days=5),  # missed 5 days ago
            status="TOBE"
        )

        # Control points that should not be updated (not in TOBE status)
        cls.not_missed_control = ControlPoint.objects.create(
            control=cls.control,
            control_user=cls.user,
            period_start_date=today - relativedelta(days=10),
            period_end_date=today - relativedelta(days=5),  # missed but not in TOBE
            status="MISS"
        )
        cls.not_missed_control_2 = ControlPoint.objects.create(
            control=cls.control,
            control_user=cls.user,
            period_start_date=today - relativedelta(days=10),
            period_end_date=today,  # today is not miss
            status="TOBE"
        )

        # Control points that should be marked as 'TOBE'
        cls.scheduled_control_1 = ControlPoint.objects.create(
            control=cls.control,
            control_user=cls.user,
            period_start_date=today.replace(day=1),
            period_end_date=today.replace(day=1) + relativedelta(months=1) - relativedelta(days=1),
            status="SCHD"
        )
        cls.scheduled_control_2 = ControlPoint.objects.create(
            control=cls.control,
            control_user=cls.user,
            period_start_date=today.replace(day=1) - relativedelta(months=3),
            period_end_date=today.replace(day=1) + relativedelta(months=2),
            status="SCHD"
        )

        # Control point that should stay in SCHED
        cls.scheduled_control_3 = ControlPoint.objects.create(
            control=cls.control,
            control_user=cls.user,
            period_start_date=today + relativedelta(days=1),
            period_end_date=today + relativedelta(days=30),
            status="SCHD"
        )

        # Control point that should not be updated (not in SCHD status)
        cls.not_scheduled_control = ControlPoint.objects.create(
            control=cls.control,
            control_user=cls.user,
            period_start_date=today.replace(day=1),
            period_end_date=today.replace(day=1) + relativedelta(months=1) - relativedelta(days=1),
            status="TOBE"
        )

        # Control point that should not be updated (OK ou NOK)
        cls.ok_control = ControlPoint.objects.create(
            control=cls.control,
            control_user=cls.user,
            period_start_date=today.replace(day=1),
            period_end_date=today.replace(day=1) + relativedelta(months=1) - relativedelta(days=1),
            status="OK"
        )
        cls.nok_control = ControlPoint.objects.create(
            control=cls.control,
            control_user=cls.user,
            period_start_date=today.replace(day=1) - relativedelta(months=3),
            period_end_date=today.replace(day=1) - relativedelta(days=1),
            status="NOK"
        )

    def test_missed_controls_update(self):
        """Test that missed controls are updated to 'MISS'."""
        today = datetime.today().date()
        SanityCheckMiddleware.check_control_points(today)

        self.missed_control_1.refresh_from_db()
        self.not_missed_control_2.refresh_from_db()
        self.missed_control_3.refresh_from_db()

        self.assertEqual(self.missed_control_1.status, 'MISS')
        self.assertEqual(self.not_missed_control_2.status, 'TOBE')
        self.assertEqual(self.missed_control_3.status, 'MISS')

    def test_scheduled_controls_update(self):
        """Test that scheduled controls are updated to 'TOBE'."""
        today = datetime.today().date()
        SanityCheckMiddleware.check_control_points(today)

        self.scheduled_control_1.refresh_from_db()
        self.scheduled_control_2.refresh_from_db()
        self.scheduled_control_3.refresh_from_db()

        self.assertEqual(self.scheduled_control_1.status, 'TOBE')
        self.assertEqual(self.scheduled_control_2.status, 'TOBE')
        self.assertEqual(self.scheduled_control_3.status, 'SCHD')

    def test_no_update(self):
        """Test some control that should not be updated"""
        today = datetime.today().date()
        SanityCheckMiddleware.check_control_points(today)

        """Test a SCHD control that should not switch to TOBE"""
        self.scheduled_control_3.refresh_from_db()
        self.assertEqual(self.scheduled_control_3.status, 'SCHD')

        """Test that controls not in 'TOBE' or 'SCHD' are not updated."""
        self.not_missed_control.refresh_from_db()
        self.not_scheduled_control.refresh_from_db()

        self.assertEqual(self.not_missed_control.status, 'MISS')
        self.assertEqual(self.not_scheduled_control.status, 'TOBE')

        """Test that controls not in 'OK' or 'NOK' are not updated."""
        self.ok_control.refresh_from_db()
        self.nok_control.refresh_from_db()

        self.assertEqual(self.ok_control.status, 'OK')
        self.assertEqual(self.nok_control.status, 'NOK')