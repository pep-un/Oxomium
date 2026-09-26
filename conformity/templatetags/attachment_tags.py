"""Template helpers for consistent attachment presentation."""
from django import template

register = template.Library()

MIME_ICON_EXACT = {
    "application/pdf": "bi-file-earmark-pdf",
    "application/zip": "bi-file-earmark-zip",
    "application/x-7z-compressed": "bi-file-earmark-zip",
    "application/x-rar-compressed": "bi-file-earmark-zip",
    "application/vnd.rar": "bi-file-earmark-zip",
    "application/msword": "bi-file-earmark-word",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "bi-file-earmark-word",
    "application/vnd.oasis.opendocument.text": "bi-file-earmark-text",
    "application/vnd.ms-excel": "bi-file-earmark-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "bi-file-earmark-excel",
    "application/vnd.oasis.opendocument.spreadsheet": "bi-file-earmark-spreadsheet",
}

MIME_ICON_PREFIXES = {
    "image/": "bi-file-earmark-image",
    "text/": "bi-file-earmark-text",
}


@register.filter
def attachment_icon(mime_type):
    """Return the Bootstrap Icon class for a detected MIME type."""
    normalized = (mime_type or "").lower().split(";", 1)[0].strip()
    if normalized in MIME_ICON_EXACT:
        return MIME_ICON_EXACT[normalized]
    for prefix, icon in MIME_ICON_PREFIXES.items():
        if normalized.startswith(prefix):
            return icon
    return "bi-file-earmark"
