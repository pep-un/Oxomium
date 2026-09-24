FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y libmagic1 \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system app \
    && adduser --system --ingroup app app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools \
    && pip install --no-cache-dir -r requirements.txt \
    && python -m pip uninstall --yes msgpack setuptools \
    && find /usr/local/lib/python3.12/site-packages -maxdepth 1 -type d \
        \( -name 'msgpack*' -o -name 'setuptools*' -o -name 'wheel*' \) \
        -exec rm -rf {} + \
    && python -m pip install --no-cache-dir --force-reinstall \
        'setuptools==84.0.0' \
        'msgpack==1.2.1' \
        'wheel==0.46.2' \
    && pip check

COPY --chown=app:app . .
COPY docker/scripts/entrypoint.sh /usr/local/bin/entrypoint
RUN chmod +x /usr/local/bin/entrypoint

USER app

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/entrypoint"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "oxomium.wsgi:application"]
