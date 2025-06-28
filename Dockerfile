# Dockerfile

FROM python:3.9

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt
    && pip install --no-cache-dir gunicorn
    && python manage.py migrate

EXPOSE 8000

CMD ["gunicorn", "Oxomium.wsgi:conformity", "--bind", "0.0.0.0:8000"]
