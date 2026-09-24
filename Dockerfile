FROM python:3.14-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apk add --no-cache libmagic \
    && addgroup -S app \
    && adduser -S -G app app

COPY requirements.txt .
RUN python -m pip install --only-binary=:all: --no-cache-dir -r requirements.txt
&& rm -rf /usr/local/lib/python3.14/site-packages/pip \
    /usr/local/lib/python3.14/site-packages/pip-*.dist-info \
    /usr/local/lib/python3.14/site-packages/setuptools \
    /usr/local/lib/python3.14/site-packages/setuptools-*.dist-info \
    /usr/local/lib/python3.14/site-packages/wheel \
    /usr/local/lib/python3.14/site-packages/wheel-*.dist-info \
    /usr/local/bin/pip \
    /usr/local/bin/pip3 \
    /usr/local/bin/pip3.14

COPY --chown=app:app . .
COPY docker/scripts/entrypoint.sh /usr/local/bin/entrypoint
RUN mkdir -p /app/data /app/staticfiles \
    && chown -R app:app /app/data /app/staticfiles \
    && chmod +x /usr/local/bin/entrypoint

USER app

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/entrypoint"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "oxomium.wsgi:application"]
