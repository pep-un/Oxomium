#!/bin/sh

python /app/manage.py migrate
python /app/manage.py collectstatic --clear --no-input
service nginx start
gunicorn oxomium.wsgi:application

exec "$@"
