"""Executable business contract for the Evidence evaluation engine.

These tests intentionally describe the target business rules independently of
its current implementation. A failing case means the engine diverges from the
agreed contract; the expected value should not be weakened to match legacy
behaviour.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase
from django.utils import timezone

from conformity.models import (
    Conformity, Evidence, Framework, HumanEvidence, Organization, Requirement,
)
from conformity.services.conformities import recompute_parent_chain
from conformity.services.evidence import evaluate_conformity, refresh_time_bound_conformities


class EvidenceContractTests(TestCase):
    """Business truth table agreed for leaf Evidence and parent aggregation."""

    def setUp(self):
        self.user = get_user_model().objects.create_user('evidence-contract-user')
        self.framework = Framework.objects.create(name='Evidence contract')
        self.root_requirement = Requirement.objects.create(
            framework=self.framework, code='ROOT', title='Root'
        )
        self.leaf_requirement = Requirement.objects.create(
            framework=self.framework,
            parent=self.root_requirement,
            code='LEAF',
            title='Leaf',
        )
        self.organization = Organization.objects.create(name='Contract organization')
        self.parent = Conformity.objects.create(
            organization=self.organization, requirement=self.root_requirement
        )
        self.leaf = Conformity.objects.create(
            organization=self.organization, requirement=self.leaf_requirement
        )
        self.now = timezone.now()

    def add_evidence(
        self, result, *, conformity=None, source_type=None, start=None, end=None
    ):
        conformity = conformity or self.leaf
        evidence = Evidence.objects.create(
            source_type=source_type or Evidence.SourceType.DOCUMENT,
            result=result,
            valid_from=start or self.now - timedelta(hours=1),
            valid_to=end,
        )
        evidence.conformities.add(conformity)
        return evidence

    def add_human(self, result, *, conformity=None, start=None):
        conformity = conformity or self.leaf
        human = HumanEvidence.objects.create(
            decision=result,
            valid_from=start or self.now - timedelta(minutes=1),
            evaluator=self.user,
        )
        human.conformities.add(conformity)
        return human

    def assert_leaf_state(self, expected):
        self.leaf.refresh_from_db()
        self.assertEqual(self.leaf.evidence_state, expected)

    def test_automatic_evidence_truth_table(self):
        """PARTIAL wins; NEUTRAL never votes positive or negative."""
        cases = (
            ('none', (), Conformity.EvidenceState.NOT_EVALUATED),
            ('positive', (Evidence.Result.POSITIVE,), Conformity.EvidenceState.COMPLIANT),
            ('negative', (Evidence.Result.NEGATIVE,), Conformity.EvidenceState.NON_COMPLIANT),
            ('neutral-only', (Evidence.Result.NEUTRAL,), Conformity.EvidenceState.INCONCLUSIVE),
            (
                'positive-neutral',
                (Evidence.Result.POSITIVE, Evidence.Result.NEUTRAL),
                Conformity.EvidenceState.COMPLIANT,
            ),
            (
                'negative-neutral',
                (Evidence.Result.NEGATIVE, Evidence.Result.NEUTRAL),
                Conformity.EvidenceState.NON_COMPLIANT,
            ),
            (
                'positive-negative',
                (Evidence.Result.POSITIVE, Evidence.Result.NEGATIVE),
                Conformity.EvidenceState.INCONCLUSIVE,
            ),
            ('partial-only', (Evidence.Result.PARTIAL,), Conformity.EvidenceState.PARTIAL),
            (
                'positive-partial',
                (Evidence.Result.POSITIVE, Evidence.Result.PARTIAL),
                Conformity.EvidenceState.PARTIAL,
            ),
            (
                'negative-partial',
                (Evidence.Result.NEGATIVE, Evidence.Result.PARTIAL),
                Conformity.EvidenceState.PARTIAL,
            ),
            (
                'positive-negative-partial',
                (
                    Evidence.Result.POSITIVE,
                    Evidence.Result.NEGATIVE,
                    Evidence.Result.PARTIAL,
                ),
                Conformity.EvidenceState.PARTIAL,
            ),
            (
                'partial-neutral',
                (Evidence.Result.PARTIAL, Evidence.Result.NEUTRAL),
                Conformity.EvidenceState.PARTIAL,
            ),
        )
        for label, results, expected in cases:
            with self.subTest(label=label):
                self.leaf.evidence.all().delete()
                for result in results:
                    self.add_evidence(result)
                state = evaluate_conformity(self.leaf, at=self.now)
                self.assertEqual(state, expected)

    def test_expired_and_future_evidence_do_not_exist_for_current_calculation(self):
        self.add_evidence(
            Evidence.Result.NEGATIVE,
            start=self.now - timedelta(days=2),
            end=self.now - timedelta(days=1),
        )
        self.add_evidence(
            Evidence.Result.NEGATIVE,
            start=self.now + timedelta(days=1),
        )
        self.add_evidence(Evidence.Result.POSITIVE)

        self.assertEqual(
            evaluate_conformity(self.leaf, at=self.now),
            Conformity.EvidenceState.COMPLIANT,
        )

    def test_human_arbitration_combination_table(self):
        """Human arbitration complements automatic evidence without erasing it."""
        P = Evidence.Result.POSITIVE
        N = Evidence.Result.NEGATIVE
        R = Evidence.Result.PARTIAL
        U = Evidence.Result.NEUTRAL
        C = Conformity.EvidenceState.COMPLIANT
        NC = Conformity.EvidenceState.NON_COMPLIANT
        PA = Conformity.EvidenceState.PARTIAL
        IC = Conformity.EvidenceState.INCONCLUSIVE

        cases = (
            ('human-positive-alone', (), P, C),
            ('human-negative-alone', (), N, NC),
            ('human-partial-alone', (), R, PA),
            ('human-neutral-algorithmic-fallback', (), U, IC),
            ('auto-inconclusive-human-positive', (P, N), P, C),
            ('auto-inconclusive-human-negative', (P, N), N, NC),
            ('auto-inconclusive-human-partial', (P, N), R, PA),
            ('auto-compliant-human-positive', (P,), P, C),
            ('auto-compliant-human-negative', (P,), N, PA),
            ('auto-compliant-human-partial', (P,), R, PA),
            ('auto-non-compliant-human-negative', (N,), N, NC),
            ('auto-non-compliant-human-positive', (N,), P, PA),
            ('auto-non-compliant-human-partial', (N,), R, PA),
            ('auto-partial-human-positive', (R,), P, C),
            ('auto-partial-human-negative', (R,), N, NC),
            ('auto-partial-human-partial', (R,), R, PA),
            ('neutral-auto-human-positive', (U,), P, C),
            ('neutral-auto-human-negative', (U,), N, NC),
            ('neutral-auto-human-partial', (U,), R, PA),
        )

        for label, automatic_results, human_result, expected in cases:
            with self.subTest(label=label):
                self.leaf.evidence.all().delete()
                for result in automatic_results:
                    self.add_evidence(result)
                self.add_human(human_result)
                self.assertEqual(
                    evaluate_conformity(self.leaf, at=self.now),
                    expected,
                )

    def test_new_human_arbitration_invalidates_previous_one(self):
        first = self.add_human(
            Evidence.Result.POSITIVE, start=self.now - timedelta(hours=2)
        )
        second = self.add_human(
            Evidence.Result.NEGATIVE, start=self.now - timedelta(hours=1)
        )

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertIsNotNone(first.valid_to)
        self.assertIsNone(second.valid_to)
        self.assertEqual(
            evaluate_conformity(self.leaf, at=self.now),
            Conformity.EvidenceState.NON_COMPLIANT,
        )

    def test_human_arbitration_compatibility_table_after_automatic_change(self):
        """Arbitration survives only while compatible with current auto state."""
        P = Evidence.Result.POSITIVE
        N = Evidence.Result.NEGATIVE
        R = Evidence.Result.PARTIAL

        cases = (
            ('not-evaluated-positive', (), P, True),
            ('not-evaluated-negative', (), N, True),
            ('not-evaluated-partial', (), R, True),
            ('inconclusive-positive', (P, N), P, True),
            ('inconclusive-negative', (P, N), N, True),
            ('inconclusive-partial', (P, N), R, True),
            ('compliant-positive', (P,), P, True),
            ('compliant-partial', (P,), R, True),
            ('compliant-negative', (P,), N, False),
            ('non-compliant-negative', (N,), N, True),
            ('non-compliant-partial', (N,), R, True),
            ('non-compliant-positive', (N,), P, False),
            ('partial-partial', (R,), R, True),
            ('partial-positive', (R,), P, False),
            ('partial-negative', (R,), N, False),
        )

        for label, automatic_results, human_result, remains_valid in cases:
            with self.subTest(label=label):
                self.leaf.evidence.all().delete()
                human = self.add_human(human_result)
                for result in automatic_results:
                    self.add_evidence(result)
                evaluate_conformity(
                    self.leaf,
                    at=self.now,
                    trigger=self.leaf.evidence.exclude(
                        source_type=Evidence.SourceType.HUMAN
                    ).order_by('-pk').first(),
                )
                human.refresh_from_db()
                self.assertEqual(human.is_valid_at(self.now), remains_valid)

    def test_redundant_human_arbitration_remains_valid(self):
        self.add_evidence(Evidence.Result.POSITIVE)
        self.add_evidence(Evidence.Result.NEGATIVE)
        human = self.add_human(Evidence.Result.POSITIVE)

        negative = self.leaf.evidence.filter(
            source_type=Evidence.SourceType.DOCUMENT,
            result=Evidence.Result.NEGATIVE,
        ).get()
        negative.valid_to = self.now
        negative.save(update_fields=['valid_to'])

        human.refresh_from_db()
        self.assertTrue(human.is_valid_at(self.now))
        self.assertEqual(
            evaluate_conformity(self.leaf, at=self.now),
            Conformity.EvidenceState.COMPLIANT,
        )

    def test_manual_human_invalidation_recalculates_leaf(self):
        self.add_evidence(Evidence.Result.POSITIVE)
        self.add_evidence(Evidence.Result.NEGATIVE)
        human = self.add_human(Evidence.Result.POSITIVE)
        self.assert_leaf_state(Conformity.EvidenceState.COMPLIANT)

        human.valid_to = self.now
        human.save(update_fields=['valid_to'])

        self.assert_leaf_state(Conformity.EvidenceState.INCONCLUSIVE)

    def test_parent_aggregation_truth_table(self):
        """Parents aggregate direct child states; they never evaluate Evidence."""
        second_requirement = Requirement.objects.create(
            framework=self.framework,
            parent=self.root_requirement,
            code='LEAF2',
            title='Second leaf',
        )
        second = Conformity.objects.create(
            organization=self.organization, requirement=second_requirement
        )
        S = Conformity.EvidenceState
        cases = (
            ('all-compliant', S.COMPLIANT, S.COMPLIANT, S.COMPLIANT),
            ('all-non-compliant', S.NON_COMPLIANT, S.NON_COMPLIANT, S.NON_COMPLIANT),
            ('compliant-non-compliant', S.COMPLIANT, S.NON_COMPLIANT, S.PARTIAL),
            ('compliant-partial', S.COMPLIANT, S.PARTIAL, S.PARTIAL),
            ('non-compliant-partial', S.NON_COMPLIANT, S.PARTIAL, S.PARTIAL),
            ('all-partial', S.PARTIAL, S.PARTIAL, S.PARTIAL),
            (
                'compliant-not-evaluated',
                S.COMPLIANT,
                S.NOT_EVALUATED,
                S.NOT_EVALUATED,
            ),
            (
                'non-compliant-not-evaluated',
                S.NON_COMPLIANT,
                S.NOT_EVALUATED,
                S.NOT_EVALUATED,
            ),
            ('partial-not-evaluated', S.PARTIAL, S.NOT_EVALUATED, S.NOT_EVALUATED),
            (
                'all-not-evaluated',
                S.NOT_EVALUATED,
                S.NOT_EVALUATED,
                S.NOT_EVALUATED,
            ),
            (
                'compliant-inconclusive',
                S.COMPLIANT,
                S.INCONCLUSIVE,
                S.NOT_EVALUATED,
            ),
            (
                'non-compliant-inconclusive',
                S.NON_COMPLIANT,
                S.INCONCLUSIVE,
                S.NOT_EVALUATED,
            ),
            ('partial-inconclusive', S.PARTIAL, S.INCONCLUSIVE, S.NOT_EVALUATED),
            (
                'all-inconclusive',
                S.INCONCLUSIVE,
                S.INCONCLUSIVE,
                S.NOT_EVALUATED,
            ),
        )
        status_for = {
            S.COMPLIANT: 100,
            S.PARTIAL: 50,
            S.NON_COMPLIANT: 0,
            S.NOT_EVALUATED: None,
            S.INCONCLUSIVE: None,
        }
        for label, first_state, second_state, expected in cases:
            with self.subTest(label=label):
                for child, state in (
                    (self.leaf, first_state),
                    (second, second_state),
                ):
                    child.evidence_state = state
                    child.status = status_for[state]
                    child.status_justification = Conformity.StatusJustification.EVIDENCE
                    child.save(
                        update_fields=[
                            'evidence_state',
                            'status',
                            'status_justification',
                        ]
                    )
                recompute_parent_chain(self.parent)
                self.parent.refresh_from_db()
                self.assertEqual(self.parent.evidence_state, expected)

    def test_shared_evidence_recalculates_each_leaf_and_its_parents(self):
        other_root = Requirement.objects.create(
            framework=self.framework, code='OTHER', title='Other root'
        )
        other_leaf_requirement = Requirement.objects.create(
            framework=self.framework,
            parent=other_root,
            code='OTHER1',
            title='Other leaf',
        )
        other_parent = Conformity.objects.create(
            organization=self.organization, requirement=other_root
        )
        other_leaf = Conformity.objects.create(
            organization=self.organization, requirement=other_leaf_requirement
        )
        shared = Evidence.objects.create(
            source_type=Evidence.SourceType.DOCUMENT,
            result=Evidence.Result.POSITIVE,
            valid_from=self.now - timedelta(hours=1),
        )
        shared.conformities.add(self.leaf, other_leaf)

        shared.result = Evidence.Result.NEGATIVE
        shared.save(update_fields=['result'])

        for conformity in (self.leaf, other_leaf, self.parent, other_parent):
            conformity.refresh_from_db()
            self.assertEqual(
                conformity.evidence_state,
                Conformity.EvidenceState.NON_COMPLIANT,
            )

    def test_evidence_can_only_be_attached_to_leaf_conformities(self):
        evidence = Evidence.objects.create(
            source_type=Evidence.SourceType.DOCUMENT,
            result=Evidence.Result.POSITIVE,
            valid_from=self.now - timedelta(hours=1),
        )
        with self.assertRaises(ValidationError), transaction.atomic():
            evidence.conformities.add(self.parent)
        with self.assertRaises(ValidationError), transaction.atomic():
            self.parent.evidence.add(evidence)

    def test_leaf_becoming_parent_dissociates_evidence_without_invalidating_it(self):
        shared = self.add_evidence(Evidence.Result.POSITIVE)
        other_root = Requirement.objects.create(
            framework=self.framework, code='SHARED', title='Shared root'
        )
        other_leaf_requirement = Requirement.objects.create(
            framework=self.framework,
            parent=other_root,
            code='SHARED1',
            title='Shared leaf',
        )
        other_leaf = Conformity.objects.create(
            organization=self.organization, requirement=other_leaf_requirement
        )
        shared.conformities.add(other_leaf)

        Requirement.objects.create(
            framework=self.framework,
            parent=self.leaf_requirement,
            code='GRANDCHILD',
            title='New child',
        )

        shared.refresh_from_db()
        self.assertNotIn(self.leaf, shared.conformities.all())
        self.assertIn(other_leaf, shared.conformities.all())
        self.assertTrue(shared.is_valid_at(self.now))

    def test_parent_becoming_leaf_does_not_restore_old_evidence(self):
        shared = self.add_evidence(Evidence.Result.POSITIVE)
        child = Requirement.objects.create(
            framework=self.framework,
            parent=self.leaf_requirement,
            code='TEMP',
            title='Temporary child',
        )
        self.assertNotIn(self.leaf, shared.conformities.all())

        child.delete()
        self.leaf.refresh_from_db()
        self.assertFalse(self.leaf.evidence.exists())
        self.assertEqual(
            evaluate_conformity(self.leaf, at=self.now),
            Conformity.EvidenceState.NOT_EVALUATED,
        )

    def test_time_refresh_persists_leaf_and_parent_state(self):
        evidence = self.add_evidence(
            Evidence.Result.POSITIVE,
            start=self.now - timedelta(hours=1),
            end=self.now + timedelta(minutes=1),
        )
        self.assert_leaf_state(Conformity.EvidenceState.COMPLIANT)

        later = evidence.valid_to + timedelta(microseconds=1)
        refresh_time_bound_conformities(at=later)

        self.leaf.refresh_from_db()
        self.parent.refresh_from_db()
        self.assertEqual(
            self.leaf.evidence_state,
            Conformity.EvidenceState.NOT_EVALUATED,
        )
        self.assertEqual(
            self.parent.evidence_state,
            Conformity.EvidenceState.NOT_EVALUATED,
        )
