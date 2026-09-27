# User feedback conventions

Oxomium uses Django's messages framework for feedback that must survive a redirect and renders selected messages as Bootstrap alerts from the common application layout.

## Configurable levels

The Constance backend exposes `FEEDBACK_ALERT_LEVELS` as checkboxes:

- `success`
- `info`
- `warning`
- `error`

The default configuration displays `INFO`, `WARNING`, and `ERROR`, while `SUCCESS` is disabled.

Administrators can change the displayed levels from the backend without redeploying the application.

## Rendering

- `SUCCESS` → `alert-success`
- `INFO` → `alert-info`
- `WARNING` → `alert-warning`
- `ERROR` → `alert-danger`

Displayed alerts include an icon as a non-color cue and a manual close button. Error messages use alert semantics; other displayed feedback uses status semantics. Alerts are never removed automatically.

Field-specific validation errors stay attached to their form fields. Global error messages are reserved for recoverable operation-level failures that need additional visibility.
