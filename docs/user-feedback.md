# User feedback conventions

Oxomium uses Django's messages framework for feedback that must survive a redirect and renders relevant messages as Bootstrap alerts from the common application layout.

## Levels

- `SUCCESS`: not rendered as a global alert.
- `INFO` → `alert-info`: neutral contextual information.
- `WARNING` → `alert-warning`: the operation can continue, but the user should review something.
- `ERROR` → `alert-danger`: a recoverable operation-level error that needs attention.

Displayed alerts include an icon as a non-color cue and a manual close button. Error messages use alert semantics; other displayed feedback uses status semantics. Alerts are never removed automatically.

Field-specific validation errors stay attached to their form fields. Global error messages are reserved for recoverable operation-level failures that need additional visibility.
