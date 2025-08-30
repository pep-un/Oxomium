from datetime import date, timedelta
from django.test import TestCase
from django.utils import timezone

from conformity.models import (
    Framework, Organization, Requirement, Conformity, Control, ControlPoint, Action, Attachment, Audit, Finding)


class SignalTests(TestCase):
    """Signal-driven lifecycle tests (m2m, pre_save/post_save hooks)."""

    def test_requirement_presave_sets_hierarchical_name(self):
        """pre_save should build hierarchical 'name' from parent chain and code."""
        fw = Framework.objects.create(name="FW-X")
        root = Requirement.objects.create(framework=fw, code="AX")
        child = Requirement.objects.create(framework=fw, code="01", parent=root)
        grandchild = Requirement.objects.create(framework=fw, code="b", parent=child)

        root.refresh_from_db()
        child.refresh_from_db()
        grandchild.refresh_from_db()

        self.assertEqual(root.name, "AX")
        self.assertEqual(child.name, "AX-01")
        self.assertEqual(grandchild.name, "AX-01-b")

    def test_org_applicable_frameworks_m2m_creates_and_removes_conformities(self):
        """
        M2M add/remove on Organization.applicable_frameworks should
        create/remove Conformity rows via signals.
        """
        org = Organization.objects.create(name="Org-M2M")
        fw = Framework.objects.create(name="FW-M2M")
        r0 = Requirement.objects.create(framework=fw, code="R0-M2M")
        Requirement.objects.create(framework=fw, code="R1-M2M", parent=r0)
        Requirement.objects.create(framework=fw, code="R2-M2M", parent=r0)

        self.assertEqual(Conformity.objects.filter(organization=org).count(), 0)

        org.applicable_frameworks.add(fw)
        self.assertEqual(Conformity.objects.filter(organization=org).count(), 3)

        org.applicable_frameworks.remove(fw)
        self.assertEqual(Conformity.objects.filter(organization=org).count(), 0)

    def test_control_post_save_bootstrap_and_rebootstrap(self):
        """
        Deterministic with random date:
        - Pick a random date and freeze date.today() inside model/signals modules,
          so business logic always computes statuses against that date.
        - Do NOT delete ControlPoints manually: the save() logic must handle rebootstrap.
        - Invariants tested:
            1. Past ControlPoints are preserved.
            2. At least one non-past ControlPoint is generated.
            3. At least one of those has a monthly-sized window (≤ 31 days).
        """
        import datetime, random, importlib, contextlib
        from unittest.mock import patch

        # --- Random date (safe range for each month) ---
        year = random.randint(1970, 2999)
        month = random.randint(1, 12)
        if month == 2:
            day = random.randint(1, 28)
        elif month in (4, 6, 9, 11):
            day = random.randint(1, 30)
        else:
            day = random.randint(1, 31)
        frozen_today = datetime.date(year, month, day)

        # --- Custom subclass freezing today() ---
        class FrozenDate(datetime.date):
            @classmethod
            def today(cls):
                return frozen_today

        # Patch modules that import/use `date.today()`
        cp_mod = importlib.import_module(ControlPoint.__module__)
        try:
            signals_mod = importlib.import_module("conformity.signals")
            signals_ctx = patch.object(signals_mod, "date", FrozenDate, create=True)
        except ModuleNotFoundError:
            signals_ctx = contextlib.nullcontext()

        with patch.object(cp_mod, "date", FrozenDate, create=True), signals_ctx:
            # Create initial Control with QUARTERLY frequency -> bootstrap ControlPoints
            ctrl = Control.objects.create(title="Bootstrap", frequency=Control.Frequency.QUARTERLY)
            self.assertEqual(
                ControlPoint.objects.filter(control=ctrl).count(),
                4,
                "Initial bootstrap must create 4 ControlPoints",
            )

            # Insert one explicit past CP so preservation can be tested regardless of random date
            manual_past = ControlPoint.objects.create(
                control=ctrl,
                period_start_date=frozen_today - datetime.timedelta(days=40),
                period_end_date=frozen_today - datetime.timedelta(days=30),
            )
            manual_past.refresh_from_db()
            self.assertEqual(manual_past.status, ControlPoint.Status.MISSED)

            # Collect IDs of past CPs before frequency change
            before_qs = ControlPoint.objects.filter(control=ctrl)
            past_ids = set(
                before_qs.filter(period_end_date__lt=frozen_today).values_list("id", flat=True)
            )
            self.assertIn(manual_past.id, past_ids, "The manual past CP must be preserved later")

            # Change frequency to MONTHLY -> should preserve past and rebootstrap non-past CPs
            ctrl.frequency = Control.Frequency.MONTHLY
            ctrl.save()

            after_qs = ControlPoint.objects.filter(control=ctrl).order_by("period_start_date", "pk")

            # Past CPs are preserved
            after_ids = set(after_qs.values_list("id", flat=True))
            self.assertTrue(
                past_ids.issubset(after_ids),
                "Past ControlPoints must be preserved after frequency change",
            )

            # At least one non-past CP exists (current or future)
            non_past_after_qs = after_qs.filter(period_end_date__gte=frozen_today)
            self.assertGreater(
                non_past_after_qs.count(),
                0,
                "Rebootstrap must generate at least one non-past ControlPoint",
            )

            # At least one regenerated CP looks like a monthly window (≤ 31 days)
            monthly_like = any(
                (pe - ps).days <= 31
                for ps, pe in non_past_after_qs.values_list("period_start_date", "period_end_date")
            )
            self.assertTrue(
                monthly_like,
                "Changing to MONTHLY must create at least one monthly-sized period (≤ 31 days)",
            )

    def test_controlpoint_presave_status_transitions(self):
        """ControlPoint pre_save should set status based on the current period window."""
        ctrl = Control.objects.create(title="StatusCalc", frequency=Control.Frequency.YEARLY)
        today = date.today()

        cp_past = ControlPoint.objects.create(
            control=ctrl,
            period_start_date=today - timedelta(days=10),
            period_end_date=today - timedelta(days=1),
        )
        cp_now = ControlPoint.objects.create(
            control=ctrl,
            period_start_date=today,
            period_end_date=today,
        )
        cp_future = ControlPoint.objects.create(
            control=ctrl,
            period_start_date=today + timedelta(days=1),
            period_end_date=today + timedelta(days=2),
        )

        cp_past.refresh_from_db()
        cp_now.refresh_from_db()
        cp_future.refresh_from_db()

        self.assertEqual(cp_past.status, ControlPoint.Status.MISSED)
        self.assertEqual(cp_now.status, ControlPoint.Status.TOBEEVALUATED)
        self.assertEqual(cp_future.status, ControlPoint.Status.SCHEDULED)

    def test_attachment_presave_sets_mime_type(self):
        """
        Attachment pre_save should populate mime_type.
        Uses a temporary file and ensures no trace is left in DB or FS after the test.
        """
        import sys, types, tempfile, os
        from unittest.mock import patch
        from django.core.files.uploadedfile import SimpleUploadedFile

        class FakeMagic:
            def __init__(self, mime=False):
                self._mime = mime

            def from_buffer(self, _buf):
                return "text/plain"

        # If python-magic is not present, inject a minimal stub so the model code can import it
        if "magic" not in sys.modules:
            sys.modules["magic"] = types.SimpleNamespace(Magic=FakeMagic)

        # Create a temporary file for upload
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        tmp.write(b"hello world")
        tmp.flush()
        tmp.close()

        try:
            with open(tmp.name, "rb") as f:
                uploaded = SimpleUploadedFile("note.txt", f.read(), content_type="text/plain")

            # Patch Magic so mime_type is deterministic
            with patch("magic.Magic", FakeMagic, create=True):
                att = Attachment.objects.create(file=uploaded)
                att.refresh_from_db()
                self.assertEqual(att.mime_type, "text/plain")

            # Clean DB record explicitly
            att.delete()

        finally:
            # Ensure the temporary file is removed
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)

    def test_findings_archiving_updates_on_action_save_and_m2m(self):
        """
        Finding.archived should reflect whether active Actions are linked
        (via m2m signals and action post_save).
        """
        org = Organization.objects.create(name="Org")
        audit = Audit.objects.create(organization=org, auditor="Aud", report_date=timezone.now())
        finding = Finding.objects.create(
            short_description="F1", audit=audit, severity=Finding.Severity.MAJOR
        )

        finding.update_archived()
        finding.refresh_from_db()
        self.assertFalse(finding.archived, msg="Finding with no action should not be archived")

        act = Action.objects.create(title="A1", organization=org, status=Action.Status.PLANNING)
        act.associated_findings.add(finding)
        act.save()
        finding.refresh_from_db()
        self.assertFalse(finding.archived, msg="Finding with active action should not be archived")

        act.status = Action.Status.ENDED
        act.save()
        finding.refresh_from_db()
        self.assertTrue(finding.archived, msg="Finding with ended action should be archived")

        act.status = Action.Status.PLANNING
        act.save()
        finding.refresh_from_db()
        self.assertFalse(finding.archived, msg="If action is back to active, finding should not be archived")

        finding.actions.remove(act)
        finding.refresh_from_db()
        self.assertFalse(finding.archived, msg="Finding with no action should not be archived")

def test_controlpoint_final_status_updates_conformity(self):
    """
    ControlPoint final status should propagate to related leaf Conformity through signals.
    Extended scenarios covered:
      - Single CP: NONCOMPLIANT -> 0, COMPLIANT -> 100
      - Multiple Controls: one compliant, one noncompliant -> overall 0
      - Multiple Controls: one compliant, one pending -> overall 100 (at least one OK)
    """
    # Base setup
    org = Organization.objects.create(name="OrgC")
    fw = Framework.objects.create(name="FWC")
    r0 = Requirement.objects.create(framework=fw, code="R0")
    r1 = Requirement.objects.create(framework=fw, code="R1", parent=r0)

    org.applicable_frameworks.add(fw)
    conf_leaf = Conformity.objects.get(organization=org, requirement=r1)

    # --- Single control path (original assertions) ---
    ctrl = Control.objects.create(title="CTRL", frequency=Control.Frequency.YEARLY)
    ctrl.conformity.add(conf_leaf)

    # Take the latest CP (bootstrap produced at least one)
    cp = ControlPoint.objects.filter(control=ctrl).order_by("period_start_date", "pk").last()
    self.assertIsNotNone(cp, "Bootstrap must create at least one ControlPoint")

    # 1) NONCOMPLIANT -> Conformity 0 (justification CONTROL)
    cp.status = ControlPoint.Status.NONCOMPLIANT
    cp.save()
    conf_leaf.refresh_from_db()
    self.assertEqual(conf_leaf.status, 0, msg="Conformity should reflect NONCOMPLIANT control")
    self.assertEqual(
        conf_leaf.status_justification, Conformity.StatusJustification.CONTROL,
        msg="Justification should be CONTROL when updated via ControlPoint",
    )

    # 2) COMPLIANT -> Conformity 100 (justification CONTROL)
    cp.status = ControlPoint.Status.COMPLIANT
    cp.save()
    conf_leaf.refresh_from_db()
    self.assertEqual(conf_leaf.status, 100, msg="Conformity should reflect COMPLIANT control")
    self.assertEqual(
        conf_leaf.status_justification, Conformity.StatusJustification.CONTROL,
        msg="Justification should be CONTROL when updated via ControlPoint",
    )

    # --- Multiple controls linked to the same conformity ---
    ctrl_ok = Control.objects.create(title="CTRL-OK", frequency=Control.Frequency.YEARLY)
    ctrl_ko = Control.objects.create(title="CTRL-KO", frequency=Control.Frequency.YEARLY)
    ctrl_ok.conformity.add(conf_leaf)
    ctrl_ko.conformity.add(conf_leaf)

    cp_ok = ControlPoint.objects.filter(control=ctrl_ok).order_by("period_start_date", "pk").last()
    cp_ko = ControlPoint.objects.filter(control=ctrl_ko).order_by("period_start_date", "pk").last()
    self.assertIsNotNone(cp_ok)
    self.assertIsNotNone(cp_ko)

    # 3) One OK, one NONCOMPLIANT -> overall should be 0
    cp_ok.status = ControlPoint.Status.COMPLIANT
    cp_ok.save()
    cp_ko.status = ControlPoint.Status.NONCOMPLIANT
    cp_ko.save()
    conf_leaf.refresh_from_db()
    self.assertEqual(
        conf_leaf.status, 0,
        msg="If any linked control is NONCOMPLIANT, conformity should be 0",
    )
    self.assertEqual(
        conf_leaf.status_justification, Conformity.StatusJustification.CONTROL,
        msg="Justification should remain CONTROL after control updates",
    )

    # 4) One OK, one pending (e.g., SCHEDULED/TOBEEVALUATED) -> overall should be 100
    #    Rationale: at least one control reached COMPLIANT and none is NONCOMPLIANT.
    cp_ko.status = ControlPoint.Status.SCHEDULED
    cp_ko.save()
    conf_leaf.refresh_from_db()
    self.assertEqual(
        conf_leaf.status, 100,
        msg="With one COMPLIANT and others pending (no NONCOMPLIANT), conformity should be 100",
    )
    self.assertEqual(
        conf_leaf.status_justification, Conformity.StatusJustification.CONTROL,
    )

    def test_controlpoint_final_status_updates_conformity(self):
        """
        ControlPoint final status should propagate to related leaf Conformity through signals.
        Extended scenarios covered:
          - Single CP: NONCOMPLIANT -> 0, COMPLIANT -> 100
          - Multiple Controls: one compliant, one noncompliant -> overall 0
          - Multiple Controls: one compliant, one pending -> overall 100 (at least one OK)
        """
        # Base setup
        org = Organization.objects.create(name="OrgC")
        fw = Framework.objects.create(name="FWC")
        r0 = Requirement.objects.create(framework=fw, code="R0")
        r1 = Requirement.objects.create(framework=fw, code="R1", parent=r0)

        org.applicable_frameworks.add(fw)
        conf_leaf = Conformity.objects.get(organization=org, requirement=r1)

        # Single control
        ctrl = Control.objects.create(title="CTRL", frequency=Control.Frequency.YEARLY)
        ctrl.conformity.add(conf_leaf)

        ## Take the latest CP (bootstrap produced at least one)
        cp = ControlPoint.objects.filter(control=ctrl).order_by("period_start_date", "pk").last()
        self.assertIsNotNone(cp, "Bootstrap must create at least one ControlPoint")

        ## NONCOMPLIANT -> Conformity 0 (justification CONTROL)
        cp.status = ControlPoint.Status.NONCOMPLIANT
        cp.save()
        conf_leaf.refresh_from_db()
        self.assertEqual(conf_leaf.status, 0, msg="Conformity should reflect NONCOMPLIANT control")
        self.assertEqual(
            conf_leaf.status_justification, Conformity.StatusJustification.CONTROL,
            msg="Justification should be CONTROL when updated via ControlPoint",
        )

        ## COMPLIANT -> Conformity 100 (justification CONTROL)
        cp.status = ControlPoint.Status.COMPLIANT
        cp.save()
        conf_leaf.refresh_from_db()
        self.assertEqual(conf_leaf.status, 100, msg="Conformity should reflect COMPLIANT control")
        self.assertEqual(
            conf_leaf.status_justification, Conformity.StatusJustification.CONTROL,
            msg="Justification should be CONTROL when updated via ControlPoint",
        )

        # Multiple controls
        ctrl_ok = Control.objects.create(title="CTRL-OK", frequency=Control.Frequency.YEARLY)
        ctrl_ko = Control.objects.create(title="CTRL-KO", frequency=Control.Frequency.YEARLY)
        ctrl_ok.conformity.add(conf_leaf)
        ctrl_ko.conformity.add(conf_leaf)

        cp_ok = ControlPoint.objects.filter(control=ctrl_ok).order_by("period_start_date", "pk").last()
        cp_ko = ControlPoint.objects.filter(control=ctrl_ko).order_by("period_start_date", "pk").last()
        self.assertIsNotNone(cp_ok)
        self.assertIsNotNone(cp_ko)

        ## One OK, one NONCOMPLIANT -> overall should be 0
        cp_ok.status = ControlPoint.Status.COMPLIANT
        cp_ok.save()
        cp_ko.status = ControlPoint.Status.NONCOMPLIANT
        cp_ko.save()
        conf_leaf.refresh_from_db()
        self.assertEqual(
            conf_leaf.status, 0,
            msg="If any linked control is NONCOMPLIANT, conformity should be 0",
        )
        self.assertEqual(
            conf_leaf.status_justification, Conformity.StatusJustification.CONTROL,
            msg="Justification should remain CONTROL after control updates",
        )

        ## One OK, one pending (e.g., SCHEDULED/TOBEEVALUATED) -> overall should be 100
        cp_ko.status = ControlPoint.Status.SCHEDULED
        cp_ko.save()
        conf_leaf.refresh_from_db()
        self.assertEqual(
            conf_leaf.status, 100,
            msg="With one COMPLIANT and others pending (no NONCOMPLIANT), conformity should be 100",
        )
        self.assertEqual(
            conf_leaf.status_justification, Conformity.StatusJustification.CONTROL,
        )

    def test_action_saved_updates_conformity_status(self):
        """
        Action status transitions should propagate to related Conformity through signals.
        Extended scenarios covered:
          - Single Action: PLANNING -> 0, ENDED -> 100
          - Multiple Actions: one ended, one active -> overall 0 (active exists)
        """
        # Base setup
        org = Organization.objects.create(name="OrgA")
        fw = Framework.objects.create(name="FWA")
        r0 = Requirement.objects.create(framework=fw, code="R0")
        r1 = Requirement.objects.create(framework=fw, code="R1", parent=r0)

        org.applicable_frameworks.add(fw)
        conf_leaf = Conformity.objects.get(organization=org, requirement=r1)

        # Single action path
        act = Action.objects.create(
            title="Improve X", organization=org, status=Action.Status.PLANNING
        )
        act.associated_conformity.add(conf_leaf)

        ## PLANNING -> Conformity 0 (justification ACTION)
        act.save()
        conf_leaf.refresh_from_db()
        self.assertEqual(conf_leaf.status, 0, msg="Conformity should reflect active action")
        self.assertEqual(
            conf_leaf.status_justification, Conformity.StatusJustification.ACTION,
            msg="Justification should be ACTION when updated via Action",
        )

        ## ENDED -> Conformity 100 (no active actions remain)
        act.status = Action.Status.ENDED
        act.save()
        conf_leaf.refresh_from_db()
        self.assertEqual(conf_leaf.status, 100, msg="Conformity should reflect ended action")
        self.assertEqual(
            conf_leaf.status_justification, Conformity.StatusJustification.ACTION,
        )

        # Multiple actions
        act2 = Action.objects.create(
            title="Improve Y", organization=org, status=Action.Status.PLANNING
        )
        act2.associated_conformity.add(conf_leaf)

        ## Mix: act (ENDED), act2 (PLANNING) -> still has active -> 0
        conf_leaf.refresh_from_db()
        self.assertEqual(
            conf_leaf.status, 0,
            msg="If at least one action is active, conformity should be 0",
        )
        self.assertEqual(
            conf_leaf.status_justification, Conformity.StatusJustification.ACTION,
        )

    def test_actions_controls_interplay_updates_conformity(self):
        """
        Interplay between Actions and Controls must consistently update Conformity:
          - If at least one Action is active -> Conformity = 0 (justification ACTION).
          - If no Action is active and at least one ControlPoint is NONCOMPLIANT -> 0 (CONTROL).
          - If no Action is active and no ControlPoint is NONCOMPLIANT but at least one is COMPLIANT -> 100 (CONTROL).
          - The last updated source (Action vs Control) should drive the justification.
        """
        # --- Base setup (org, framework, requirement, leaf conformity) ---
        org = Organization.objects.create(name="Org-Interplay")
        fw = Framework.objects.create(name="FW-Interplay")
        r0 = Requirement.objects.create(framework=fw, code="R0")
        r1 = Requirement.objects.create(framework=fw, code="R1", parent=r0)

        org.applicable_frameworks.add(fw)
        conf_leaf = Conformity.objects.get(organization=org, requirement=r1)

        # Two controls linked to the same conformity
        ctrl_a = Control.objects.create(title="CTRL-A", frequency=Control.Frequency.YEARLY)
        ctrl_b = Control.objects.create(title="CTRL-B", frequency=Control.Frequency.YEARLY)
        ctrl_a.conformity.add(conf_leaf)
        ctrl_b.conformity.add(conf_leaf)

        # Latest ControlPoints bootstrapped by frequency
        cp_a = ControlPoint.objects.filter(control=ctrl_a).order_by("period_start_date", "pk").last()
        cp_b = ControlPoint.objects.filter(control=ctrl_b).order_by("period_start_date", "pk").last()
        self.assertIsNotNone(cp_a, "Bootstrap must create at least one ControlPoint for CTRL-A")
        self.assertIsNotNone(cp_b, "Bootstrap must create at least one ControlPoint for CTRL-B")

        # Normalize baseline: bring controls to a compliant state
        cp_a.status = ControlPoint.Status.COMPLIANT
        cp_a.save()
        cp_b.status = ControlPoint.Status.COMPLIANT
        cp_b.save()
        conf_leaf.refresh_from_db()
        self.assertEqual(conf_leaf.status, 100, "With compliant controls and no active actions, status should be 100")
        self.assertEqual(
            conf_leaf.status_justification,
            Conformity.StatusJustification.CONTROL,
            "Justification should reflect the last writer: CONTROL",
        )

        # Add an active action -> should drop to 0, justification ACTION
        act1 = Action.objects.create(
            title="Improve A", organization=org, status=Action.Status.PLANNING
        )
        act1.associated_conformity.add(conf_leaf)
        conf_leaf.refresh_from_db()
        self.assertEqual(conf_leaf.status, 0, "Active action must drive conformity to 0")
        self.assertEqual(
            conf_leaf.status_justification,
            Conformity.StatusJustification.ACTION,
            "Justification should be ACTION when action is active",
        )

        # Add a second action already ended -> still 0 because at least one is active
        act2 = Action.objects.create(
            title="Improve B", organization=org, status=Action.Status.ENDED
        )
        act2.associated_conformity.add(conf_leaf)
        conf_leaf.refresh_from_db()
        self.assertEqual(conf_leaf.status, 0, "Having at least one active action keeps status at 0")
        self.assertEqual(
            conf_leaf.status_justification,
            Conformity.StatusJustification.ACTION,
        )

        # End the active action -> all actions ended; controls still compliant -> 100 (ACTION is the last writer)
        act1.status = Action.Status.ENDED
        act1.save()
        conf_leaf.refresh_from_db()
        self.assertEqual(conf_leaf.status, 100, "No active actions; controls are compliant -> 100")
        self.assertEqual(
            conf_leaf.status_justification,
            Conformity.StatusJustification.ACTION,
            "Justification should come from the last update source (action ended)",
        )

        # Flip one control to NONCOMPLIANT -> should drop to 0, justification CONTROL
        cp_a.status = ControlPoint.Status.NONCOMPLIANT
        cp_a.save()
        conf_leaf.refresh_from_db()
        self.assertEqual(conf_leaf.status, 0, "A NONCOMPLIANT control must drive conformity to 0")
        self.assertEqual(
            conf_leaf.status_justification,
            Conformity.StatusJustification.CONTROL,
            "Justification should be CONTROL after control update",
        )

        # Bring that control back to COMPLIANT -> 100 (since both controls are OK and no active actions)
        cp_a.status = ControlPoint.Status.COMPLIANT
        cp_a.save()
        conf_leaf.refresh_from_db()
        self.assertEqual(conf_leaf.status, 100, "All controls compliant and no active actions -> 100")
        self.assertEqual(
            conf_leaf.status_justification,
            Conformity.StatusJustification.CONTROL,
        )

        # Introduce a new active action again -> back to 0 (ACTION)
        act3 = Action.objects.create(
            title="Improve C", organization=org, status=Action.Status.PLANNING
        )
        act3.associated_conformity.add(conf_leaf)
        conf_leaf.refresh_from_db()
        self.assertEqual(conf_leaf.status, 0, "A newly active action should bring conformity back to 0")
        self.assertEqual(
            conf_leaf.status_justification,
            Conformity.StatusJustification.ACTION,
            "Justification should switch to ACTION with a new active action",
        )
