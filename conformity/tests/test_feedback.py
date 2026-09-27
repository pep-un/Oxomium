from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
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

    def test_non_success_message_levels_map_to_dismissible_bootstrap_alerts(self):
        cases = (
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
                self.assertIn("alert-dismissible", html)
                self.assertIn('data-bs-dismiss="alert"', html)

    def test_success_messages_are_not_rendered_by_default(self):
        html = self.render_message(messages.SUCCESS, "Saved")
        self.assertNotIn("Saved", html)
        self.assertNotIn("alert-success", html)


class FormFeedbackTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="feedback-user", password="p@ss")
        self.client.force_login(self.user)

    def test_success_feedback_is_not_rendered_after_create(self):
        response = self.client.post(
            reverse("conformity:organization_create"),
            {"name": "Created organization"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "created successfully")
        self.assertNotContains(response, "alert-success")

    def test_success_feedback_is_not_rendered_after_update(self):
        organization = Organization.objects.create(name="Before update")
        response = self.client.post(
            reverse("conformity:organization_form", args=[organization.pk]),
            {"name": "After update"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "updated successfully")
        self.assertNotContains(response, "alert-success")

    def test_field_validation_error_stays_inline_without_global_error(self):
        response = self.client.post(
            reverse("conformity:organization_create"),
            {"name": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")
        self.assertNotContains(response, "alert-danger")
        self.assertNotContains(response, "created successfully")


    def test_attachment_validation_error_is_also_shown_as_global_feedback(self):
        upload = SimpleUploadedFile(
            "report.exe",
            b"MZ" + b"\x00" * 128,
            content_type="application/octet-stream",
        )
        response = self.client.post(
            reverse("conformity:organization_create"),
            {"name": "Upload failure", "attachments": upload},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Attachment upload failed:")
        self.assertContains(response, "alert-danger")
        self.assertNotContains(response, "created successfully")
