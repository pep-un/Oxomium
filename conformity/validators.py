"""Central attachment upload policy and content-based validation."""
from pathlib import Path

from constance import config
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from magic import Magic

MIME_EXTENSIONS = {
    "application/pdf": {".pdf"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "text/plain": {".txt"},
    "text/csv": {".csv"},
    "application/zip": {".zip"},
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {".docx"},
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {".xlsx"},
}


def allowed_mime_types():
    return {item.strip().lower() for item in config.ATTACHMENT_ALLOWED_MIME_TYPES.split(",") if item.strip()}


def attachment_accept():
    return ",".join(sorted(allowed_mime_types()))


def attachment_max_size_help():
    return _("Maximum file size: %(size)s MB.") % {"size": config.ATTACHMENT_MAX_SIZE_MB}


def detect_mime(uploaded_file):
    position = uploaded_file.tell()
    uploaded_file.seek(0)
    sample = uploaded_file.read(8192)
    uploaded_file.seek(position)
    return Magic(mime=True).from_buffer(sample).split(";", 1)[0].strip().lower()


def validate_attachment(uploaded_file):
    """Validate one upload against the configured allowlist before persistence."""
    max_bytes = config.ATTACHMENT_MAX_SIZE_MB * 1024 * 1024
    if uploaded_file.size > max_bytes:
        raise ValidationError(
            _("File exceeds the maximum allowed size of %(size)s MB."),
            code="attachment_too_large",
            params={"size": config.ATTACHMENT_MAX_SIZE_MB},
        )

    detected = detect_mime(uploaded_file)
    allowed = allowed_mime_types()
    if detected not in allowed:
        raise ValidationError(
            _("Unsupported file type: %(mime)s."),
            code="attachment_mime_not_allowed",
            params={"mime": detected},
        )

    extension = Path(uploaded_file.name).suffix.lower()
    expected_extensions = MIME_EXTENSIONS.get(detected)
    if expected_extensions and extension not in expected_extensions:
        raise ValidationError(
            _("File extension %(extension)s does not match detected type %(mime)s."),
            code="attachment_extension_mismatch",
            params={"extension": extension or _("(none)"), "mime": detected},
        )
    return detected
