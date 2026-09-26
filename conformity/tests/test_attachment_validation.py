from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings

from conformity.forms import AuditForm, OrganizationForm
from conformity.models import Attachment
from conformity.validators import attachment_accept, validate_attachment


class AttachmentValidationTests(SimpleTestCase):
    def upload(self, name="report.pdf", content=b"%PDF-1.4 test", content_type="application/octet-stream"):
        return SimpleUploadedFile(name, content, content_type=content_type)

    @patch("conformity.validators.detect_mime", return_value="application/pdf")
    def test_allowed_file_uses_detected_content_type(self, _detect):
        upload = self.upload(content_type="application/x-msdownload")
        self.assertEqual(validate_attachment(upload), "application/pdf")

    @patch("conformity.validators.detect_mime", return_value="application/x-executable")
    def test_forbidden_detected_mime_is_rejected(self, _detect):
        with self.assertRaisesMessage(ValidationError, "Unsupported file type"):
            validate_attachment(self.upload())

    @patch("conformity.validators.detect_mime", return_value="application/pdf")
    def test_misleading_extension_is_rejected(self, _detect):
        with self.assertRaisesMessage(ValidationError, "does not match detected type"):
            validate_attachment(self.upload(name="report.exe"))

    @patch("conformity.validators.config.ATTACHMENT_MAX_SIZE_MB", 1)
    def test_oversized_file_is_rejected(self):
        upload = self.upload(content=b"x" * (1024 * 1024 + 1))
        with self.assertRaisesMessage(ValidationError, "maximum allowed size"):
            validate_attachment(upload)

    @patch("conformity.validators.config.ATTACHMENT_MAX_SIZE_MB", 1)
    @patch("conformity.validators.detect_mime", return_value="application/pdf")
    def test_boundary_size_is_allowed(self, _detect):
        upload = self.upload(content=b"x" * (1024 * 1024))
        self.assertEqual(validate_attachment(upload), "application/pdf")

    @patch("conformity.validators.detect_mime", return_value="application/pdf")
    def test_attachment_model_validates_direct_orm_save(self, _detect):
        attachment = Attachment(file=self.upload())
        with patch("django.db.models.Model.save") as model_save:
            attachment.save()
        self.assertEqual(attachment.mime_type, "application/pdf")
        model_save.assert_called_once()

    def test_upload_forms_expose_configured_accept_and_size_hint(self):
        for form in (AuditForm(), OrganizationForm()):
            self.assertEqual(form.fields["attachments"].widget.attrs["accept"], attachment_accept())
            self.assertIn("Maximum file size", str(form.fields["attachments"].help_text))

    def test_accept_hint_comes_from_configured_mime_types(self):
        with patch("conformity.validators.config.ATTACHMENT_ALLOWED_MIME_TYPES", "image/png, application/pdf"):
            self.assertEqual(attachment_accept(), "application/pdf,image/png")
