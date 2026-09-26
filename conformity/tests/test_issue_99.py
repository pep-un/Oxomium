from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse

from conformity.filterset import ActionFilter
from conformity.models import Action, Organization
from conformity.tables import ActionTable


User = get_user_model()


class ActionPriorityModelTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Priority Org")

    def test_priority_choices_and_null_default(self):
        action = Action.objects.create(
            title="No priority",
            organization=self.organization,
        )

        self.assertIsNone(action.priority)
        self.assertEqual(
            dict(Action.Priority.choices),
            {
                1: "Priority 1",
                2: "Priority 2",
                3: "Priority 3",
                4: "Priority 4",
                5: "Priority 5",
            },
        )

    def test_active_transition_without_priority_is_rejected(self):
        for status in (
            Action.Status.PLANNING,
            Action.Status.IMPLEMENTING,
            Action.Status.CONTROLLING,
        ):
            with self.subTest(status=status):
                action = Action.objects.create(
                    title=f"Needs priority {status}",
                    organization=self.organization,
                    status=Action.Status.ANALYSING,
                )
                action.status = status

                with self.assertRaises(ValidationError) as caught:
                    action.save()

                self.assertIn("priority", caught.exception.message_dict)
                action.refresh_from_db()
                self.assertEqual(action.status, Action.Status.ANALYSING)

    def test_active_transition_with_priority_is_allowed(self):
        action = Action.objects.create(
            title="Prioritized",
            organization=self.organization,
            status=Action.Status.ANALYSING,
        )
        action.priority = Action.Priority.PRIORITY_1
        action.status = Action.Status.PLANNING
        action.save()

        action.refresh_from_db()
        self.assertEqual(action.priority, Action.Priority.PRIORITY_1)
        self.assertEqual(action.status, Action.Status.PLANNING)

    def test_non_workflow_exit_does_not_require_priority(self):
        for status in (
            Action.Status.FROZEN,
            Action.Status.CANCELED,
            Action.Status.ENDED,
        ):
            with self.subTest(status=status):
                action = Action.objects.create(
                    title=f"Exit {status}",
                    organization=self.organization,
                    status=Action.Status.ANALYSING,
                )
                action.status = status
                action.save()

                action.refresh_from_db()
                self.assertEqual(action.status, status)
                self.assertIsNone(action.priority)

    def test_direct_non_analysis_creation_remains_compatible(self):
        action = Action.objects.create(
            title="Direct planning",
            organization=self.organization,
            status=Action.Status.PLANNING,
        )

        self.assertEqual(action.status, Action.Status.PLANNING)
        self.assertIsNone(action.priority)

    def test_partial_status_save_cannot_bypass_persisted_priority(self):
        action = Action.objects.create(
            title="Partial transition",
            organization=self.organization,
            status=Action.Status.ANALYSING,
        )
        action.priority = Action.Priority.PRIORITY_1
        action.status = Action.Status.PLANNING

        with self.assertRaises(ValidationError) as caught:
            action.save(update_fields=["status"])

        self.assertIn("priority", caught.exception.message_dict)
        action.refresh_from_db()
        self.assertEqual(action.status, Action.Status.ANALYSING)
        self.assertIsNone(action.priority)

    def test_established_priority_cannot_be_cleared_in_active_workflow(self):
        action = Action.objects.create(
            title="Established priority",
            organization=self.organization,
            status=Action.Status.PLANNING,
            priority=Action.Priority.PRIORITY_2,
        )
        action.priority = None

        with self.assertRaises(ValidationError) as caught:
            action.save(update_fields=["priority"])

        self.assertIn("priority", caught.exception.message_dict)
        action.refresh_from_db()
        self.assertEqual(action.priority, Action.Priority.PRIORITY_2)

    def test_legacy_non_analysis_null_priority_remains_editable(self):
        action = Action.objects.create(
            title="Legacy",
            organization=self.organization,
            status=Action.Status.PLANNING,
            priority=Action.Priority.PRIORITY_3,
        )
        Action.objects.filter(pk=action.pk).update(priority=None)
        action.refresh_from_db()

        action.title = "Legacy edited"
        action.save()

        action.refresh_from_db()
        self.assertEqual(action.title, "Legacy edited")
        self.assertIsNone(action.priority)


class ActionPriorityFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="action-priority-form-user")
        self.organization = Organization.objects.create(name="Priority Form Org")
        self.client.force_login(self.user)

    def test_priority_is_available_in_analysis_section(self):
        action = Action.objects.create(
            title="Form action",
            organization=self.organization,
            status=Action.Status.ANALYSING,
        )

        response = self.client.get(
            reverse("conformity:action_form", args=[action.pk]),
        )

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertIn("priority", form.fields)
        self.assertEqual(
            [(value, str(label)) for value, label in form.fields["priority"].choices],
            [
                ("", "Not defined"),
                (1, "Priority 1"),
                (2, "Priority 2"),
                (3, "Priority 3"),
                (4, "Priority 4"),
                (5, "Priority 5"),
            ],
        )

        html = response.content.decode()
        analysis_start = html.index('id="collapseAnalyse"')
        priority_position = html.index('name="priority"')
        planning_start = html.index('id="collapsePlan"')
        self.assertLess(analysis_start, priority_position)
        self.assertLess(priority_position, planning_start)

    def test_form_rejects_transition_without_priority(self):
        action = Action.objects.create(
            title="Transition form",
            organization=self.organization,
            status=Action.Status.ANALYSING,
        )

        response = self.client.post(
            reverse("conformity:action_form", args=[action.pk]),
            {
                "title": action.title,
                "owner": "",
                "status": Action.Status.PLANNING,
                "status_comment": "",
                "reference": "",
                "priority": "",
                "description": "",
                "organization": self.organization.pk,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("priority", response.context["form"].errors)
        action.refresh_from_db()
        self.assertEqual(action.status, Action.Status.ANALYSING)

    def test_configured_priority_is_locked_after_analysis(self):
        action = Action.objects.create(
            title="Locked priority",
            organization=self.organization,
            status=Action.Status.PLANNING,
            priority=Action.Priority.PRIORITY_2,
        )

        response = self.client.get(
            reverse("conformity:action_form", args=[action.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].fields["priority"].disabled)

    def test_priority_remains_editable_during_analysis(self):
        action = Action.objects.create(
            title="Analysis priority",
            organization=self.organization,
            status=Action.Status.ANALYSING,
            priority=Action.Priority.PRIORITY_2,
        )

        response = self.client.get(
            reverse("conformity:action_form", args=[action.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].fields["priority"].disabled)

    def test_legacy_null_priority_remains_editable_after_analysis(self):
        action = Action.objects.create(
            title="Legacy null priority",
            organization=self.organization,
            status=Action.Status.PLANNING,
        )

        response = self.client.get(
            reverse("conformity:action_form", args=[action.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].fields["priority"].disabled)


class ActionPriorityRenderingTests(TestCase):
    def test_priority_column_is_part_of_rich_action_table(self):
        table = ActionTable([])

        self.assertIn("priority", table.columns)
        self.assertEqual(table.columns["priority"].verbose_name, "Priority")
        self.assertTrue(table.columns["priority"].orderable)

    def test_priority_badge_mapping(self):
        expected = {
            Action.Priority.PRIORITY_1: ("text-bg-dark", "Priority 1"),
            Action.Priority.PRIORITY_2: ("text-bg-danger", "Priority 2"),
            Action.Priority.PRIORITY_3: ("text-bg-warning", "Priority 3"),
            Action.Priority.PRIORITY_4: ("text-bg-secondary", "Priority 4"),
            Action.Priority.PRIORITY_5: ("text-bg-info", "Priority 5"),
            None: ("text-bg-light", "Not defined"),
        }

        for priority, (css_class, label) in expected.items():
            with self.subTest(priority=priority):
                html = render_to_string(
                    "conformity/includes/action_priority.html",
                    {"action": Action(priority=priority)},
                )
                self.assertIn("badge rounded-pill", html)
                self.assertIn(css_class, html)
                self.assertIn(label, html)


class ActionPriorityListTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="action-priority-user")
        self.organization = Organization.objects.create(name="Action Priority Org")
        self.client.force_login(self.user)

        self.p1_analyzing = self.create_action(
            "P1 analysing", Action.Priority.PRIORITY_1, Action.Status.ANALYSING
        )
        self.p1_planning = self.create_action(
            "P1 planning", Action.Priority.PRIORITY_1, Action.Status.PLANNING
        )
        self.p1_implementing = self.create_action(
            "P1 implementing", Action.Priority.PRIORITY_1, Action.Status.IMPLEMENTING
        )
        self.p1_controlling = self.create_action(
            "P1 controlling", Action.Priority.PRIORITY_1, Action.Status.CONTROLLING
        )
        self.p2 = self.create_action(
            "P2", Action.Priority.PRIORITY_2, Action.Status.ANALYSING
        )
        self.p3 = self.create_action(
            "P3", Action.Priority.PRIORITY_3, Action.Status.ANALYSING
        )
        self.p4 = self.create_action(
            "P4", Action.Priority.PRIORITY_4, Action.Status.ANALYSING
        )
        self.p5 = self.create_action(
            "P5", Action.Priority.PRIORITY_5, Action.Status.ANALYSING
        )
        self.undefined = self.create_action(
            "Undefined", None, Action.Status.ANALYSING
        )
        self.closed = self.create_action(
            "Closed", Action.Priority.PRIORITY_5, Action.Status.ENDED
        )
        self.canceled = self.create_action(
            "Canceled", Action.Priority.PRIORITY_5, Action.Status.CANCELED
        )

    def create_action(self, title, priority, status):
        return Action.objects.create(
            title=title,
            organization=self.organization,
            priority=priority,
            status=status,
        )

    @staticmethod
    def table_records(response):
        return [row.record for row in response.context["table"].page.object_list]

    def test_priority_filter_is_available(self):
        self.assertIn("priority", getattr(ActionFilter, "base_filters"))

        response = self.client.get(
            reverse("conformity:action_index"),
            {"priority": Action.Priority.PRIORITY_1},
        )

        self.assertEqual(
            self.table_records(response),
            [
                self.p1_analyzing,
                self.p1_planning,
                self.p1_implementing,
                self.p1_controlling,
            ],
        )

    def test_default_filter_and_complete_ordering(self):
        response = self.client.get(reverse("conformity:action_index"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [action.title for action in self.table_records(response)],
            [
                "P1 analysing",
                "P1 planning",
                "P1 implementing",
                "P1 controlling",
                "P2",
                "P3",
                "P4",
                "P5",
                "Undefined",
            ],
        )

    def test_closed_and_canceled_are_hidden_by_default(self):
        response = self.client.get(reverse("conformity:action_index"))
        records = self.table_records(response)

        self.assertNotIn(self.closed, records)
        self.assertNotIn(self.canceled, records)

    def test_closed_and_canceled_can_be_explicitly_filtered(self):
        for status, expected in (
            (Action.Status.ENDED, self.closed),
            (Action.Status.CANCELED, self.canceled),
        ):
            with self.subTest(status=status):
                response = self.client.get(
                    reverse("conformity:action_index"),
                    {"status": status},
                )
                self.assertEqual(self.table_records(response), [expected])

    def test_rich_table_renders_priority_badges(self):
        response = self.client.get(reverse("conformity:action_index"))

        self.assertContains(response, "Priority 1")
        self.assertContains(response, "text-bg-dark")
        self.assertContains(response, "Priority 5")
        self.assertContains(response, "text-bg-info")
        self.assertContains(response, "Not defined")
        self.assertContains(response, "text-bg-light")

    def test_external_reference_is_rendered_in_associations_column(self):
        action = Action.objects.create(
            title="ITSM linked",
            organization=self.organization,
            status=Action.Status.ANALYSING,
            reference="https://itsm.example.test/tickets/42",
        )

        table = ActionTable([])
        self.assertIn("associations", table.columns)
        self.assertNotIn("actions", table.columns)

        response = self.client.get(reverse("conformity:action_index"))

        self.assertContains(response, action.reference)
        self.assertContains(response, 'target="_blank"')
        self.assertContains(response, 'rel="noopener"')
        self.assertContains(
            response,
            'class="btn btn-sm btn-outline-secondary w-75 mx-auto"',
        )
        self.assertContains(response, "ITSM Ticket")
        self.assertContains(response, 'class="bi bi-box-arrow-up-right ms-1"')
        self.assertNotContains(response, ">Reference</")
