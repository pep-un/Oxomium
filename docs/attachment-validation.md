# Attachment upload validation

Attachment uploads are validated server-side before persistence. The policy is centralized in `conformity/validators.py` and is enforced by the `Attachment` model as well as upload forms/views.

## Configuration

Django Constance exposes:

- `ATTACHMENT_ALLOWED_MIME_TYPES`: comma-separated MIME allowlist.
- `ATTACHMENT_MAX_SIZE_MB`: maximum size in MiB.

The default allowlist covers PDF, JPEG, PNG, plain text, CSV, ZIP, DOCX and XLSX files. Changing the browser `accept` attribute or an upload Content-Type header does not bypass server validation.

## MIME detection

Oxomium uses `python-magic` to inspect file content. The application container therefore requires the libmagic runtime library. The project Dockerfile installs Alpine's `libmagic` package before Python dependencies are installed.

Validation checks file size, content-detected MIME type, the configured allowlist, and the filename extension for known supported types. Invalid files raise a Django validation error before an `Attachment` is saved.
