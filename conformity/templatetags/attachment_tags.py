"""Template helpers for consistent attachment presentation."""
from django import template

register = template.Library()

MIME_ICON_EXACT = {
    "application/pdf": "bi-file-earmark-pdf",

    # Structured/text formats with dedicated Bootstrap filetype icons.
    "application/json": "bi-filetype-json",
    "text/json": "bi-filetype-json",
    "application/xml": "bi-filetype-xml",
    "text/xml": "bi-filetype-xml",
    "text/html": "bi-filetype-html",
    "application/xhtml+xml": "bi-filetype-html",

    # Archives.
    "application/zip": "bi-file-earmark-zip",
    "application/x-7z-compressed": "bi-file-earmark-zip",
    "application/x-rar-compressed": "bi-file-earmark-zip",
    "application/vnd.rar": "bi-file-earmark-zip",
    "application/gzip": "bi-file-earmark-zip",
    "application/x-gzip": "bi-file-earmark-zip",
    "application/x-tar": "bi-file-earmark-zip",

    # Microsoft Office and LibreOffice/OpenDocument text documents.
    "application/msword": "bi-file-earmark-text",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "bi-file-earmark-text",
    "application/vnd.ms-word.document.macroenabled.12": "bi-file-earmark-text",
    "application/vnd.oasis.opendocument.text": "bi-file-earmark-text",
    "application/rtf": "bi-file-earmark-text",
    "text/rtf": "bi-file-earmark-text",

    # Microsoft Office and LibreOffice/OpenDocument spreadsheets.
    "application/vnd.ms-excel": "bi-file-earmark-spreadsheet",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "bi-file-earmark-spreadsheet",
    "application/vnd.ms-excel.sheet.macroenabled.12": "bi-file-earmark-spreadsheet",
    "application/vnd.ms-excel.sheet.binary.macroenabled.12": "bi-file-earmark-spreadsheet",
    "application/vnd.oasis.opendocument.spreadsheet": "bi-file-earmark-spreadsheet",
    "text/csv": "bi-file-earmark-spreadsheet",
    "application/csv": "bi-file-earmark-spreadsheet",

    # Microsoft Office and LibreOffice/OpenDocument presentations.
    "application/vnd.ms-powerpoint": "bi-file-earmark-slides",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "bi-file-earmark-slides",
    "application/vnd.ms-powerpoint.presentation.macroenabled.12": "bi-file-earmark-slides",
    "application/vnd.oasis.opendocument.presentation": "bi-file-earmark-slides",
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
