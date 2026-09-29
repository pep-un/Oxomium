# Demo environment deployment

Oxomium demo runs the latest published release in Docker and uses Nginx installed on the host as the HTTPS reverse proxy. Its deterministic demonstration data is reset every night.

## Architecture

A GitHub Release publishes `docker.io/pepun/oxomium:<version>`. The dedicated CD workflow targets the GitHub Environment `demo`, connects with a dedicated SSH key, deploys only the `web` container on loopback port 8001, then validates the public HTTPS URL. Host Nginx serves the shared static directory.

## Server bootstrap

Install Docker Engine with the Compose plugin and Nginx, then:

```shell
sudo mkdir -p /opt/oxomium-demo/{data,staticfiles}
sudo chown -R 100:101 /opt/oxomium-demo/data /opt/oxomium-demo/staticfiles
```

Copy `deploy/demo/compose.yaml`, copy `deploy/demo/env.example` to `/opt/oxomium-demo/.env`, and copy `reset-demo.sh` there with executable permissions. Set a unique `SECRET_KEY`, the real `ALLOWED_HOSTS`, and a demo password.

Install `deploy/demo/nginx.conf.example` in the existing host Nginx configuration, replace the hostname and integrate it with the existing TLS certificate configuration.

Install the reset service and timer under `/etc/systemd/system/`:

```shell
sudo systemctl daemon-reload
sudo systemctl enable --now oxomium-demo-reset.timer
```

## GitHub Environment

Create the GitHub Environment `demo`.

Secrets:
- `DEMO_SSH_PRIVATE_KEY`: dedicated deployment private key.
- `DEMO_SSH_KNOWN_HOSTS`: pinned server host-key entry.

Variables:
- `DEMO_HOST`
- `DEMO_SSH_USER`
- `DEMO_SSH_PORT` (normally 22)
- `DEMO_DEPLOY_PATH` (normally `/opt/oxomium-demo`)
- `DEMO_HEALTHCHECK_URL` (must be HTTPS)

The deployment user needs Docker Compose access in the deployment directory, but no write access to GitHub.

## Deployment and migrations

Publishing a release triggers `.github/workflows/deploy-demo.yml`. The immutable release version is derived from the `v<semver>` release tag. The server pulls that image and recreates the application. The image entrypoint runs migrations and `collectstatic` before Gunicorn starts. Startup or migration failure therefore fails the deployment before the HTTPS health check.

The workflow can also be started manually with an already published release tag.

## Demo data and nightly reset

Initialize/reset explicitly:

```shell
cd /opt/oxomium-demo
./reset-demo.sh
```

`reset_demo` requires `OXOMIUM_DEMO_INSTANCE=true`, supports SQLite only, refuses the normal development database path, deletes the dedicated demo database, migrates it and runs `seed_demo`. `seed_demo` refuses a non-empty database and requires `DEMO_PASSWORD`.

The systemd timer performs the same operation every night around 03:00, with a small randomized delay.

## Diagnostics

```shell
cd /opt/oxomium-demo
docker compose ps
docker compose logs -f web
systemctl list-timers oxomium-demo-reset.timer
journalctl -u oxomium-demo-reset.service
curl --fail http://127.0.0.1:8001/
```
