from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from conformity.models import Indicator, IndicatorPoint


class IndicatorIndexTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='indicator-view-user', password='test-password'
        )
        self.client.force_login(self.user)
        self.indicator = Indicator.objects.create(
            name='Indicator without a current point', responsible=self.user
        )

    def test_missing_current_point_does_not_reverse_an_empty_pk(self):
        IndicatorPoint.objects.filter(indicator=self.indicator).delete()

        response = self.client.get(reverse('conformity:indicator_index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No measurement point for the current period.')
        self.assertContains(
            response,
            reverse('conformity:indicator_form', args=[self.indicator.pk]),
        )

    def test_existing_current_point_keeps_edit_link(self):
        IndicatorPoint.objects.filter(indicator=self.indicator).delete()
        today = timezone.localdate()
        point = IndicatorPoint.objects.create(
            indicator=self.indicator, period_start_date=today, period_end_date=today
        )

        response = self.client.get(reverse('conformity:indicator_index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, reverse('conformity:indicatorpoint_form', args=[point.pk])
        )
