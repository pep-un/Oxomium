#!/bin/sh
until nc -vz $1 $2; do echo "Waiting for MySQL $1:$2..."; sleep 3; done;

python /app/manage.py migrate
python /app/manage.py collectstatic --clear --no-input
python /app/manage.py loaddata /app/dashboard/fixtures/os.yaml
python /app/manage.py createsuperuser --noinput --username admin --email test@example.com
service nginx start
gunicorn updatesdashboard.wsgi:application

exec "$@"
