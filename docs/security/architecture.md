# Security architecture

This document summarizes security controls that are currently visible in the Oxomium codebase and deployment configuration. It is not a security certification or a substitute for a deployment-specific risk assessment.

## Authentication and access control

Oxomium uses Django's authentication framework.

Application class-based views in `conformity.views` are covered by a regression test requiring an authentication or authorization mixin:

- `LoginRequiredMixin`;
- `PermissionRequiredMixin`;
- `UserPassesTestMixin`.

This test is intended to detect accidental exposure of new class-based views without an authentication-related control.

The Django administration interface is exposed under `/django-backend/` and should only be available to appropriate administrative users.

## Password handling

Password storage and password validation are delegated to Django.

The current settings enable Django's standard password validators for:

- similarity to user attributes;
- minimum length;
- common passwords;
- numeric-only passwords.

Password hashing behavior follows the Django version and configuration used by the deployed application.

## CSRF, sessions, and browser-facing protections

The middleware stack includes Django's:

- `SecurityMiddleware`;
- `CsrfViewMiddleware`;
- `AuthenticationMiddleware`;
- `XFrameOptionsMiddleware`.

Production-oriented settings are configurable through environment variables, including:

- `SESSION_COOKIE_SECURE`;
- `SESSION_COOKIE_HTTPONLY`;
- `SESSION_COOKIE_SAMESITE`;
- `SESSION_COOKIE_NAME`;
- `CSRF_USE_SESSIONS`;
- `SECURE_SSL_REDIRECT`;
- `SECURE_HSTS_SECONDS`;
- `SECURE_HSTS_INCLUDE_SUBDOMAINS`;
- `SECURE_HSTS_PRELOAD`.

The repository's `.env.example` documents recommended values that must be reviewed for the actual deployment.

## Database access and input handling

Application database access is primarily implemented through Django models and the Django ORM.

Django forms and model validation provide part of the server-side input-validation layer. File attachments have additional content-based validation documented in [Attachment validation](../features/attachment-validation.md).

Security-sensitive validation must remain server-side; browser validation alone is not treated as a security boundary.

## File uploads

Attachment uploads are validated using content-detected MIME types through `python-magic`, configurable allow/deny rules, size limits, and known filename extensions.

See [Attachment validation](../features/attachment-validation.md) for the exact current behavior.

## Audit logging

Oxomium uses `django-auditlog`.

The audit middleware is enabled, application models are tracked, and Oxomium also contains explicit handling for business relations and bulk updates where ordinary model signals are not sufficient.

The application exposes an audit-log view and export functionality.

Audit logging should be treated as an application accountability feature, not as a replacement for host, reverse-proxy, authentication, or infrastructure logs.

## Reverse proxy and TLS

The deployment examples use Nginx.

The manual Linux Nginx template includes HTTPS configuration, HTTP-to-HTTPS redirection, and a Content-Security-Policy header. The generic container and Docker/system-Nginx examples require deployment-specific TLS configuration.

Do not expose the HTTP-only examples directly to the public Internet without an appropriate TLS termination layer.

## Dependency and supply-chain controls

Dependabot tracks:

- Python dependencies daily;
- GitHub Actions weekly.

Pull requests run dependency review as part of CI.

Release automation:

- builds the source archive from the released commit;
- builds the final Docker image;
- scans the image with Trivy for HIGH and CRITICAL vulnerabilities;
- generates CycloneDX SBOMs for both the source archive and Docker image;
- publishes SHA-256 checksums for release artifacts.

These controls reduce supply-chain risk but do not guarantee that a release is free of vulnerabilities.

## Deployment validation

Before exposing a production installation, run:

```shell
python manage.py check --deploy
```

using the same environment configuration as the production instance.

Review Django's deployment checklist as part of production hardening:

https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

## Security boundaries and future review

Security assumptions should be reviewed whenever authentication, authorization, externally supplied URLs, file handling, integrations, or network-facing services change.

The historical Wiki contained an OWASP Top 10 checklist with several TODO items. Those items were not copied here as current facts unless they could be verified in the present codebase. OWASP guidance remains useful as a review framework, but this document intentionally describes implemented controls rather than claiming compliance with an OWASP standard.
