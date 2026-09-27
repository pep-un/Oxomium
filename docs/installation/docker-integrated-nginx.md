# Docker with integrated Nginx

This setup runs Oxomium and Nginx in Docker.

Deployment templates:

- `deploy/docker/integrated-nginx.yaml`;
- `deploy/nginx/container.conf`;
- `.env.example`.

## 1. Prepare the deployment

```shell
sudo mkdir -p /opt/oxomium-compose
cd /opt/oxomium-compose

sudo cp /path/to/Oxomium/deploy/docker/integrated-nginx.yaml compose.yaml
sudo cp /path/to/Oxomium/deploy/nginx/container.conf nginx.conf
sudo cp /path/to/Oxomium/.env.example .env
sudo editor .env
```

Set an exact published release in `OXOMIUM_VERSION`. Also set `DEBUG=False`, a unique `SECRET_KEY`, and the public hostname in `ALLOWED_HOSTS`.

## 2. Start the stack

```shell
docker compose pull
docker compose up -d
docker compose ps
```

The Oxomium image entrypoint runs migrations and `collectstatic`. Nginx waits for the application health check and serves the shared static volume.

## 3. Create an administrator

```shell
docker compose exec web python manage.py createsuperuser
```

## 4. HTTPS

The supplied container Nginx template listens on HTTP. For a public production deployment, terminate TLS in front of the stack or adapt the Nginx container configuration and mount the certificate and private key read-only.

## 5. Upgrade

Back up the `dbdata` volume, change `OXOMIUM_VERSION`, then run:

```shell
docker compose pull
docker compose up -d
```

## Diagnostics

```shell
docker compose ps
docker compose logs -f web
docker compose logs -f nginx
```
