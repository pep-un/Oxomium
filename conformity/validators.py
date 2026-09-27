"""Central attachment upload policy and content-based validation."""
import hashlib
import os
import tempfile
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
    "application/json": {".json"},
    "text/json": {".json"},
    "application/xml": {".xml"},
    "text/xml": {".xml"},
    "text/html": {".html", ".htm"},
    "application/xhtml+xml": {".xhtml", ".html", ".htm"},
    "application/vnd.ms-powerpoint": {".ppt"},
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": {".pptx"},
    "application/vnd.oasis.opendocument.presentation": {".odp"},
}


def allowed_mime_types():
    return {item.strip().lower() for item in config.ATTACHMENT_ALLOWED_MIME_TYPES.split(",") if item.strip()}


def attachment_accept():
    return ",".join(sorted(allowed_mime_types()))


def attachment_max_size_help():
    return _("Maximum file size: %(size)s MB.") % {"size": config.ATTACHMENT_MAX_SIZE_MB}


def inspect_attachment(uploaded_file):
    """Return detected MIME type and SHA-256 using a temporary on-disk copy."""
    position = uploaded_file.tell()
    uploaded_file.seek(0)
    digest = hashlib.sha256()
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False) as temporary:
            temp_path = temporary.name
            for chunk in uploaded_file.chunks():
                digest.update(chunk)
                temporary.write(chunk)

        detected = Magic(mime=True).from_file(temp_path).split(";", 1)[0].strip().lower()
        return detected, digest.hexdigest()
    finally:
        uploaded_file.seek(position)
        if temp_path:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass


def detect_mime(uploaded_file):
    return inspect_attachment(uploaded_file)[0]


def calculate_sha256(uploaded_file):
    return inspect_attachment(uploaded_file)[1]


def validate_attachment(uploaded_file):
    """Validate one upload and return its detected MIME type and SHA-256."""
    max_bytes = config.ATTACHMENT_MAX_SIZE_MB * 1024 * 1024
    if uploaded_file.size > max_bytes:
        raise ValidationError(
            _("File exceeds the maximum allowed size of %(size)s MB."),
            code="attachment_too_large",
            params={"size": config.ATTACHMENT_MAX_SIZE_MB},
        )

    detected, checksum = inspect_attachment(uploaded_file)
    allowed = allowed_mime_types()
    allowed_by_prefix = any(
        item.endswith("/*") and detected.startswith(item[:-1])
        for item in allowed
    )
    if detected not in allowed and not allowed_by_prefix:
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
    return detected, checksum
