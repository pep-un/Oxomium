# Docker with system Nginx

Use this setup when Nginx is already installed on the host. Oxomium runs in Docker and is bound only to `127.0.0.1:8001`.

Deployment templates:

- `deploy/docker/system-nginx.yaml`;
- `deploy/nginx/docker-system.conf`;
- `.env.example`.

## 1. Prepare the deployment

```shell
sudo mkdir -p /opt/oxomium-docker/{data,staticfiles}
cd /opt/oxomium-docker

sudo cp /path/to/Oxomium/deploy/docker/system-nginx.yaml compose.yaml
sudo cp /path/to/Oxomium/.env.example .env
sudo editor .env
```

Set an exact published release in `OXOMIUM_VERSION`. Also set `DEBUG=False`, a unique `SECRET_KEY`, and the public hostname in `ALLOWED_HOSTS`.

Ensure the bind-mounted `data` and `staticfiles` directories are writable by the non-root user used by the Oxomium image.

## 2. Start Oxomium

```shell
docker compose pull
docker compose up -d
docker compose ps
```

The image entrypoint runs migrations and `collectstatic` before Gunicorn starts.

## 3. Configure host Nginx

```shell
sudo cp /path/to/Oxomium/deploy/nginx/docker-system.conf /etc/nginx/sites-available/oxomium
sudo editor /etc/nginx/sites-available/oxomium
sudo ln -s /etc/nginx/sites-available/oxomium /etc/nginx/sites-enabled/oxomium
sudo nginx -t
sudo systemctl reload nginx
```

Replace the example hostname and configure TLS using the host certificate-management process. Nginx serves `/opt/oxomium-docker/staticfiles` and proxies application requests to `127.0.0.1:8001`.

## 4. Create an administrator

```shell
docker compose exec web python manage.py createsuperuser
```

## 5. Upgrade

Use the common [Upgrade Oxomium](../operations/upgrade.md) procedure. It includes backup, image update, validation, and rollback guidance.

## Diagnostics

```shell
docker compose ps
docker compose logs -f web
curl -I http://127.0.0.1:8001/
sudo nginx -t
```
