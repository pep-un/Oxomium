### DEV ENV ###
FROM python:3.13.1-slim-bookworm AS app_dev

ARG APP_UID=1000
ARG APP_GID=1000

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app/

RUN apt update && apt install -y procps less netcat-traditional gcc nginx-light pkg-config python3-magic

COPY ./docker/nginx/oxomium.conf /etc/nginx/sites-enabled/oxomium.conf
RUN rm -f /etc/nginx/sites-enabled/default

RUN addgroup --system gunicorn --gid ${APP_GID} && adduser --uid ${APP_UID} --system --disabled-login --group gunicorn

RUN pip install --upgrade pip
COPY ./app/requirements.txt .
RUN pip install -r requirements.txt

COPY ./docker/scripts/entrypoint.dev.sh /usr/local/bin/entrypoint
RUN chmod +x /usr/local/bin/entrypoint

COPY ./app/ .
COPY ./app/env-exemple ./app/.env

RUN rm -f ./app/.env

ENTRYPOINT ["/usr/local/bin/entrypoint"]
