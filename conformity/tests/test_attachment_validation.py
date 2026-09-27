import hashlib
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from constance.test import override_config

from conformity.forms import AuditForm, OrganizationForm
from conformity.models import Attachment
from conformity.validators import attachment_accept, inspect_attachment, validate_attachment


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

    def test_upload_forms_expose_configured_accept_and_size_hint(self):
        for form in (AuditForm(), OrganizationForm()):
            self.assertEqual(form.fields["attachments"].widget.attrs["accept"], attachment_accept())
            self.assertIn("Maximum file size", str(form.fields["attachments"].help_text))

    def test_accept_hint_comes_from_configured_mime_types(self):
        with override_config(ATTACHMENT_ALLOWED_MIME_TYPES="image/png, application/pdf"):
            self.assertEqual(attachment_accept(), "application/pdf,image/png")
