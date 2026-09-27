# Upgrade Oxomium

Use this procedure as a general upgrade checklist. Always read the release notes for the target version before upgrading.

## Before the upgrade

1. Identify the exact target release.
2. Back up the database and any persistent application data.
3. Make sure the backup can be restored.
4. Record the currently deployed version and configuration.
5. Schedule enough time to validate the application after migrations.

For the default SQLite setup, back up the database file before running migrations.

## Manual Linux installation

Stop the application service before changing the installed code:

```shell
sudo systemctl stop oxomium.service
cd /srv/web/Oxomium
sudo git fetch --tags
sudo git checkout <release-tag>
```

Update Python dependencies:

```shell
sudo .venv/bin/python -m pip install --upgrade pip
sudo .venv/bin/python -m pip install -r requirements.txt
```

Preview and apply database migrations:

```shell
sudo -u www-data .venv/bin/python manage.py check
sudo -u www-data .venv/bin/python manage.py migrate --plan
sudo -u www-data .venv/bin/python manage.py migrate --no-input
```

Refresh static files:

```shell
sudo -u www-data .venv/bin/python manage.py collectstatic --no-input
```

Then start the service again:

```shell
sudo systemctl start oxomium.service
sudo systemctl status oxomium.service
```

## Docker deployment

Back up the persistent database data or volume first.

Set `OXOMIUM_VERSION` in the deployment `.env` file to the exact target release, then update the stack:

```shell
docker compose pull
docker compose up -d
docker compose ps
```

The Oxomium container entrypoint runs migrations and `collectstatic` before starting Gunicorn.

## Production checks

Run Django's deployment checks using the same production configuration as the deployed application:

```shell
python manage.py check --deploy
```

For Docker:

```shell
docker compose exec web python manage.py check --deploy
```

Investigate warnings rather than suppressing them without understanding their impact.

Also verify:

- the application responds through the expected public URL;
- authentication works;
- static assets load;
- the application and reverse-proxy logs contain no new errors;
- expected data is present after the migration.

For manual deployments:

```shell
sudo journalctl -u oxomium.service -n 100
sudo nginx -t
```

For Docker deployments:

```shell
docker compose ps
docker compose logs --tail=100 web
```

## Rollback considerations

Application code can usually be returned to an earlier release, but database migrations may not always be safely reversible.

Do not rely on a code rollback as the only recovery plan. Keep a tested database backup from immediately before the upgrade.
