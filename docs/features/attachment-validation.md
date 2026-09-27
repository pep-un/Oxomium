# Attachment upload validation

Attachment uploads are validated server-side before persistence. The policy is centralized in `conformity/validators.py` and is enforced by the `Attachment` model as well as upload forms/views.

## Configuration

Django Constance exposes:

- `ATTACHMENT_ALLOWED_CATEGORIES`: multiple-choice categories shown as checkboxes.
- `ATTACHMENT_ALLOWED_MIME_TYPES`: additional comma-separated MIME allowlist. Wildcards such as `image/*` are supported.
- `ATTACHMENT_DENIED_MIME_TYPES`: comma-separated MIME denylist.
- `ATTACHMENT_MAX_SIZE_MB`: maximum size in MiB.

The denylist has precedence over both the selected categories and the manual allowlist.

### Category MIME mappings

The category selector stays compact in Constance. The exact MIME patterns are defined centrally in `conformity.validators.ATTACHMENT_MIME_CATEGORIES` and can be exposed through `mime_category_details()`.

Current defaults:

- Images: `image/*`
- PDF: `application/pdf`
- Text documents: `application/msword`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `application/vnd.oasis.opendocument.text`
- Spreadsheets: `application/vnd.ms-excel`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, `application/vnd.oasis.opendocument.spreadsheet`, `text/csv`
- Presentations: `application/vnd.ms-powerpoint`, `application/vnd.openxmlformats-officedocument.presentationml.presentation`, `application/vnd.oasis.opendocument.presentation`
- JSON: `application/json`, `text/json`
- XML: `application/xml`, `text/xml`
- HTML: `text/html`, `application/xhtml+xml`
- ZIP archives: `application/zip`
- Plain text: `text/plain`

Changing the browser `accept` attribute or an upload Content-Type header does not bypass server validation.

## MIME detection

Oxomium uses `python-magic` to inspect file content. The application container therefore requires the libmagic runtime library. The project Dockerfile installs Alpine's `libmagic` package before Python dependencies are installed.

Validation checks file size, content-detected MIME type, the configured policy, and the filename extension for known supported types. Invalid files raise a Django validation error before an `Attachment` is saved.
