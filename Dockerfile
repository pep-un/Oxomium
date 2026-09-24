FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    setuptools \
    && pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir --upgrade --force-reinstall \
    'setuptools>=78.1.1' \
    'msgpack>=1.2.1'

COPY . .
COPY docker/scripts/entrypoint.sh /usr/local/bin/entrypoint
RUN chmod +x /usr/local/bin/entrypoint

ENTRYPOINT ["/usr/local/bin/entrypoint"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "oxomium.wsgi:application"]
