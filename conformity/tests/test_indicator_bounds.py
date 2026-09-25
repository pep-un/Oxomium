from datetime import timedelta
from html.parser import HTMLParser

from auditlog.models import LogEntry
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from conformity.forms import IndicatorForm, IndicatorPointForm
from conformity.models import Indicator, IndicatorPoint


class InputParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.value_attrs = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input' and attrs.get('name') == 'value':
            self.value_attrs = attrs


class IndicatorBoundsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='bounds_user')
        self.client.force_login(self.user)
        self.indicator = Indicator.objects.create(
            name='Bounded indicator', responsible=self.user,
            worst=0, best=100, warning=80, critical=20,
        )
        IndicatorPoint.objects.filter(indicator=self.indicator).delete()
        today = timezone.localdate()
        self.point = IndicatorPoint.objects.create(
            indicator=self.indicator, period_start_date=today,
            period_end_date=today + timedelta(days=1),
        )
        self.url = reverse('conformity:indicatorpoint_form', args=[self.point.pk])

    def configure(self, worst, best, warning, critical):
        # Set fixture bounds without regenerating points via the indicator signal.
        Indicator.objects.filter(pk=self.indicator.pk).update(
            worst=worst, best=best, warning=warning, critical=critical,
        )
        self.indicator.refresh_from_db()
        self.point.refresh_from_db()

    def test_direct_save_rejects_out_of_bounds_before_data_or_audit_changes(self):
        for worst, best, warning, critical in ((0, 100, 80, 20), (100, 0, 20, 80), (-10, -2, -4, -8), (5, 5, 5, 5)):
            self.configure(worst, best, warning, critical)
            for value in (min(worst, best) - 1, max(worst, best) + 1):
                with self.subTest(worst=worst, best=best, value=value):
                    LogEntry.objects.all().delete()
                    self.point.value = value
                    with self.assertRaises(ValidationError) as caught:
                        self.point.save()
                    self.assertIn('value', caught.exception.message_dict)
                    self.point.refresh_from_db()
                    self.assertIsNone(self.point.value)
                    self.assertFalse(LogEntry.objects.exists())
                    with self.assertRaises(ValidationError):
                        IndicatorPoint.objects.create(
                            indicator=self.indicator, value=value,
                            period_start_date=self.point.period_start_date,
                            period_end_date=self.point.period_end_date,
                        )
                    self.assertEqual(IndicatorPoint.objects.filter(indicator=self.indicator).count(), 1)
                    self.assertFalse(LogEntry.objects.exists())

    def test_model_clean_and_form_reject_values_outside_bounds(self):
        for value in (-1, 101):
            with self.subTest(value=value):
                self.point.value = value
                with self.assertRaises(ValidationError) as caught:
                    self.point.full_clean()
                self.assertIn('value', caught.exception.message_dict)
                form = IndicatorPointForm(data={'value': value}, instance=self.point)
                self.assertFalse(form.is_valid())
                self.assertIn('value', form.errors)

    def test_inclusive_boundaries_and_thresholds_have_correct_status(self):
        configurations = (
            (0, 100, 80, 20, ((0, 'CRIT'), (20, 'CRIT'), (21, 'WARN'), (80, 'WARN'), (81, 'OK'), (100, 'OK'))),
            (100, 0, 20, 80, ((0, 'OK'), (19, 'OK'), (20, 'WARN'), (79, 'WARN'), (80, 'CRIT'), (100, 'CRIT'))),
            (-10, -2, -4, -8, ((-10, 'CRIT'), (-6, 'WARN'), (-2, 'OK'))),
            (5, 5, 5, 5, ((5, 'MISS'),)),
        )
        for worst, best, warning, critical, cases in configurations:
            self.configure(worst, best, warning, critical)
            for value, status in cases:
                with self.subTest(worst=worst, best=best, value=value):
                    response = self.client.post(self.url, {'value': value, 'comment': 'Measured'})
                    self.assertEqual(response.status_code, 302)
                    self.point.refresh_from_db()
                    self.assertEqual(self.point.value, value)
                    self.assertEqual(self.point.status, status)

    def test_http_rejection_preserves_existing_value_status_and_logs(self):
        self.point.value = 50
        self.point.save()
        LogEntry.objects.all().delete()
        for value in (-1, 101, '1.5', '', 'abc'):
            with self.subTest(value=value):
                response = self.client.post(self.url, {'value': value, 'comment': 'Invalid'})
                self.assertEqual(response.status_code, 200)
                self.assertIn('value', response.context['form'].errors)
                self.point.refresh_from_db()
                self.assertEqual(self.point.value, 50)
                self.assertEqual(self.point.status, 'WARN')
                self.assertEqual(self.point.comment, '')
                self.assertFalse(LogEntry.objects.get_for_object(self.point).exists())

    def test_html_bounds_match_backend_for_both_directions(self):
        for worst, best in ((0, 100), (100, 0), (-10, -2), (5, 5)):
            self.configure(worst, best, worst, best)
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200)
            attrs = InputParser(response.content.decode()).value_attrs
            self.assertEqual(attrs['type'], 'number')
            self.assertEqual(attrs['min'], str(min(worst, best)))
            self.assertEqual(attrs['max'], str(max(worst, best)))
            self.assertEqual(attrs['step'], '1')
            self.assertIn('required', attrs)

    def test_post_uses_latest_indicator_bounds(self):
        self.client.get(self.url)
        self.configure(0, 40, 30, 10)
        response = self.client.post(self.url, {'value': 50})
        self.assertEqual(response.status_code, 200)
        self.assertIn('value', response.context['form'].errors)
        self.assertEqual(InputParser(response.content.decode()).value_attrs['max'], '40')
        self.point.refresh_from_db()
        self.assertIsNone(self.point.value)

    def test_unmeasured_points_can_still_be_generated(self):
        self.assertIsNone(self.point.value)
        self.point.save()
        indicator = Indicator.objects.create(name='New indicator', responsible=self.user)
        self.assertTrue(IndicatorPoint.objects.filter(indicator=indicator, value__isnull=True).exists())

    def test_measurement_without_indicator_is_rejected(self):
        self.point.indicator = None
        self.point.value = 10
        with self.assertRaises(ValidationError) as caught:
            self.point.save()
        self.assertIn('value', caught.exception.message_dict)

    def test_zero_is_visible_and_audited_in_list_and_detail(self):
        self.configure(100, 0, 20, 80)
        LogEntry.objects.all().delete()
        response = self.client.post(self.url, {'value': 0})
        self.assertEqual(response.status_code, 302)
        self.point.refresh_from_db()
        self.assertEqual(self.point.status, 'OK')
        entry = LogEntry.objects.get_for_object(self.point).get()
        self.assertEqual(entry.actor, self.user)
        self.assertEqual(entry.changes['value'], ['None', '0'])
        self.assertEqual(entry.changes['status'], ['SCHD', 'OK'])
        for name in ('conformity:indicator_index', 'conformity:indicator_detail'):
            url = reverse(name, args=[self.indicator.pk]) if name.endswith('detail') else reverse(name)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            if name.endswith('detail'):
                self.assertContains(response, '<td class="text-center">0</td>', html=True)
                self.assertContains(response, 'Compliant')
            else:
                self.assertContains(response, 'text-success')
                self.assertContains(response, '0\n')
                self.assertNotContains(response, 'Add a value')

    def test_partial_value_save_persists_derived_status(self):
        self.point.value = 90
        self.point.save(update_fields=['value'])
        self.point.refresh_from_db()
        self.assertEqual(self.point.status, 'OK')

    def test_indicator_create_and_edit_forms_feed_point_bounds(self):
        data = {
            'name': 'Created through form', 'responsible': self.user.pk,
            'worst': 0, 'best': 100, 'warning': 80, 'critical': 20, 'frequency': 1,
        }
        response = self.client.post(reverse('conformity:indicator_create'), data)
        self.assertEqual(response.status_code, 302)
        indicator = Indicator.objects.get(name=data['name'])
        point = indicator.get_current_point()
        url = reverse('conformity:indicatorpoint_form', args=[point.pk])
        self.assertEqual(self.client.post(url, {'value': 100}).status_code, 302)
        response = self.client.post(
            reverse('conformity:indicator_form', args=[indicator.pk]),
            {**data, 'worst': 100, 'best': 0, 'warning': 20, 'critical': 80},
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.post(url, {'value': 101})
        self.assertEqual(response.status_code, 200)
        self.assertIn('value', response.context['form'].errors)
        self.assertEqual(self.client.post(url, {'value': 0}).status_code, 302)
        point.refresh_from_db()
        self.assertEqual((point.value, point.status), (0, 'OK'))

    def test_admin_rejects_out_of_bounds_measurement(self):
        self.user.is_staff = self.user.is_superuser = True
        self.user.save()
        url = reverse('admin:conformity_indicatorpoint_change', args=[self.point.pk])
        response = self.client.post(url, {
            'indicator': self.indicator.pk, 'value': 101, 'status': 'SCHD',
            'period_start_date': self.point.period_start_date.isoformat(),
            'period_end_date': self.point.period_end_date.isoformat(), '_save': 'Save',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('value', response.context['adminform'].form.errors)
        self.point.refresh_from_db()
        self.assertIsNone(self.point.value)


class IndicatorThresholdValidationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='threshold_user')
        self.client.force_login(self.user)

    def make_indicator(self, **thresholds):
        values = {
            'worst': 0, 'critical': 20, 'warning': 80, 'best': 100,
        }
        values.update(thresholds)
        return Indicator(
            name='Threshold indicator',
            responsible=self.user,
            **values,
        )

    def test_valid_ascending_and_descending_thresholds(self):
        configurations = (
            {'worst': 0, 'critical': 20, 'warning': 80, 'best': 100},
            {'worst': 100, 'critical': 80, 'warning': 20, 'best': 0},
            {'worst': -10, 'critical': -8, 'warning': -4, 'best': -2},
            {'worst': -2, 'critical': -4, 'warning': -8, 'best': -10},
        )
        for index, thresholds in enumerate(configurations):
            with self.subTest(**thresholds):
                indicator = self.make_indicator(**thresholds)
                indicator.name = f'Valid threshold indicator {index}'
                indicator.full_clean()
                indicator.save()
                self.assertIsNotNone(indicator.pk)

    def test_equal_adjacent_thresholds_are_rejected(self):
        configurations = (
            # Ascending: equality at each adjacent boundary.
            {'worst': 0, 'critical': 0, 'warning': 80, 'best': 100},
            {'worst': 0, 'critical': 20, 'warning': 20, 'best': 100},
            {'worst': 0, 'critical': 20, 'warning': 100, 'best': 100},
            # Descending: equality at each adjacent boundary.
            {'worst': 100, 'critical': 100, 'warning': 20, 'best': 0},
            {'worst': 100, 'critical': 80, 'warning': 80, 'best': 0},
            {'worst': 100, 'critical': 80, 'warning': 0, 'best': 0},
        )
        for thresholds in configurations:
            with self.subTest(**thresholds):
                indicator = self.make_indicator(**thresholds)
                with self.assertRaises(ValidationError) as caught:
                    indicator.full_clean()
                self.assertIn('critical', caught.exception.message_dict)
                self.assertIn('warning', caught.exception.message_dict)

    def test_equal_outer_bounds_are_rejected(self):
        indicator = self.make_indicator(
            worst=5, critical=5, warning=5, best=5,
        )
        with self.assertRaises(ValidationError) as caught:
            indicator.full_clean()
        self.assertIn('best', caught.exception.message_dict)

        with self.assertRaises(ValidationError):
            indicator.save()
        self.assertIsNone(indicator.pk)

    def test_mixed_or_out_of_range_threshold_order_is_rejected(self):
        invalid_configurations = (
            {'worst': 0, 'critical': 90, 'warning': 20, 'best': 100},
            {'worst': 100, 'critical': 20, 'warning': 80, 'best': 0},
            {'worst': 0, 'critical': -1, 'warning': 80, 'best': 100},
            {'worst': 100, 'critical': 80, 'warning': -1, 'best': 0},
        )
        for thresholds in invalid_configurations:
            with self.subTest(**thresholds):
                indicator = self.make_indicator(**thresholds)
                with self.assertRaises(ValidationError) as caught:
                    indicator.full_clean()
                self.assertIn('critical', caught.exception.message_dict)
                self.assertIn('warning', caught.exception.message_dict)

    def test_direct_save_rejects_invalid_changes_without_persisting_them(self):
        indicator = self.make_indicator()
        indicator.save()
        indicator.critical = 90
        indicator.warning = 20

        with self.assertRaises(ValidationError):
            indicator.save()

        indicator.refresh_from_db()
        self.assertEqual((indicator.critical, indicator.warning), (20, 80))

    def test_indicator_form_orders_thresholds_from_worst_to_best(self):
        form = IndicatorForm(instance=self.make_indicator())
        fields = list(form.fields)
        self.assertEqual(
            fields[4:8],
            ['worst', 'critical', 'warning', 'best'],
        )

    def test_indicator_form_surfaces_threshold_errors(self):
        form = IndicatorForm(data={
            'name': 'Invalid form indicator',
            'responsible': self.user.pk,
            'worst': 0,
            'critical': 90,
            'warning': 20,
            'best': 100,
            'frequency': Indicator.Frequency.YEARLY,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('critical', form.errors)
        self.assertIn('warning', form.errors)

    def test_admin_surfaces_threshold_errors(self):
        self.user.is_staff = self.user.is_superuser = True
        self.user.save()
        indicator = self.make_indicator()
        indicator.save()

        response = self.client.post(
            reverse('admin:conformity_indicator_change', args=[indicator.pk]),
            {
                'name': indicator.name,
                'goal': '',
                'source': '',
                'formula': '',
                'worst': 0,
                'best': 100,
                'warning': 20,
                'critical': 90,
                'responsible': self.user.pk,
                'organization': '',
                'conformity': [],
                'frequency': Indicator.Frequency.YEARLY,
                '_save': 'Save',
            },
        )

        self.assertEqual(response.status_code, 200)
        errors = response.context['adminform'].form.errors
        self.assertIn('critical', errors)
        self.assertIn('warning', errors)
        indicator.refresh_from_db()
        self.assertEqual((indicator.critical, indicator.warning), (20, 80))

    def test_default_thresholds_are_valid(self):
        indicator = Indicator(name='Default threshold indicator', responsible=self.user)
        self.assertEqual(
            (indicator.worst, indicator.critical, indicator.warning, indicator.best),
            (0, 20, 80, 100),
        )
        indicator.full_clean()
        indicator.save()

    def test_threshold_ranges_are_displayed_without_overlap(self):
        configurations = (
            (
                {'worst': 0, 'critical': 20, 'warning': 80, 'best': 100},
                '↑ Higher is better',
                ('0 – 20', '21 – 80', '81 – 100'),
            ),
            (
                {'worst': 100, 'critical': 80, 'warning': 20, 'best': 0},
                '↓ Lower is better',
                ('100 – 80', '79 – 20', '19 – 0'),
            ),
        )
        for index, (thresholds, direction, ranges) in enumerate(configurations):
            with self.subTest(**thresholds):
                indicator = self.make_indicator(**thresholds)
                indicator.name = f'Range display indicator {index}'
                indicator.save()

                self.assertEqual(
                    tuple((item['start'], item['end']) for item in indicator.threshold_ranges),
                    tuple(
                        tuple(int(value) for value in range_text.split(' – '))
                        for range_text in ranges
                    ),
                )

                for name in ('conformity:indicator_index', 'conformity:indicator_detail'):
                    url = (
                        reverse(name, args=[indicator.pk])
                        if name.endswith('detail')
                        else reverse(name)
                    )
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 200)
                    self.assertContains(response, direction)
                    for expected_range in ranges:
                        self.assertContains(response, expected_range)
