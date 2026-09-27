# Manual Linux installation

This setup runs Oxomium from a Python virtual environment, with Gunicorn managed by systemd and Nginx as the public reverse proxy.

The canonical deployment templates are:

- `deploy/systemd/oxomium.service`;
- `deploy/systemd/oxomium.socket`;
- `deploy/nginx/manual-linux.conf`.

## 1. Install system packages

On Debian or Ubuntu:

```shell
sudo apt update
sudo apt install -y python3 python3-venv python3-pip libmagic1 nginx git
```

## 2. Install Oxomium

The supplied systemd unit expects the application in `/srv/web/Oxomium`:

```shell
sudo mkdir -p /srv/web
sudo git clone https://github.com/pep-un/Oxomium.git /srv/web/Oxomium
cd /srv/web/Oxomium
sudo git checkout <release-tag>

sudo python3 -m venv .venv
sudo .venv/bin/pip install --upgrade pip
sudo .venv/bin/pip install -r requirements.txt
```

Use an exact release tag for reproducible upgrades.

## 3. Configure the environment

Create the runtime environment file from the repository template:

```shell
cd /srv/web/Oxomium
sudo cp .env.example .env
sudo editor .env
```

At minimum, set `DEBUG=False`, a unique `SECRET_KEY`, and the public hostname in `ALLOWED_HOSTS`.

For this layout, use:

```text
DB_NAME=data/db.sqlite3
STATIC_ROOT=/srv/web/Oxomium/static
```

Create the persistent directories and grant the service account access:

```shell
sudo mkdir -p /srv/web/Oxomium/data /srv/web/Oxomium/static
sudo chown -R www-data:www-data /srv/web/Oxomium
```

Generate a Django secret key with:

```shell
python3 scripts/generate_django_secret_key.py
```

## 4. Initialize Django

```shell
cd /srv/web/Oxomium
sudo -u www-data .venv/bin/python manage.py migrate --no-input
sudo -u www-data .venv/bin/python manage.py collectstatic --no-input
sudo -u www-data .venv/bin/python manage.py createsuperuser
```

## 5. Install the systemd units

```shell
sudo cp deploy/systemd/oxomium.service /etc/systemd/system/oxomium.service
sudo cp deploy/systemd/oxomium.socket /etc/systemd/system/oxomium.socket
sudo systemctl daemon-reload
sudo systemctl enable --now oxomium.socket oxomium.service
sudo systemctl status oxomium.service
```

Gunicorn is exposed through `/run/oxomium.sock`, which matches the supplied Nginx configuration.

## 6. Configure Nginx

```shell
sudo cp deploy/nginx/manual-linux.conf /etc/nginx/sites-available/oxomium
sudo editor /etc/nginx/sites-available/oxomium
sudo ln -s /etc/nginx/sites-available/oxomium /etc/nginx/sites-enabled/oxomium
sudo nginx -t
sudo systemctl reload nginx
```

Replace the example hostname and certificate paths with the real deployment values.

## 7. Upgrade

Back up `/srv/web/Oxomium/data/db.sqlite3`, then update to the required release:

```shell
sudo systemctl stop oxomium.service
cd /srv/web/Oxomium
sudo git fetch --tags
sudo git checkout <release-tag>
sudo .venv/bin/pip install -r requirements.txt
sudo -u www-data .venv/bin/python manage.py migrate --no-input
sudo -u www-data .venv/bin/python manage.py collectstatic --no-input
sudo systemctl start oxomium.service
```

## Diagnostics

```shell
sudo systemctl status oxomium.socket oxomium.service
sudo journalctl -u oxomium.service -f
sudo nginx -t
```
