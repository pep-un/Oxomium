# Dockerfile

FROM unit:python3.12

WORKDIR /app

COPY . /app/

RUN pip install --no-cache-dir -r requirements.txt \
    && python manage.py collectstatic --noinput\
    && python manage.py migrate

COPY unit.json /docker-entrypoint.d/

EXPOSE 8000

CMD ["unitd", "--no-daemon", "--control", "unix:/run/control.unit.sock"]