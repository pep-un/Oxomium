"""Central attachment upload policy and content-based validation."""
import hashlib
import os
import tempfile
from pathlib import Path

from constance import config
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from magic import Magic

ATTACHMENT_MIME_CATEGORIES = {
    "images": {
        "label": "Images",
        "mimes": ("image/*",),
    },
    "pdf": {
        "label": "PDF",
        "mimes": ("application/pdf",),
    },
    "text_documents": {
        "label": "Text documents (DOC, DOCX, ODT)",
        "mimes": (
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.oasis.opendocument.text",
        ),
    },
    "spreadsheets": {
        "label": "Spreadsheets (XLS, XLSX, ODS, CSV)",
        "mimes": (
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.oasis.opendocument.spreadsheet",
            "text/csv",
        ),
    },
    "presentations": {
        "label": "Presentations (PPT, PPTX, ODP)",
        "mimes": (
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.oasis.opendocument.presentation",
        ),
    },
    "json": {
        "label": "JSON",
        "mimes": ("application/json", "text/json"),
    },
    "xml": {
        "label": "XML",
        "mimes": ("application/xml", "text/xml"),
    },
    "html": {
        "label": "HTML",
        "mimes": ("text/html", "application/xhtml+xml"),
    },
    "archives": {
        "label": "ZIP archives",
        "mimes": ("application/zip",),
    },
    "plain_text": {
        "label": "Plain text",
        "mimes": ("text/plain",),
    },
}

ATTACHMENT_MIME_CATEGORY_CHOICES = tuple(
    (key, value["label"]) for key, value in ATTACHMENT_MIME_CATEGORIES.items()
)

MIME_EXTENSIONS = {
    "application/pdf": {".pdf"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "text/plain": {".txt"},
    "text/csv": {".csv"},
    "application/zip": {".zip"},
    "application/msword": {".doc"},
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {".docx"},
    "application/vnd.oasis.opendocument.text": {".odt"},
    "application/vnd.ms-excel": {".xls"},
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {".xlsx"},
    "application/vnd.oasis.opendocument.spreadsheet": {".ods"},
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


def _parse_mime_list(value):
    return {
        item.strip().lower()
        for item in (value or "").split(",")
        if item.strip()
    }


def mime_category_details():
    """Return category labels and their exact MIME patterns for UI/help text."""
    return tuple(
        {
            "key": key,
            "label": value["label"],
            "mimes": value["mimes"],
        }
        for key, value in ATTACHMENT_MIME_CATEGORIES.items()
    )


def configured_mime_policy():
    """Return effective allow/deny MIME patterns. Deny always takes precedence."""
    categories = getattr(config, "ATTACHMENT_ALLOWED_CATEGORIES", ()) or ()
    allowed = set()
    for category in categories:
        category_config = ATTACHMENT_MIME_CATEGORIES.get(category)
        if category_config:
            allowed.update(category_config["mimes"])

    allowed.update(_parse_mime_list(getattr(config, "ATTACHMENT_ALLOWED_MIME_TYPES", "")))
    denied = _parse_mime_list(getattr(config, "ATTACHMENT_DENIED_MIME_TYPES", ""))
    return allowed, denied


def _matches_mime_pattern(mime_type, patterns):
    return any(
        mime_type == pattern
        or (pattern.endswith("/*") and mime_type.startswith(pattern[:-1]))
        for pattern in patterns
    )


def allowed_mime_types():
    """Compatibility helper returning configured allow patterns."""
    return configured_mime_policy()[0]


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
    allowed, denied = configured_mime_policy()
    if _matches_mime_pattern(detected, denied):
        raise ValidationError(
            _("Unsupported file type: %(mime)s."),
            code="attachment_mime_denied",
            params={"mime": detected},
        )
    if not _matches_mime_pattern(detected, allowed):
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
