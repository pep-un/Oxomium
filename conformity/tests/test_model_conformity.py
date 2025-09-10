from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import NoReverseMatch
from django.utils import timezone

from conformity.models import (
    Framework, Organization, Requirement, Conformity,
    Action, Control, ControlPoint
)

def _uniq(s: str) -> str:
    import random, string
    return f"{s}-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

class ConformityModelFullTests(TestCase):
    """
    Unit tests for Conformity helpers and guards aligned with current models.py:
    - Action has ManyToMany 'associated_conformity' (related_name='actions')
    - Control has ManyToMany 'conformity'
    - Action.Status has ENDED (not COMPLETED)
    - Control uses 'frequency' (IntegerChoices), default is fine
    """

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(username=_uniq("alice"))

        # Minimal graph: Framework -> Requirement tree (root -> child1, child2)
        cls.fw = Framework.objects.create(
            name=_uniq("Framework Conformity"),
        )

        # Root and leaves
        cls.r_root = Requirement.objects.create(framework=cls.fw, code=_uniq("R-ROOT"), title="Root", level=0, order=0)
        cls.r_child1 = Requirement.objects.create(framework=cls.fw, code=_uniq("R-C1"), title="Child 1", level=1, order=1, parent=cls.r_root)
        cls.r_child2 = Requirement.objects.create(framework=cls.fw, code=_uniq("R-C2"), title="Child 2", level=1, order=2, parent=cls.r_root)

        cls.org = Organization.objects.create(name=_uniq("Org"))

        # Conformities for the tree
        cls.c_root = Conformity.objects.create(organization=cls.org, requirement=cls.r_root, applicable=True)
        cls.c1 = Conformity.objects.create(organization=cls.org, requirement=cls.r_child1, applicable=True)
        cls.c2 = Conformity.objects.create(organization=cls.org, requirement=cls.r_child2, applicable=True)

        # Some Actions / Controls on child1 for get_related tests
        # - Completed/ended action (should not count as "negative" progress)
        cls.a_ended = Action.objects.create(
            title="Done",
            status=Action.Status.ENDED,
            active=False,
        )
        cls.a_ended.associated_conformity.add(cls.c1)

        # - In-progress action (negative_only should include it)
        cls.a_in_progress = Action.objects.create(
            title="Doing",
            status=Action.Status.IMPLEMENTING,
            active=True,
        )
        cls.a_in_progress.associated_conformity.add(cls.c1)

        # Control linked to c1 (M2M)
        cls.ctrl = Control.objects.create(title="C-Periodic")
        cls.ctrl.conformity.add(cls.c1)

        # ControlPoints: one negative in current period, one compliant in the past
        today = date.today()
        cls.cp_negative = ControlPoint.objects.create(
            control=cls.ctrl,
            period_start_date=today - timedelta(days=10),
            period_end_date=today + timedelta(days=10),
            status=ControlPoint.Status.NONCOMPLIANT,
        )
        cls.cp_past_ok = ControlPoint.objects.create(
            control=cls.ctrl,
            period_start_date=today - timedelta(days=90),
            period_end_date=today - timedelta(days=60),
            status=ControlPoint.Status.COMPLIANT,
        )

    # ---------- Basic helpers ----------

    def test_str_natural_key_absolute_url(self):
        s = str(self.c1)
        self.assertIn(str(self.org), s)
        self.assertIn(str(self.r_child1), s)

        nk = self.c1.natural_key()
        self.assertEqual(nk, (self.org, self.r_child1))

        # get_absolute_url depends on project urls; skip cleanly if route missing
        try:
            url = self.c1.get_absolute_url()
            self.assertIsInstance(url, str)
            self.assertIn(str(self.org.id), url)
            self.assertIn(str(self.r_child1.framework.id), url)
        except NoReverseMatch:
            self.skipTest("Route 'conformity:conformity_detail_index' not configured; skipping.")

    def test_tree_navigation_helpers(self):
        self.assertIsNone(self.c_root.get_parent())
        self.assertEqual(self.c1.get_parent(), self.c_root)

        children = list(self.c_root.get_children())
        self.assertCountEqual(children, [self.c1, self.c2])

        desc = list(self.c_root.get_descendants())
        self.assertCountEqual(desc, [self.c1, self.c2])

    # ---------- Action / Control getters ----------

    def test_get_action_and_get_control(self):
        acts = list(self.c1.get_action())
        ctrls = list(self.c1.get_control())
        self.assertIn(self.a_in_progress, acts)
        self.assertNotIn(self.a_ended, acts)  # get_action filters active=True
        self.assertIn(self.ctrl, ctrls)

    # ---------- get_related (default & negative_only) + sorting ----------

    def test_get_related_default_modes_and_sort(self):
        items = self.c1.get_related(negative_only=False, include_actions=True, include_controls=True, only_active=False)
        kinds = [k for (k, _) in items]
        objs = [o for (_, o) in items]
        self.assertIn("action", kinds)
        self.assertIn("control", kinds)
        self.assertIn(self.a_in_progress, objs)
        self.assertIn(self.a_ended, objs)   # because only_active=False
        self.assertIn(self.ctrl, objs)

        items_active = self.c1.get_related(only_active=True)
        objs_active = [o for (_, o) in items_active]
        self.assertIn(self.a_in_progress, objs_active)
        self.assertNotIn(self.a_ended, objs_active)

        items_alpha = self.c1.get_related(sort="alpha")
        labels = []
        for _, obj in items_alpha:
            labels.append(getattr(obj, "title", None) or getattr(obj, "name", None) or getattr(obj, "short_description", None) or str(obj))
        self.assertEqual(labels, sorted(labels))

        items_recent = self.c1.get_related(sort="recent_first")
        self.assertTrue(len(items_recent) >= 1)

    def test_get_related_negative_only(self):
        items = self.c1.get_related(negative_only=True, include_actions=True, include_controls=True)
        kinds = [k for (k, _) in items]
        objs = [o for (_, o) in items]

        self.assertIn("action", kinds)
        self.assertIn("controlpoint", kinds)
        self.assertIn(self.a_in_progress, objs)
        self.assertIn(self.cp_negative, objs)
        self.assertNotIn(self.a_ended, objs)
        self.assertNotIn(self.cp_past_ok, objs)

    # ---------- update_responsible ----------

    def test_update_responsible_propagates_to_descendants(self):
        self.c_root.responsible = self.user
        self.c_root.update_responsible()
        self.c1.refresh_from_db()
        self.c2.refresh_from_db()
        self.assertEqual(self.c1.responsible, self.user)
        self.assertEqual(self.c2.responsible, self.user)

    # ---------- update_applicable ----------

    def test_update_applicable_descendants_and_ancestors(self):
        self.c_root.applicable = False
        self.c_root.update_applicable()
        self.c1.refresh_from_db()
        self.c2.refresh_from_db()
        self.assertFalse(self.c1.applicable)
        self.assertFalse(self.c2.applicable)

        self.c1.applicable = True
        self.c1.update_applicable()
        self.c_root.refresh_from_db()
        self.assertTrue(self.c_root.applicable)

    # ---------- update_status aggregation ----------

    def test_update_status_aggregates_children_and_recurses(self):
        self.c1.status = 20
        self.c1.status_justification = Conformity.StatusJustification.EXPERT
        self.c1.status_last_update = timezone.now()
        self.c1.save()

        self.c2.status = 80
        self.c2.status_justification = Conformity.StatusJustification.EXPERT
        self.c2.status_last_update = timezone.now()
        self.c2.save()

        self.c_root.update_status()
        self.c_root.refresh_from_db()
        self.assertEqual(self.c_root.status, 50)
        self.assertEqual(self.c_root.status_justification, Conformity.StatusJustification.CONFORMITY)
        self.assertIsNotNone(self.c_root.status_last_update)

        self.c2.applicable = False
        self.c2.save(update_fields=["applicable"])
        self.c_root.update_status()
        self.c_root.refresh_from_db()
        self.assertEqual(self.c_root.status, 20)

    # ---------- set_status_from guards & success paths ----------

    def test_set_status_from_no_change_returns_false(self):
        ok = self.c1.set_status_from(10, Conformity.StatusJustification.EXPERT)
        self.assertTrue(ok)

        again = self.c1.set_status_from(10, Conformity.StatusJustification.EXPERT)
        self.assertFalse(again)

    def test_set_status_from_expert_guard_on_non_leaf(self):
        changed = self.c_root.set_status_from(42, Conformity.StatusJustification.EXPERT)
        self.assertFalse(changed)
        self.c_root.refresh_from_db()
        self.assertIsNone(self.c_root.status)

    def test_set_status_from_action_and_control_guards(self):
        # Trying to force 100 with negatives present -> must be rejected
        changed = self.c1.set_status_from(100, Conformity.StatusJustification.CONTROL)
        self.assertFalse(changed)
        self.c1.refresh_from_db()
        self.assertNotEqual(self.c1.status, 100)

        # Remove negatives: mark action ended and CP compliant
        self.a_in_progress.status = Action.Status.ENDED
        self.a_in_progress.active = False
        self.a_in_progress.save()
        self.cp_negative.status = ControlPoint.Status.COMPLIANT
        self.cp_negative.save()

        # Now, setting 0 without negatives should not rejected
        changed_zero = self.c1.set_status_from(0, Conformity.StatusJustification.ACTION)
        self.assertTrue(changed_zero)

        ok_mid = self.c1.set_status_from(60, Conformity.StatusJustification.ACTION)
        self.assertTrue(ok_mid)
        self.c1.refresh_from_db()
        self.assertEqual(self.c1.status, 60)
        self.assertEqual(self.c1.status_justification, Conformity.StatusJustification.ACTION)
        self.assertTrue(self.c1.applicable)
        self.assertIsNotNone(self.c1.status_last_update)

    def test_get_related_toggles_include_flags(self):
        only_ctrls = self.c1.get_related(include_actions=False, include_controls=True)
        kinds = set(k for (k, _) in only_ctrls)
        self.assertEqual(kinds, {"control"})

        only_actions = self.c1.get_related(include_actions=True, include_controls=False, only_active=False)
        kinds2 = set(k for (k, _) in only_actions)
        self.assertEqual(kinds2, {"action"})
