from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from conformity.models import (
    Conformity, Control, ControlPoint, DocumentEvidence, Evidence, Framework,
    HumanEvidence, Indicator, IndicatorPoint, ManualEvidence, Organization,
    Requirement,
)


class EvidenceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('evidence-user', password='test')
        self.framework = Framework.objects.create(name='Evidence framework')
        self.root = Requirement.objects.create(
            framework=self.framework, code='E', title='Evidence root'
        )
        self.leaf = Requirement.objects.create(
            framework=self.framework, parent=self.root, code='E1', title='Evidence leaf'
        )
        self.organization = Organization.objects.create(name='Evidence organization')
        self.parent = Conformity.objects.create(
            organization=self.organization, requirement=self.root
        )
        self.conformity = Conformity.objects.create(
            organization=self.organization, requirement=self.leaf
        )
        self.now = timezone.now()

    def evidence(self, result, start=None, end=None):
        item = Evidence.objects.create(
            source_type=Evidence.SourceType.MANUAL,
            result=result,
            valid_from=start or self.now - timedelta(hours=1),
            valid_to=end,
        )
        item.conformities.add(self.conformity)
        return item

    def test_half_open_validity_and_validation(self):
        item = self.evidence(
            Evidence.Result.POSITIVE,
            self.now - timedelta(days=1), self.now + timedelta(days=1),
        )
        self.assertTrue(item.is_valid_at(item.valid_from))
        self.assertFalse(item.is_valid_at(item.valid_to))
        self.assertIn(item, Evidence.objects.valid_at(item.valid_from))
        self.assertNotIn(item, Evidence.objects.valid_at(item.valid_to))

        item.valid_to = item.valid_from
        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_no_positive_negative_and_mixed_evaluation(self):
        self.assertEqual(
            self.conformity.evaluate_evidence(), Conformity.EvidenceState.NOT_EVALUATED
        )
        positive = self.evidence(Evidence.Result.POSITIVE)
        self.conformity.refresh_from_db()
        self.assertEqual(self.conformity.evidence_state, Conformity.EvidenceState.COMPLIANT)
        self.assertEqual(self.conformity.status, 100)

        negative = self.evidence(Evidence.Result.NEGATIVE)
        self.conformity.refresh_from_db()
        self.assertEqual(self.conformity.evidence_state, Conformity.EvidenceState.INCONCLUSIVE)
        self.assertIsNone(self.conformity.status)

        positive.valid_to = self.now
        positive.save(update_fields=['valid_to'])
        self.conformity.refresh_from_db()
        self.assertEqual(self.conformity.evidence_state, Conformity.EvidenceState.NON_COMPLIANT)
        self.assertEqual(self.conformity.status, 0)
        self.assertEqual(
            self.conformity.status_justification, Conformity.StatusJustification.EVIDENCE
        )
        self.assertTrue(negative.is_valid_at())

    def test_neutral_evidence_does_not_create_consensus(self):
        self.evidence(Evidence.Result.NEUTRAL)
        self.conformity.refresh_from_db()
        self.assertEqual(
            self.conformity.evidence_state, Conformity.EvidenceState.NOT_EVALUATED
        )
        self.assertIsNone(self.conformity.status)

    def test_removing_evidence_recalculates_previous_conformity(self):
        item = self.evidence(Evidence.Result.POSITIVE)
        item.conformities.remove(self.conformity)
        self.conformity.refresh_from_db()
        self.assertEqual(
            self.conformity.evidence_state, Conformity.EvidenceState.NOT_EVALUATED
        )

    def test_human_arbitration_and_automatic_invalidation(self):
        self.evidence(Evidence.Result.POSITIVE)
        negative = self.evidence(Evidence.Result.NEGATIVE)
        human = HumanEvidence.objects.create(
            decision=HumanEvidence.Decision.PARTIAL,
            valid_from=self.now - timedelta(minutes=30),
            evaluator=self.user,
            comment='Reviewed conflicting evidence.',
        )
        human.conformities.add(self.conformity)
        self.conformity.refresh_from_db()
        self.assertEqual(self.conformity.evidence_state, Conformity.EvidenceState.PARTIAL)

        negative.valid_to = self.now
        negative.save(update_fields=['valid_to'])
        human.refresh_from_db()
        self.assertIsNotNone(human.valid_to)
        self.assertFalse(human.is_valid_at())
        self.conformity.refresh_from_db()
        self.assertEqual(self.conformity.evidence_state, Conformity.EvidenceState.COMPLIANT)

    def test_human_can_arbitrate_existing_mixed_evidence(self):
        self.evidence(Evidence.Result.POSITIVE)
        self.evidence(Evidence.Result.NEGATIVE)
        human = HumanEvidence.objects.create(
            decision=HumanEvidence.Decision.COMPLIANT,
            valid_from=self.now,
            evaluator=self.user,
        )
        human.conformities.add(self.conformity)
        human.refresh_from_db()
        self.assertIsNone(human.valid_to)
        self.conformity.refresh_from_db()
        self.assertEqual(self.conformity.evidence_state, Conformity.EvidenceState.COMPLIANT)

        later_negative = Evidence.objects.create(
            source_type=Evidence.SourceType.MANUAL,
            result=Evidence.Result.NEGATIVE,
            valid_from=self.now - timedelta(minutes=1),
        )
        later_negative.conformities.add(self.conformity)
        human.refresh_from_db()
        self.assertIsNotNone(human.valid_to)

    def test_later_control_result_invalidates_human_arbitration(self):
        control = Control.objects.create(
            title='Human-arbitrated control', organization=self.organization
        )
        control.conformity.add(self.conformity)
        point = ControlPoint.objects.create(
            control=control,
            period_start_date=date.today() - timedelta(days=1),
            period_end_date=date.today() + timedelta(days=1),
            status=ControlPoint.Status.COMPLIANT,
        )
        human = HumanEvidence.objects.create(
            decision=HumanEvidence.Decision.COMPLIANT,
            valid_from=self.now,
            evaluator=self.user,
        )
        human.conformities.add(self.conformity)

        point.status = ControlPoint.Status.NONCOMPLIANT
        point.save(update_fields=['status'])
        human.refresh_from_db()
        point.refresh_from_db()
        self.assertIsNotNone(human.valid_to)
        self.assertEqual(point.result, Evidence.Result.NEGATIVE)

    def test_non_result_control_update_keeps_human_arbitration(self):
        control = Control.objects.create(
            title='Documented control', organization=self.organization
        )
        control.conformity.add(self.conformity)
        point = ControlPoint.objects.create(
            control=control,
            period_start_date=date.today() - timedelta(days=1),
            period_end_date=date.today() + timedelta(days=1),
            status=ControlPoint.Status.NONCOMPLIANT,
        )
        self.evidence(Evidence.Result.POSITIVE)
        human = HumanEvidence.objects.create(
            decision=HumanEvidence.Decision.COMPLIANT,
            valid_from=self.now,
            evaluator=self.user,
        )
        human.conformities.add(self.conformity)

        point.comment = 'More context, but no new result.'
        point.save(update_fields=['comment'])
        human.refresh_from_db()
        self.assertIsNone(human.valid_to)

    def test_control_point_is_evidence_without_losing_business_fields(self):
        control = Control.objects.create(
            title='Access review', organization=self.organization
        )
        control.conformity.add(self.conformity)
        point = ControlPoint.objects.create(
            control=control,
            period_start_date=date.today() - timedelta(days=1),
            period_end_date=date.today() + timedelta(days=1),
            status=ControlPoint.Status.NONCOMPLIANT,
            comment='Access not removed.',
        )
        point.refresh_from_db()
        self.assertTrue(issubclass(ControlPoint, Evidence))
        self.assertEqual(point.result, Evidence.Result.NEGATIVE)
        self.assertEqual(point.comment, 'Access not removed.')
        self.assertEqual(list(point.conformities.all()), [self.conformity])

    def test_indicator_point_is_evidence_and_preserves_threshold_logic(self):
        indicator = Indicator.objects.create(
            name='Coverage', responsible=self.user, organization=self.organization,
            worst=0, critical=20, warning=80, best=100,
        )
        indicator.conformity.add(self.conformity)
        point = IndicatorPoint.objects.create(
            indicator=indicator,
            period_start_date=date.today() - timedelta(days=1),
            period_end_date=date.today() + timedelta(days=1),
            value=10,
        )
        point.refresh_from_db()
        self.assertEqual(point.status, IndicatorPoint.Status.CRITICAL)
        self.assertTrue(issubclass(IndicatorPoint, Evidence))
        self.assertEqual(point.result, Evidence.Result.NEGATIVE)

    def test_human_evidence_view_requires_login_and_records_author(self):
        url = reverse('conformity:human_evidence_create', args=[self.conformity.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.user)
        response = self.client.post(url, {
            'decision': HumanEvidence.Decision.COMPLIANT,
            'valid_from': self.now.strftime('%Y-%m-%d %H:%M:%S'),
            'valid_to': '',
            'comment': 'Expert review',
        })
        self.assertRedirects(
            response, reverse('conformity:conformity_form', args=[self.conformity.pk])
        )
        human = HumanEvidence.objects.get()
        self.assertEqual(human.evaluator, self.user)
        self.assertIn(self.conformity, human.conformities.all())

    def test_additional_evidence_types_share_common_engine(self):
        manual = ManualEvidence.objects.create(
            title='Supplier attestation', result=Evidence.Result.POSITIVE,
            valid_from=self.now,
        )
        manual.conformities.add(self.conformity)
        self.assertEqual(manual.source_type, Evidence.SourceType.MANUAL)
        self.assertTrue(issubclass(DocumentEvidence, Evidence))
