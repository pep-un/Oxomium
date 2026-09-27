# Installation

Oxomium supports three deployment patterns. Choose the one that best matches the host environment.

| Deployment | Application | Reverse proxy | Guide |
| --- | --- | --- | --- |
| Manual Linux | Python virtual environment + Gunicorn | System Nginx | [Manual Linux](manual-linux.md) |
| Docker + system Nginx | Published Oxomium image | Nginx on the host | [Docker with system Nginx](docker-system-nginx.md) |
| Docker + integrated Nginx | Published Oxomium image | Nginx container | [Docker with integrated Nginx](docker-integrated-nginx.md) |

## Production requirements

For production deployments:

- use an explicit Oxomium release tag;
- set `DEBUG=False`;
- generate a unique `SECRET_KEY`;
- configure `ALLOWED_HOSTS`;
- configure HTTPS before exposing the application publicly;
- back up the SQLite database before upgrades.

The reusable deployment resources live under `deploy/`, grouped by technology:

```text
deploy/
├── docker/
├── nginx/
└── systemd/
```

The environment template is `.env.example`.


## After installation

Continue with the [Quick start](../getting-started/quick-start.md) to create an organization and load or import a framework.

For production hardening, review [Security architecture](../security/architecture.md) and run Django's deployment checks with the production configuration.

For later maintenance, use the common [Upgrade Oxomium](../operations/upgrade.md) procedure.
