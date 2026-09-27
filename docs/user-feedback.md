# User feedback conventions

Oxomium uses Django's messages framework for feedback that must survive a redirect and renders those messages as Bootstrap alerts from the common application layout.

## Levels

- `SUCCESS` → `alert-success`: a requested operation completed successfully.
- `INFO` → `alert-info`: neutral contextual information.
- `WARNING` → `alert-warning`: the operation can continue, but the user should review something.
- `ERROR` → `alert-danger`: a recoverable operation-level error that needs attention.

Alerts include an icon as a non-color cue. Error messages use alert semantics; non-error feedback uses status semantics. Alerts are not dismissible by default so important feedback is not accidentally hidden.

## Wording

Successful form operations use concise past-tense wording:

- `<Object type> created successfully.`
- `<Object type> updated successfully.`

Field-specific validation errors stay attached to their form fields and must not be duplicated as global messages. Global error messages are reserved for recoverable operation-level failures that are not attributable to one field.
