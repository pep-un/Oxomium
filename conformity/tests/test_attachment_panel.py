import os
from datetime import date
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from conformity.models import (
    Attachment,
    Audit,
    Control,
    ControlPoint,
    Framework,
    Indicator,
    IndicatorPoint,
    Organization,
)


User = get_user_model()


class AttachmentPanelTests(TestCase):
    def setUp(self):
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        config = override_settings(MEDIA_ROOT=media.name)
        config.enable()
        self.addCleanup(config.disable)

        self.user = User.objects.create_user(
            username="attachment-panel-user",
            password="secret",
        )
        self.client.force_login(self.user)

        self.framework = Framework.objects.create(
            name="Attachment framework",
            publish_by="Test",
        )
        self.organization = Organization.objects.create(
            name="Attachment organization",
        )
        self.audit = Audit.objects.create(
            organization=self.organization,
            auditor="Attachment auditor",
        )
        self.control = Control.objects.create(
            title="Attachment control",
        )
        self.control_point = ControlPoint.objects.filter(
            control=self.control,
        ).first()
        if self.control_point is None:
            self.control_point = ControlPoint.objects.create(
                control=self.control,
                period_start_date=date.today(),
                period_end_date=date.today(),
                status=ControlPoint.Status.TOBEEVALUATED,
            )

        self.indicator = Indicator.objects.create(
            name="Attachment indicator",
            responsible=self.user,
        )
        self.indicator_point = IndicatorPoint.objects.filter(
            indicator=self.indicator,
        ).first()
        if self.indicator_point is None:
            self.indicator_point = IndicatorPoint.objects.create(
                indicator=self.indicator,
                period_start_date=date.today(),
                period_end_date=date.today(),
            )

        self.attachment = Attachment.objects.create(
            file=SimpleUploadedFile(
                "panel.txt",
                b"attachment panel",
                content_type="text/plain",
            )
        )

    def test_detail_pages_use_read_only_shared_panel(self):
        self.framework.attachment.add(self.attachment)
        self.organization.attachment.add(self.attachment)
        self.audit.attachment.add(self.attachment)

        urls = (
            reverse("conformity:framework_detail", args=[self.framework.pk]),
            reverse("conformity:organization_detail", args=[self.organization.pk]),
            reverse("conformity:audit_detail", args=[self.audit.pk]),
        )
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "card border-info mb-3")
                self.assertContains(response, "panel.txt")
                self.assertContains(response, "bi-file-earmark-text")
                self.assertNotContains(response, "Remove attachment")
                self.assertNotContains(response, "Add another document")

    def test_attachment_forms_use_editable_shared_panel(self):
        owners = (
            (
                self.audit,
                "audit",
                reverse("conformity:audit_form", args=[self.audit.pk]),
                'name="type"',
            ),
            (
                self.organization,
                "organization",
                reverse(
                    "conformity:organization_form",
                    args=[self.organization.pk],
                ),
                'name="applicable_frameworks"',
            ),
            (
                self.control_point,
                "controlpoint",
                reverse(
                    "conformity:controlpoint_form",
                    args=[self.control_point.pk],
                ),
                'name="comment"',
            ),
            (
                self.indicator_point,
                "indicatorpoint",
                reverse(
                    "conformity:indicatorpoint_form",
                    args=[self.indicator_point.pk],
                ),
                'name="comment"',
            ),
        )

        for owner, owner_type, url, last_content_marker in owners:
            owner.attachment.add(self.attachment)
            with self.subTest(owner_type=owner_type):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "card border-info mb-3")
                self.assertContains(response, "Remove attachment")
                self.assertContains(response, "Add another document")
                self.assertContains(response, 'type="file"')
                self.assertContains(response, 'name="attachments"')
                self.assertContains(response, "multiple")
                self.assertContains(response, "drag &amp; drop")
                self.assertContains(response, "paste a screenshot")
                self.assertContains(response, "js-attachment-dropzone")
                self.assertContains(response, "js-attachment-pending")
                self.assertContains(response, "bi bi-download")
                self.assertContains(response, 'form="object-form"')
                html = response.content.decode()
                self.assertLess(
                    html.index(last_content_marker),
                    html.index("card border-info mb-3"),
                )
                self.assertLess(
                    html.index("card border-info mb-3"),
                    html.index("form-toolbar"),
                )
                self.assertContains(
                    response,
                    reverse(
                        "conformity:attachment_unlink",
                        args=[owner_type, owner.pk, self.attachment.pk],
                    ),
                )

    def test_create_forms_show_empty_panel_next_to_file_upload(self):
        for url in (
            reverse("conformity:audit_create"),
            reverse("conformity:organization_create"),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "card border-info mb-3")
                self.assertContains(response, "No attachment")
                self.assertContains(response, "Add another document")
                self.assertContains(response, 'type="file"')
                self.assertContains(response, 'name="attachments"')
                self.assertContains(response, "multiple")
                self.assertContains(response, "drag &amp; drop")
                self.assertContains(response, "paste a screenshot")
                self.assertContains(response, "js-attachment-dropzone")
                self.assertContains(response, "js-attachment-pending")
                self.assertContains(response, 'form="object-form"')
                html = response.content.decode()
                self.assertLess(
                    html.index("card border-info mb-3"),
                    html.index("form-toolbar"),
                )

    def test_indicator_point_upload_creates_multiple_attachment_relations(self):
        uploads = [
            SimpleUploadedFile(
                "indicator-note.txt",
                b"indicator attachment",
                content_type="text/plain",
            ),
            SimpleUploadedFile(
                "indicator-proof.txt",
                b"second indicator attachment",
                content_type="text/plain",
            ),
        ]

        response = self.client.post(
            reverse(
                "conformity:indicatorpoint_form",
                args=[self.indicator_point.pk],
            ),
            {
                "value": 50,
                "comment": "with attachments",
                "action": "save_stay",
                "attachments": uploads,
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "conformity:indicatorpoint_form",
                args=[self.indicator_point.pk],
            ),
            fetch_redirect_response=False,
        )
        self.assertEqual(self.indicator_point.attachment.count(), 2)
        self.assertEqual(
            {str(item) for item in self.indicator_point.attachment.all()},
            {"indicator-note.txt", "indicator-proof.txt"},
        )

    def test_unlink_shared_attachment_preserves_document_and_other_links(self):
        self.control_point.attachment.add(self.attachment)
        self.indicator_point.attachment.add(self.attachment)
        file_path = self.attachment.file.path

        response = self.client.post(
            reverse(
                "conformity:attachment_unlink",
                args=[
                    "controlpoint",
                    self.control_point.pk,
                    self.attachment.pk,
                ],
            )
        )

        self.assertRedirects(
            response,
            reverse(
                "conformity:controlpoint_form",
                args=[self.control_point.pk],
            ),
            fetch_redirect_response=False,
        )
        self.assertFalse(
            self.control_point.attachment.filter(pk=self.attachment.pk).exists()
        )
        self.assertTrue(
            self.indicator_point.attachment.filter(pk=self.attachment.pk).exists()
        )
        self.assertTrue(Attachment.objects.filter(pk=self.attachment.pk).exists())
        self.assertTrue(os.path.exists(file_path))

    def test_unlink_last_relation_deletes_document_and_file(self):
        self.organization.attachment.add(self.attachment)
        attachment_pk = self.attachment.pk
        file_path = self.attachment.file.path

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse(
                    "conformity:attachment_unlink",
                    args=["organization", self.organization.pk, attachment_pk],
                )
            )

        self.assertRedirects(
            response,
            reverse(
                "conformity:organization_form",
                args=[self.organization.pk],
            ),
            fetch_redirect_response=False,
        )
        self.assertFalse(Attachment.objects.filter(pk=attachment_pk).exists())
        self.assertFalse(os.path.exists(file_path))

    def test_unlink_rejects_attachment_not_linked_to_owner(self):
        other = Organization.objects.create(name="Other attachment organization")
        response = self.client.post(
            reverse(
                "conformity:attachment_unlink",
                args=["organization", other.pk, self.attachment.pk],
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Attachment.objects.filter(pk=self.attachment.pk).exists())
