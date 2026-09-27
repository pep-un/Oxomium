from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase
from django.template.loader import render_to_string
from django.urls import reverse

from conformity.models import Organization


User = get_user_model()


class FeedbackComponentTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def render_message(self, level, text):
        request = self.factory.get("/")
        request.session = {}
        storage = FallbackStorage(request)
        request._messages = storage
        messages.add_message(request, level, text)
        return render_to_string("includes/messages.html", request=request)

    def test_message_levels_map_to_accessible_bootstrap_alerts(self):
        cases = (
            (messages.SUCCESS, "Saved", "alert-success", 'role="status"'),
            (messages.INFO, "Information", "alert-info", 'role="status"'),
            (messages.WARNING, "Warning", "alert-warning", 'role="status"'),
            (messages.ERROR, "Error", "alert-danger", 'role="alert"'),
        )
        for level, text, css_class, role in cases:
            with self.subTest(level=level):
                html = self.render_message(level, text)
                self.assertIn(css_class, html)
                self.assertIn(role, html)
                self.assertIn(text, html)
                self.assertIn("bi-", html)


class FormFeedbackTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="feedback-user", password="p@ss")
        self.client.force_login(self.user)

    def test_create_feedback_survives_redirect(self):
        response = self.client.post(
            reverse("conformity:organization_create"),
            {"name": "Created organization"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Organization created successfully.")
        self.assertContains(response, "alert-success")

    def test_update_feedback_survives_redirect(self):
        organization = Organization.objects.create(name="Before update")
        response = self.client.post(
            reverse("conformity:organization_form", args=[organization.pk]),
            {"name": "After update"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Organization updated successfully.")

    def test_field_validation_error_stays_inline_without_global_error(self):
        response = self.client.post(
            reverse("conformity:organization_create"),
            {"name": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")
        self.assertNotContains(response, "alert-danger")
        self.assertNotContains(response, "created successfully")
