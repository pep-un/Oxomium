FROM python:3.14-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apk add --no-cache libmagic \
    && addgroup -S app \
    && adduser -S -G app app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app . .
COPY docker/scripts/entrypoint.sh /usr/local/bin/entrypoint
RUN chmod +x /usr/local/bin/entrypoint

USER app

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/entrypoint"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "oxomium.wsgi:application"]
