from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from conformity.models import (
    Conformity, Control, ControlPoint, DocumentEvidence, Evidence, Framework,
    HumanEvidence, Indicator, IndicatorPoint, Organization,
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
            source_type=Evidence.SourceType.GENERIC,
            result=result,
            valid_from=start or self.now - timedelta(hours=1),
            valid_to=end,
        )
        item.conformities.add(self.conformity)
        return item

    def test_evidence_cannot_be_associated_with_parent_conformity(self):
        item = Evidence.objects.create(
            source_type=Evidence.SourceType.GENERIC,
            result=Evidence.Result.POSITIVE,
            valid_from=self.now - timedelta(hours=1),
        )

        with self.assertRaises(ValidationError), transaction.atomic():
            item.conformities.add(self.parent)

        with self.assertRaises(ValidationError), transaction.atomic():
            self.parent.evidence.add(item)

        self.assertFalse(item.conformities.exists())

    def test_evidence_create_url_rejects_parent_conformity(self):
        self.client.force_login(self.user)

        for route_name in (
            'human_evidence_create',
            'evidence_create',
            'document_evidence_create',
        ):
            with self.subTest(route=route_name):
                response = self.client.get(
                    reverse(f'conformity:{route_name}', args=[self.parent.pk])
                )
                self.assertEqual(response.status_code, 404)

    def test_control_point_only_targets_leaf_conformities(self):
        control = Control.objects.create(
            title='Leaf-only control',
        )
        control.conformity.add(self.parent, self.conformity)

        point = ControlPoint.objects.create(
            control=control,
            period_start_date=date.today() - timedelta(days=1),
            period_end_date=date.today() + timedelta(days=1),
            status=Evidence.Status.EVALUATED, result=Evidence.Result.POSITIVE,
        )

        self.assertEqual(
            list(point.conformities.order_by('pk')),
            [self.conformity],
        )

    def test_indicator_point_only_targets_leaf_conformities(self):
        indicator = Indicator.objects.create(
            name='Leaf-only indicator',
            responsible=self.user,
            worst=0,
            critical=20,
            warning=80,
            best=100,
        )
        indicator.conformity.add(self.parent, self.conformity)

        point = IndicatorPoint.objects.create(
            indicator=indicator,
            period_start_date=date.today() - timedelta(days=1),
            period_end_date=date.today() + timedelta(days=1),
            value=90,
        )

        self.assertEqual(
            list(point.conformities.order_by('pk')),
            [self.conformity],
        )

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

    def test_attaching_existing_contradictory_evidence_invalidates_human(self):
        self.evidence(Evidence.Result.POSITIVE)
        self.evidence(Evidence.Result.NEGATIVE)
        human = HumanEvidence.objects.create(
            decision=HumanEvidence.Decision.COMPLIANT,
            valid_from=self.now,
            evaluator=self.user,
        )
        human.conformities.add(self.conformity)

        existing_negative = Evidence.objects.create(
            source_type=Evidence.SourceType.GENERIC,
            result=Evidence.Result.NEGATIVE,
            valid_from=self.now - timedelta(days=1),
        )
        # It predates the human decision but becomes relevant only now.
        existing_negative.conformities.add(self.conformity)

        human.refresh_from_db()
        self.assertIsNotNone(human.valid_to)
        self.conformity.refresh_from_db()
        self.assertEqual(
            self.conformity.evidence_state,
            Conformity.EvidenceState.INCONCLUSIVE,
        )

    def test_evidence_status_change_propagates_to_parent(self):
        positive = self.evidence(Evidence.Result.POSITIVE)
        self.conformity.refresh_from_db()
        self.parent.refresh_from_db()
        self.assertEqual(self.conformity.status, 100)
        self.assertEqual(self.parent.status, 100)
        self.assertEqual(
            self.parent.evidence_state,
            Conformity.EvidenceState.COMPLIANT,
        )

        positive.result = Evidence.Result.NEGATIVE
        positive.save(update_fields=['result'])
        self.conformity.refresh_from_db()
        self.parent.refresh_from_db()
        self.assertEqual(self.conformity.status, 0)
        self.assertEqual(self.parent.status, 0)
        self.assertEqual(
            self.parent.evidence_state,
            Conformity.EvidenceState.NON_COMPLIANT,
        )

    def test_parent_aggregate_uses_partial_evidence_state(self):
        second_leaf = Requirement.objects.create(
            framework=self.framework,
            parent=self.root,
            code='E2',
            title='Second Evidence leaf',
        )
        second = Conformity.objects.create(
            organization=self.organization,
            requirement=second_leaf,
        )

        positive = Evidence.objects.create(
            source_type=Evidence.SourceType.GENERIC,
            result=Evidence.Result.POSITIVE,
            valid_from=self.now - timedelta(hours=1),
        )
        positive.conformities.add(self.conformity)

        negative = Evidence.objects.create(
            source_type=Evidence.SourceType.GENERIC,
            result=Evidence.Result.NEGATIVE,
            valid_from=self.now - timedelta(hours=1),
        )
        negative.conformities.add(second)

        self.parent.refresh_from_db()
        self.assertEqual(
            self.parent.evidence_state,
            Conformity.EvidenceState.PARTIAL,
        )

    def test_parent_conformity_form_lists_descendant_evidence_with_ownership(self):
        second_leaf = Requirement.objects.create(
            framework=self.framework,
            parent=self.root,
            code='E2',
            title='Second Evidence leaf',
        )
        second = Conformity.objects.create(
            organization=self.organization,
            requirement=second_leaf,
        )

        shared = Evidence.objects.create(source_type=Evidence.SourceType.GENERIC, 
            title='Shared child evidence',
            result=Evidence.Result.POSITIVE,
            valid_from=self.now - timedelta(hours=1),
        )
        shared.conformities.add(self.conformity, second)

        self.client.force_login(self.user)
        response = self.client.get(
            reverse('conformity:conformity_form', args=[self.parent.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Evidence from descendant requirements')
        self.assertContains(response, self.leaf.full_path)
        self.assertContains(response, self.leaf.title)
        self.assertContains(response, second_leaf.full_path)
        self.assertContains(response, second_leaf.title)
        self.assertContains(
            response,
            reverse('conformity:conformity_form', args=[self.conformity.pk]),
        )
        self.assertContains(
            response,
            reverse('conformity:conformity_form', args=[second.pk]),
        )
        self.assertEqual(
            list(response.context['active_evidence']),
            [shared],
        )

    def test_generic_evidence_editor_shows_all_requirement_context_cards(self):
        second_leaf = Requirement.objects.create(
            framework=self.framework,
            parent=self.root,
            code='E2',
            title='Second Evidence leaf',
        )
        second = Conformity.objects.create(
            organization=self.organization,
            requirement=second_leaf,
        )
        manual = Evidence.objects.create(source_type=Evidence.SourceType.GENERIC, 
            title='Shared generic evidence',
            result=Evidence.Result.POSITIVE,
            valid_from=self.now - timedelta(hours=1),
        )
        manual.conformities.add(self.conformity, second)

        self.client.force_login(self.user)
        response = self.client.get(
            reverse('conformity:evidence_form', args=[manual.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.framework.name, count=1)
        self.assertContains(response, self.leaf.title)
        self.assertContains(response, second_leaf.title)
        self.assertContains(response, self.leaf.full_path)
        self.assertContains(response, second_leaf.full_path)
        self.assertContains(response, 'col-12 col-lg-6', count=2)
        self.assertContains(response, 'name="attachments"')
        self.assertContains(response, 'Add another document')

    def test_requirement_context_compacts_shared_framework_and_section(self):
        section = Requirement.objects.create(
            framework=self.framework,
            parent=self.root,
            code='SEC',
            title='Shared section',
        )
        first_leaf = Requirement.objects.create(
            framework=self.framework,
            parent=section,
            code='1',
            title='First grouped leaf',
        )
        second_leaf = Requirement.objects.create(
            framework=self.framework,
            parent=section,
            code='2',
            title='Second grouped leaf',
        )
        first = Conformity.objects.create(
            organization=self.organization,
            requirement=first_leaf,
        )
        second = Conformity.objects.create(
            organization=self.organization,
            requirement=second_leaf,
        )
        manual = Evidence.objects.create(source_type=Evidence.SourceType.GENERIC, 
            title='Grouped requirements',
            result=Evidence.Result.POSITIVE,
            valid_from=self.now - timedelta(hours=1),
        )
        manual.conformities.add(first, second)

        self.client.force_login(self.user)
        response = self.client.get(
            reverse('conformity:evidence_form', args=[manual.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.framework.name, count=1)
        self.assertContains(response, 'Shared section', count=1)
        self.assertContains(response, 'First grouped leaf')
        self.assertContains(response, 'Second grouped leaf')
        self.assertContains(response, 'Add requirement')

    def test_control_point_editor_shows_requirement_and_control_context(self):
        control = Control.objects.create(
            title='Context control',
            description='Control context description',
            frequency=Control.Frequency.QUARTERLY,
            level=Control.Level.SECOND,
        )
        control.conformity.add(self.conformity)
        point = next(
            item for item in control.get_controlpoint()
            if item.is_current_period()
        )

        self.client.force_login(self.user)
        response = self.client.get(
            reverse('conformity:controlpoint_form', args=[point.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.framework.name)
        self.assertContains(response, self.leaf.title)
        self.assertContains(response, '<span class="h4 mb-0">Periodic control</span>', html=True)
        self.assertContains(response, 'Context control')
        self.assertContains(response, 'Quarterly')
        self.assertContains(response, '2nd level')
        self.assertContains(response, 'Periodic control result')
        self.assertContains(response, 'Attachments')

    def test_indicator_point_editor_shows_requirement_and_indicator_context(self):
        indicator = Indicator.objects.create(
            name='Context indicator',
            goal='Measure the control objective',
            source='SIEM export',
            formula='Compliant systems / total systems * 100',
            responsible=self.user,
            frequency=Indicator.Frequency.MONTHLY,
            worst=0,
            critical=20,
            warning=80,
            best=100,
        )
        indicator.conformity.add(self.conformity)
        point = indicator.get_current_point()

        self.client.force_login(self.user)
        response = self.client.get(
            reverse('conformity:indicatorpoint_form', args=[point.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.framework.name)
        self.assertContains(response, self.leaf.title)
        self.assertContains(response, '<span class="h4 mb-0">Periodic indicator</span>', html=True)
        self.assertContains(response, 'Context indicator')
        self.assertContains(response, 'Monthly')
        self.assertContains(response, 'Responsible')
        self.assertContains(response, self.user.username)
        self.assertContains(response, 'Source of data')
        self.assertContains(response, 'SIEM export')
        self.assertContains(response, 'Formula or calculation')
        self.assertContains(response, 'Compliant systems / total systems * 100')
        self.assertContains(response, 'Thresholds')
        self.assertContains(response, 'Critical')
        self.assertContains(response, 'Warning')
        self.assertContains(response, 'Compliant')
        self.assertContains(response, 'Periodic indicator result')
        self.assertContains(response, 'card border-primary mb-4')
        self.assertContains(response, 'card-header text-bg-primary')
        self.assertContains(response, 'name="value"')
        self.assertContains(response, 'Attachments')

    def test_human_evidence_editor_has_no_periodic_source_card(self):
        human = HumanEvidence.objects.create(
            decision=HumanEvidence.Decision.PARTIAL,
            valid_from=self.now - timedelta(hours=1),
            evaluator=self.user,
        )
        human.conformities.add(self.conformity)

        self.client.force_login(self.user)
        response = self.client.get(
            reverse('conformity:evidence_form', args=[human.pk])
        )
        html = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn(self.framework.name, html)
        self.assertIn(self.leaf.title, html)
        self.assertNotIn('<span class="h4 mb-0">Periodic control</span>', html)
        self.assertNotIn('<span class="h4 mb-0">Periodic indicator</span>', html)
        self.assertIn('name="decision"', html)
        self.assertIn('name="attachments"', html)

    def test_evidence_editor_always_offers_add_requirement_and_excludes_existing(self):
        second_leaf = Requirement.objects.create(
            framework=self.framework,
            parent=self.root,
            code='E2',
            title='Second Evidence leaf',
        )
        second = Conformity.objects.create(
            organization=self.organization,
            requirement=second_leaf,
        )
        manual = Evidence.objects.create(source_type=Evidence.SourceType.GENERIC, 
            title='Multi requirement evidence',
            result=Evidence.Result.POSITIVE,
            valid_from=self.now - timedelta(hours=1),
        )
        manual.conformities.add(self.conformity)

        self.client.force_login(self.user)
        response = self.client.get(
            reverse('conformity:evidence_form', args=[manual.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Add requirement')
        self.assertContains(
            response,
            reverse('conformity:evidence_requirement_add', args=[manual.pk]),
        )

        response = self.client.get(
            reverse('conformity:evidence_requirement_add', args=[manual.pk])
        )
        queryset = response.context['form'].fields['conformity'].queryset
        self.assertNotIn(self.conformity, queryset)
        self.assertIn(second, queryset)

        response = self.client.post(
            reverse('conformity:evidence_requirement_add', args=[manual.pk]),
            {'conformity': second.pk},
        )

        self.assertRedirects(
            response,
            reverse('conformity:evidence_form', args=[manual.pk]),
            fetch_redirect_response=False,
        )
        self.assertEqual(
            list(manual.conformities.order_by('pk')),
            [self.conformity, second],
        )

    def test_orphan_evidence_editor_offers_requirement_association(self):
        orphan = Evidence.objects.create(source_type=Evidence.SourceType.GENERIC, 
            title='Orphan evidence',
            result=Evidence.Result.POSITIVE,
            valid_from=self.now - timedelta(hours=1),
        )

        self.client.force_login(self.user)
        response = self.client.get(
            reverse('conformity:evidence_form', args=[orphan.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No associated requirement.')
        self.assertContains(response, 'Add requirement')
        self.assertContains(
            response,
            reverse('conformity:evidence_requirement_add', args=[orphan.pk]),
        )

        response = self.client.post(
            reverse('conformity:evidence_requirement_add', args=[orphan.pk]),
            {'conformity': self.conformity.pk},
        )

        self.assertRedirects(
            response,
            reverse('conformity:evidence_form', args=[orphan.pk]),
            fetch_redirect_response=False,
        )
        self.assertEqual(list(orphan.conformities.all()), [self.conformity])

    def test_conformity_evidence_rows_show_source_names_semantic_actions_and_fixed_result_width(self):
        indicator = Indicator.objects.create(
            name='Named indicator',
            responsible=self.user,
            frequency=Indicator.Frequency.YEARLY,
            worst=0,
            critical=20,
            warning=80,
            best=100,
        )
        indicator.conformity.add(self.conformity)
        indicator_point = indicator.get_current_point()

        manual = Evidence.objects.create(source_type=Evidence.SourceType.GENERIC, 
            title='Named manual evidence',
            result=Evidence.Result.POSITIVE,
            valid_from=self.now - timedelta(hours=1),
        )
        manual.conformities.add(self.conformity)

        self.client.force_login(self.user)
        response = self.client.get(
            reverse('conformity:conformity_form', args=[self.conformity.pk])
        )
        html = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('bi bi-speedometer', html)
        self.assertIn('Named indicator', html)
        self.assertIn('Named manual evidence', html)
        self.assertIn('Valid from', html)
        self.assertIn('style="min-width: 10rem;"', html)
        self.assertIn('class="btn btn-primary"', html)
        self.assertIn('class="btn btn-warning"', html)
        self.assertIn('class="btn btn-warning disabled"', html)
        self.assertIn('bi bi-eye', html)
        self.assertIn('bi bi-pencil-square', html)
        self.assertIn(
            reverse('conformity:evidence_detail', args=[indicator_point.pk]),
            html,
        )
        self.assertIn(
            reverse('conformity:evidence_form', args=[manual.pk]),
            html,
        )

    def test_conformity_update_uses_header_actions_for_evidence_and_corrective_action(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse('conformity:conformity_form', args=[self.conformity.pk])
        )
        html = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('btn btn-sm btn-success', html)
        self.assertIn('Create evidence', html)
        self.assertIn('Register corrective action', html)
        self.assertLess(
            html.index('Associated action'),
            html.index('Register corrective action'),
        )
        self.assertLess(
            html.index('Evidence'),
            html.index('Create evidence'),
        )
        self.assertIn('bi bi-person-check text-primary', html)
        self.assertIn('bg-body-tertiary p-3', html)

    def test_conformity_assessment_layout_comment_and_empty_states(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse('conformity:conformity_form', args=[self.conformity.pk])
        )
        html = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('Person responsible for reviewing this requirement.', html)
        self.assertIn('col-12 col-md-6', html)
        self.assertIn('name="responsible"', html)
        self.assertNotIn('/django-backend/auth/user/', html)
        self.assertNotIn('/django-backend/auth/user/', html)
        self.assertIn('placeholder="Comment required"', html)
        self.assertIn('class="form-control w-100"', html)
        self.assertNotIn('for="id_comment"', html)
        self.assertIn('id="conformity-comment"', html)
        self.assertIn('bg-body-tertiary p-3', html)
        self.assertGreaterEqual(html.count('empty-state'), 2)
        self.assertIn('No action associated.', html)
        self.assertIn('No currently valid evidence associated.', html)

    def test_framework_review_header_uses_status_pill_and_stacked_bar(self):
        manual = Evidence.objects.create(source_type=Evidence.SourceType.GENERIC, 
            title='Framework summary evidence',
            result=Evidence.Result.POSITIVE,
            valid_from=self.now - timedelta(hours=1),
        )
        manual.conformities.add(self.conformity)

        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                'conformity:conformity_detail_index',
                args=[self.organization.pk, self.framework.pk],
            )
        )
        html = response.content.decode()

        self.assertIn('badge rounded-pill text-bg-success fs-5 px-3 py-2 ms-auto', html)
        self.assertIn('progress-bar bg-success', html)
        self.assertNotIn('Completeness:', html)

    def test_framework_review_uses_evidence_column_and_categorical_status(self):
        manual = Evidence.objects.create(source_type=Evidence.SourceType.GENERIC, 
            title='Framework review evidence',
            result=Evidence.Result.POSITIVE,
            valid_from=self.now - timedelta(hours=1),
        )
        manual.conformities.add(self.conformity)

        self.client.force_login(self.user)
        response = self.client.get(
            reverse(
                'conformity:conformity_detail_index',
                args=[self.organization.pk, self.framework.pk],
            )
        )

        self.assertContains(response, '>Evidence<', html=False)
        self.assertContains(response, 'Conforme')
        self.assertContains(response, '1 evidence')
        self.assertNotContains(response, '>Control<', html=False)

    def test_removing_last_evidence_clears_parent_aggregate(self):
        positive = self.evidence(Evidence.Result.POSITIVE)
        self.parent.refresh_from_db()
        self.assertEqual(self.parent.status, 100)

        positive.conformities.remove(self.conformity)
        self.conformity.refresh_from_db()
        self.parent.refresh_from_db()
        self.assertIsNone(self.conformity.status)
        self.assertIsNone(self.parent.status)
        self.assertEqual(
            self.parent.evidence_state,
            Conformity.EvidenceState.NOT_EVALUATED,
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
            source_type=Evidence.SourceType.GENERIC,
            result=Evidence.Result.NEGATIVE,
            valid_from=self.now - timedelta(minutes=1),
        )
        later_negative.conformities.add(self.conformity)
        human.refresh_from_db()
        self.assertIsNotNone(human.valid_to)

    def test_later_control_result_invalidates_human_arbitration(self):
        control = Control.objects.create(
            title='Human-arbitrated control',
        )
        control.conformity.add(self.conformity)
        point = ControlPoint.objects.create(
            control=control,
            period_start_date=date.today() - timedelta(days=1),
            period_end_date=date.today() + timedelta(days=1),
            status=Evidence.Status.EVALUATED, result=Evidence.Result.POSITIVE,
        )
        human = HumanEvidence.objects.create(
            decision=HumanEvidence.Decision.COMPLIANT,
            valid_from=self.now,
            evaluator=self.user,
        )
        human.conformities.add(self.conformity)

        point.status = Evidence.Status.EVALUATED
        point.result = Evidence.Result.NEGATIVE
        point.save(update_fields=['status'])
        human.refresh_from_db()
        point.refresh_from_db()
        self.assertIsNotNone(human.valid_to)
        self.assertEqual(point.result, Evidence.Result.NEGATIVE)

    def test_non_result_control_update_keeps_human_arbitration(self):
        control = Control.objects.create(
            title='Documented control',
        )
        control.conformity.add(self.conformity)
        point = ControlPoint.objects.create(
            control=control,
            period_start_date=date.today() - timedelta(days=1),
            period_end_date=date.today() + timedelta(days=1),
            status=Evidence.Status.EVALUATED, result=Evidence.Result.NEGATIVE,
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
            title='Access review',
        )
        control.conformity.add(self.conformity)
        point = ControlPoint.objects.create(
            control=control,
            period_start_date=date.today() - timedelta(days=1),
            period_end_date=date.today() + timedelta(days=1),
            status=Evidence.Status.EVALUATED, result=Evidence.Result.NEGATIVE,
            comment='Access not removed.',
        )
        point.refresh_from_db()
        self.assertTrue(issubclass(ControlPoint, Evidence))
        self.assertEqual(point.result, Evidence.Result.NEGATIVE)
        self.assertEqual(point.comment, 'Access not removed.')
        self.assertEqual(list(point.conformities.all()), [self.conformity])

    def test_indicator_point_is_evidence_and_preserves_threshold_logic(self):
        indicator = Indicator.objects.create(
            name='Coverage', responsible=self.user,
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
        self.assertEqual(point.status, Evidence.Status.EVALUATED)
        self.assertEqual(point.result, Evidence.Result.NEGATIVE)
        self.assertTrue(issubclass(IndicatorPoint, Evidence))
        self.assertEqual(point.result, Evidence.Result.NEGATIVE)

    def test_human_evidence_view_requires_login_and_records_author(self):
        self.evidence(Evidence.Result.POSITIVE)
        self.evidence(Evidence.Result.NEGATIVE)
        self.conformity.refresh_from_db()
        self.assertEqual(
            self.conformity.evidence_state,
            Conformity.EvidenceState.INCONCLUSIVE,
        )

        url = reverse('conformity:human_evidence_create', args=[self.conformity.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.user)
        create_response = self.client.get(url)
        valid_from = create_response.context['form'].initial['valid_from']
        valid_to = create_response.context['form'].initial['valid_to']
        self.assertEqual(valid_to - valid_from, timedelta(days=365))

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

        # The M2M association is the creation trigger: the HumanEvidence must
        # arbitrate the mixed situation immediately.
        self.conformity.refresh_from_db()
        self.assertEqual(
            self.conformity.evidence_state,
            Conformity.EvidenceState.COMPLIANT,
        )
        self.assertEqual(self.conformity.status, 100)
        self.assertEqual(
            self.conformity.status_justification,
            Conformity.StatusJustification.EVIDENCE,
        )

    def test_standalone_human_evidence_evaluates_conformity(self):
        human = HumanEvidence.objects.create(
            decision=HumanEvidence.Decision.COMPLIANT,
            valid_from=self.now - timedelta(minutes=1),
            evaluator=self.user,
        )
        human.conformities.add(self.conformity)

        self.conformity.refresh_from_db()
        self.assertEqual(
            self.conformity.evidence_state,
            Conformity.EvidenceState.COMPLIANT,
        )
        self.assertEqual(self.conformity.status, 100)

    def test_editing_human_evidence_re_evaluates_conformity(self):
        human = HumanEvidence.objects.create(
            decision=HumanEvidence.Decision.COMPLIANT,
            valid_from=self.now - timedelta(minutes=1),
            evaluator=self.user,
            comment='Initial decision',
        )
        human.conformities.add(self.conformity)
        self.conformity.refresh_from_db()
        self.assertEqual(self.conformity.status, 100)

        self.client.force_login(self.user)
        response = self.client.post(
            reverse('conformity:evidence_form', args=[human.pk]),
            {
                'decision': HumanEvidence.Decision.NON_COMPLIANT,
                'valid_from': human.valid_from.strftime('%Y-%m-%d %H:%M:%S'),
                'valid_to': '',
                'comment': 'Decision changed after review',
            },
        )

        self.assertRedirects(
            response,
            reverse('conformity:conformity_form', args=[self.conformity.pk]),
        )
        human.refresh_from_db()
        self.conformity.refresh_from_db()

        self.assertEqual(human.result, Evidence.Result.NEGATIVE)
        self.assertEqual(
            self.conformity.evidence_state,
            Conformity.EvidenceState.NON_COMPLIANT,
        )
        self.assertEqual(self.conformity.status, 0)
        self.assertEqual(
            self.conformity.status_justification,
            Conformity.StatusJustification.EVIDENCE,
        )

    def test_conformity_update_shows_only_current_evidence(self):
        current = Evidence.objects.create(source_type=Evidence.SourceType.GENERIC, 
            title='Current evidence',
            result=Evidence.Result.POSITIVE,
            valid_from=self.now - timedelta(hours=1),
            valid_to=self.now + timedelta(hours=1),
        )
        current.conformities.add(self.conformity)

        expired = Evidence.objects.create(source_type=Evidence.SourceType.GENERIC, 
            title='Expired evidence',
            result=Evidence.Result.NEGATIVE,
            valid_from=self.now - timedelta(days=2),
            valid_to=self.now - timedelta(days=1),
        )
        expired.conformities.add(self.conformity)

        future = Evidence.objects.create(source_type=Evidence.SourceType.GENERIC, 
            title='Future evidence',
            result=Evidence.Result.POSITIVE,
            valid_from=self.now + timedelta(days=1),
        )
        future.conformities.add(self.conformity)

        self.client.force_login(self.user)
        response = self.client.get(
            reverse('conformity:conformity_form', args=[self.conformity.pk])
        )

        self.assertContains(response, reverse('conformity:evidence_detail', args=[current.pk]))
        self.assertContains(response, reverse('conformity:evidence_form', args=[current.pk]))
        self.assertNotContains(response, reverse('conformity:evidence_detail', args=[expired.pk]))
        self.assertNotContains(response, reverse('conformity:evidence_detail', args=[future.pk]))

    def test_evidence_detail_is_available_for_control_but_edit_is_not(self):
        control = Control.objects.create(
            title='Immutable control evidence',
        )
        control.conformity.add(self.conformity)
        point = ControlPoint.objects.create(
            control=control,
            period_start_date=date.today() - timedelta(days=1),
            period_end_date=date.today() + timedelta(days=1),
            status=Evidence.Status.EVALUATED, result=Evidence.Result.POSITIVE,
        )

        self.client.force_login(self.user)
        detail_url = reverse('conformity:evidence_detail', args=[point.pk])
        edit_url = reverse('conformity:evidence_form', args=[point.pk])

        self.assertEqual(self.client.get(detail_url).status_code, 200)
        self.assertEqual(self.client.get(edit_url).status_code, 404)

    def test_generic_evidence_can_be_edited(self):
        manual = Evidence.objects.create(source_type=Evidence.SourceType.GENERIC, 
            title='Editable evidence',
            result=Evidence.Result.POSITIVE,
            valid_from=self.now - timedelta(hours=1),
        )
        manual.conformities.add(self.conformity)

        self.client.force_login(self.user)
        response = self.client.post(
            reverse('conformity:evidence_form', args=[manual.pk]),
            {
                'title': 'Edited evidence',
                'result': Evidence.Result.NEGATIVE,
                'valid_from': manual.valid_from.strftime('%Y-%m-%d %H:%M:%S'),
                'valid_to': '',
                'comment': 'Updated generically',
            },
        )

        self.assertRedirects(
            response,
            reverse('conformity:evidence_detail', args=[manual.pk]),
        )
        manual.refresh_from_db()
        self.assertEqual(manual.title, 'Edited evidence')
        self.assertEqual(manual.result, Evidence.Result.NEGATIVE)
        self.assertEqual(manual.comment, 'Updated generically')

    def test_additional_evidence_types_share_common_engine(self):
        manual = Evidence.objects.create(source_type=Evidence.SourceType.GENERIC, 
            title='Supplier attestation', result=Evidence.Result.POSITIVE,
            valid_from=self.now,
        )
        manual.conformities.add(self.conformity)
        self.assertEqual(manual.source_type, Evidence.SourceType.GENERIC)
        self.assertTrue(issubclass(DocumentEvidence, Evidence))
