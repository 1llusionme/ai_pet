FROM python:3.11-slim

WORKDIR /workspace/server

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MINDSHADOW_HOST=0.0.0.0
ENV MINDSHADOW_PORT=8080

COPY requirements.txt ./requirements.txt
COPY requirements-prod.txt ./requirements-prod.txt

RUN pip install --no-cache-dir -r ./requirements-prod.txt

COPY . .

RUN mkdir -p /workspace/data/uploads

EXPOSE 8080

CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
