#!/bin/sh

python /app/manage.py migrate
python /app/manage.py collectstatic
#python /app/manage.py createsuperuser --noinput --username admin --email test@example.com
service nginx start
gunicorn oxomium.wsgi:application

exec "$@"
