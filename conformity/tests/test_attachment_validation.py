from datetime import date
import hashlib
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.db import models
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils.datastructures import MultiValueDict
from constance.test import override_config

from conformity.forms import AuditForm, ControlPointForm, IndicatorPointForm, OrganizationForm
from conformity.models import Attachment, Audit, Framework, Indicator, IndicatorPoint, Organization
from conformity.validators import (
    attachment_accept,
    configured_mime_policy,
    inspect_attachment,
    mime_category_details,
    validate_attachment,
    validate_attachment_once,
)


class AttachmentValidationTests(TestCase):
    def upload(self, name="report.pdf", content=b"%PDF-1.4 test", content_type="application/octet-stream"):
        return SimpleUploadedFile(name, content, content_type=content_type)

    @patch("conformity.validators.inspect_attachment", return_value=("application/pdf", "a" * 64))
    def test_allowed_file_uses_detected_content_type(self, _inspect):
        upload = self.upload(content_type="application/x-msdownload")
        self.assertEqual(validate_attachment(upload), ("application/pdf", "a" * 64))

    @patch("conformity.validators.inspect_attachment", return_value=("application/x-executable", "a" * 64))
    def test_forbidden_detected_mime_is_rejected(self, _inspect):
        with self.assertRaisesMessage(ValidationError, "Unsupported file type"):
            validate_attachment(self.upload())

    @patch("conformity.validators.inspect_attachment", return_value=("application/pdf", "a" * 64))
    def test_misleading_extension_is_rejected(self, _inspect):
        with self.assertRaisesMessage(ValidationError, "does not match detected type"):
            validate_attachment(self.upload(name="report.exe"))

    @override_config(ATTACHMENT_MAX_SIZE_MB=1)
    def test_oversized_file_is_rejected_before_temp_inspection(self):
        upload = self.upload(content=b"x" * (1024 * 1024 + 1))
        with patch("conformity.validators.inspect_attachment") as inspect:
            with self.assertRaisesMessage(ValidationError, "maximum allowed size"):
                validate_attachment(upload)
            inspect.assert_not_called()

    @override_config(ATTACHMENT_MAX_SIZE_MB=1)
    @patch("conformity.validators.inspect_attachment", return_value=("application/pdf", "a" * 64))
    def test_boundary_size_is_allowed(self, _inspect):
        upload = self.upload(content=b"x" * (1024 * 1024))
        self.assertEqual(validate_attachment(upload), ("application/pdf", "a" * 64))

    @patch("conformity.validators.Magic")
    def test_inspect_attachment_uses_temp_file_hashes_and_restores_position(self, magic_class):
        content = b"PK\x03\x04" + b"x" * 16384
        upload = self.upload(name="archive.zip", content=content)
        upload.seek(123)

        magic = MagicMock()
        magic.from_file.return_value = "application/zip; charset=binary"
        magic_class.return_value = magic

        mime_type, checksum = inspect_attachment(upload)

        self.assertEqual(mime_type, "application/zip")
        self.assertEqual(checksum, hashlib.sha256(content).hexdigest())
        magic.from_file.assert_called_once()
        self.assertEqual(upload.tell(), 123)

    @patch("conformity.validators.validate_attachment", return_value=("application/pdf", "b" * 64))
    def test_attachment_model_stores_checksum_on_direct_orm_save(self, _validate):
        attachment = Attachment.objects.create(file=self.upload())
        self.assertEqual(attachment.mime_type, "application/pdf")
        self.assertEqual(attachment.sha256, "b" * 64)
        self.assertTrue(attachment.pk)

    @patch("conformity.validators.validate_attachment", return_value=("application/pdf", "c" * 64))
    def test_identical_upload_reuses_existing_attachment(self, _validate):
        first, created_first = Attachment.get_or_create_for_upload(self.upload(name="first.pdf"))
        second, created_second = Attachment.get_or_create_for_upload(self.upload(name="second.pdf"))

        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Attachment.objects.count(), 1)
        self.assertEqual(first.file.name, second.file.name)

    @patch("conformity.validators.validate_attachment", return_value=("application/pdf", "d" * 64))
    def test_calculate_checksum_updates_legacy_attachment(self, _validate):
        attachment = Attachment.objects.create(file=self.upload())
        Attachment.objects.filter(pk=attachment.pk).update(sha256=None)
        attachment.refresh_from_db()

        result, merged = attachment.calculate_checksum_and_merge()

        self.assertFalse(merged)
        self.assertEqual(result.pk, attachment.pk)
        attachment.refresh_from_db()
        self.assertEqual(attachment.sha256, "d" * 64)
        self.assertEqual(attachment.mime_type, "application/pdf")

    @patch("conformity.validators.validate_attachment", return_value=("application/pdf", "e" * 64))
    def test_calculate_checksum_merges_into_existing_attachment_and_preserves_relations(self, _validate):
        existing = Attachment.objects.create(
            file=self.upload(name="existing.pdf"),
            mime_type="application/pdf",
            sha256="e" * 64,
        )
        duplicate = Attachment(
            file=self.upload(name="duplicate.pdf", content=b"%PDF-1.4 duplicate"),
            mime_type="application/pdf",
            sha256="legacy-placeholder",
        )
        models.Model.save(duplicate, force_insert=True)
        Attachment.objects.filter(pk=duplicate.pk).update(sha256=None)
        duplicate.refresh_from_db()
        duplicate_path = duplicate.file.path

        org = Organization.objects.create(name="Checksum merge org")
        framework = Framework.objects.create(name="Checksum framework", publish_by="Test")
        audit = Audit.objects.create(organization=org, auditor="Tester")
        org.attachment.add(duplicate)
        framework.attachment.add(duplicate)
        audit.attachment.add(duplicate)

        result, merged = duplicate.calculate_checksum_and_merge()

        self.assertTrue(merged)
        self.assertEqual(result.pk, existing.pk)
        self.assertFalse(Attachment.objects.filter(pk=duplicate.pk).exists())
        self.assertTrue(org.attachment.filter(pk=existing.pk).exists())
        self.assertTrue(framework.attachment.filter(pk=existing.pk).exists())
        self.assertTrue(audit.attachment.filter(pk=existing.pk).exists())
        self.assertEqual(org.attachment.filter(pk=existing.pk).count(), 1)
        self.assertFalse(existing.file.storage.exists(duplicate_path))

    def test_upload_forms_expose_configured_accept_and_size_hint(self):
        for form in (
            AuditForm(),
            OrganizationForm(),
            ControlPointForm(),
            IndicatorPointForm(),
        ):
            field = form.fields["attachments"]
            self.assertEqual(
                field.widget.attrs["accept"],
                attachment_accept(),
            )
            self.assertTrue(field.widget.allow_multiple_selected)
            self.assertIn("multiple", field.widget.render("attachments", None))
            self.assertIn(
                "Maximum file size",
                str(field.help_text),
            )

    @patch("conformity.forms.validate_attachment_once")
    def test_multiple_upload_field_validates_every_selected_file(self, validate):
        first = self.upload(name="first.pdf")
        second = self.upload(name="second.pdf")
        form = OrganizationForm(
            data={
                "name": "Multiple upload organization",
                "administrative_id": "",
                "description": "",
            },
            files=MultiValueDict({"attachments": [first, second]}),
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(len(form.cleaned_data["attachments"]), 2)
        self.assertEqual(validate.call_count, 2)

    @patch("conformity.validators.validate_attachment", return_value=("application/pdf", "f" * 64))
    def test_validate_attachment_once_reuses_cached_result(self, validate):
        upload = self.upload()

        first = validate_attachment_once(upload)
        second = validate_attachment_once(upload)

        self.assertEqual(first, ("application/pdf", "f" * 64))
        self.assertEqual(second, first)
        validate.assert_called_once_with(upload)

    def test_accept_hint_comes_from_configured_mime_types(self):
        with override_config(
            ATTACHMENT_ALLOWED_CATEGORIES=[],
            ATTACHMENT_ALLOWED_MIME_TYPES="image/png, application/pdf",
            ATTACHMENT_DENIED_MIME_TYPES="",
        ):
            self.assertEqual(attachment_accept(), "application/pdf,image/png")

    @override_config(
        ATTACHMENT_ALLOWED_CATEGORIES=[],
        ATTACHMENT_ALLOWED_MIME_TYPES="image/*",
        ATTACHMENT_DENIED_MIME_TYPES="",
    )
    @patch("conformity.validators.inspect_attachment", return_value=("image/webp", "a" * 64))
    def test_wildcard_image_prefix_allows_any_detected_image_mime(self, _inspect):
        upload = self.upload(name="picture.webp")
        self.assertEqual(validate_attachment(upload), ("image/webp", "a" * 64))

    def test_default_allowlist_includes_structured_and_presentation_formats(self):
        allowed = {
            "application/json",
            "text/json",
            "application/xml",
            "text/xml",
            "text/html",
            "application/xhtml+xml",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.oasis.opendocument.text",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.oasis.opendocument.spreadsheet",
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.oasis.opendocument.presentation",
            "image/*",
        }
        from conformity.validators import allowed_mime_types
        self.assertTrue(allowed.issubset(allowed_mime_types()))

    @override_config(
        ATTACHMENT_ALLOWED_CATEGORIES=["images"],
        ATTACHMENT_ALLOWED_MIME_TYPES="application/json",
        ATTACHMENT_DENIED_MIME_TYPES="image/png",
    )
    def test_denylist_has_precedence_over_categories_and_manual_allowlist(self):
        allowed, denied = configured_mime_policy()
        self.assertIn("image/*", allowed)
        self.assertIn("application/json", allowed)
        self.assertIn("image/png", denied)

        with patch("conformity.validators.inspect_attachment", return_value=("image/png", "c" * 64)):
            with self.assertRaisesMessage(ValidationError, "Unsupported file type"):
                validate_attachment(self.upload(name="picture.png"))

    @override_config(
        ATTACHMENT_ALLOWED_CATEGORIES=[],
        ATTACHMENT_ALLOWED_MIME_TYPES="application/x-custom",
        ATTACHMENT_DENIED_MIME_TYPES="",
    )
    @patch("conformity.validators.inspect_attachment", return_value=("application/x-custom", "d" * 64))
    def test_manual_allowlist_can_enable_custom_mime(self, _inspect):
        upload = self.upload(name="custom.bin")
        self.assertEqual(validate_attachment(upload), ("application/x-custom", "d" * 64))

    def test_mime_category_helper_exposes_exact_patterns(self):
        details = {item["key"]: item for item in mime_category_details()}
        self.assertEqual(details["images"]["mimes"], ("image/*",))
        self.assertIn(
            "application/vnd.oasis.opendocument.presentation",
            details["presentations"]["mimes"],
        )
        self.assertIn(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            details["spreadsheets"]["mimes"],
        )

    def test_extension_mapping_for_structured_and_presentation_formats(self):
        cases = [
            ("application/json", "data.json"),
            ("application/xml", "data.xml"),
            ("text/html", "index.html"),
            ("application/msword", "document.doc"),
            ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "document.docx"),
            ("application/vnd.oasis.opendocument.text", "document.odt"),
            ("application/vnd.ms-excel", "sheet.xls"),
            ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "sheet.xlsx"),
            ("application/vnd.oasis.opendocument.spreadsheet", "sheet.ods"),
            ("text/csv", "sheet.csv"),
            ("application/vnd.ms-powerpoint", "slides.ppt"),
            ("application/vnd.openxmlformats-officedocument.presentationml.presentation", "slides.pptx"),
            ("application/vnd.oasis.opendocument.presentation", "slides.odp"),
        ]
        for mime_type, filename in cases:
            with self.subTest(mime_type=mime_type):
                with override_config(
                    ATTACHMENT_ALLOWED_CATEGORIES=[],
                    ATTACHMENT_ALLOWED_MIME_TYPES=mime_type,
                    ATTACHMENT_DENIED_MIME_TYPES="",
                ):
                    with patch("conformity.validators.inspect_attachment", return_value=(mime_type, "b" * 64)):
                        self.assertEqual(
                            validate_attachment(self.upload(name=filename)),
                            (mime_type, "b" * 64),
                        )



class AttachmentChecksumViewTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.user = get_user_model().objects.create_user(username="attachment-checksum-user")
        self.client.force_login(self.user)

    def upload(self, name="report.pdf", content=b"%PDF-1.4 test"):
        return SimpleUploadedFile(name, content, content_type="application/pdf")

    @patch("conformity.models.Attachment.calculate_checksum_and_merge")
    def test_checksum_endpoint_is_post_only_and_redirects_to_library(self, calculate):
        attachment = Attachment.objects.create(
            file=self.upload(),
            mime_type="application/pdf",
            sha256="f" * 64,
        )

        get_response = self.client.get(
            reverse("conformity:attachment_checksum", args=[attachment.pk])
        )
        self.assertEqual(get_response.status_code, 405)
        calculate.assert_not_called()

        post_response = self.client.post(
            reverse("conformity:attachment_checksum", args=[attachment.pk])
        )
        self.assertRedirects(post_response, reverse("conformity:attachment_index"))
        calculate.assert_called_once_with()

    def test_attachment_library_renders_split_checksum_control(self):
        checksum = "1" * 64
        attachment = Attachment.objects.create(
            file=self.upload(),
            mime_type="application/pdf",
            sha256=checksum,
        )

        response = self.client.get(reverse("conformity:attachment_index"))

        self.assertContains(response, checksum[:16] + "…")
        self.assertContains(response, f'data-copy-value="{checksum}"')
        self.assertContains(response, 'aria-label="Copy SHA-256"')
        self.assertNotContains(
            response,
            reverse("conformity:attachment_checksum", args=[attachment.pk]),
        )

    def test_attachment_library_renders_indicator_point_reference(self):
        organization = Organization.objects.create(name="Indicator attachment org")
        indicator = Indicator.objects.create(
            name="Indicator attachment reference",
            responsible=self.user,
        )
        point = IndicatorPoint.objects.create(
            indicator=indicator,
            period_start_date=date.today(),
            period_end_date=date.today(),
        )
        attachment = Attachment.objects.create(
            file=self.upload(name="indicator-reference.pdf"),
            mime_type="application/pdf",
            sha256="3" * 64,
        )
        point.attachment.add(attachment)

        response = self.client.get(reverse("conformity:attachment_index"))

        self.assertContains(
            response,
            reverse("conformity:indicatorpoint_form", args=[point.pk]),
        )
        self.assertContains(response, "bi bi-speedometer")

    def test_attachment_library_renders_calculate_button_for_missing_checksum(self):
        attachment = Attachment.objects.create(
            file=self.upload(name="legacy.pdf"),
            mime_type="application/pdf",
            sha256="2" * 64,
        )
        Attachment.objects.filter(pk=attachment.pk).update(sha256=None)

        response = self.client.get(reverse("conformity:attachment_index"))

        self.assertContains(
            response,
            reverse("conformity:attachment_checksum", args=[attachment.pk]),
        )
        self.assertContains(response, "Calculate SHA-256")
        self.assertContains(response, "Calculate")
