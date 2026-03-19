FROM python:3.11-slim

WORKDIR /workspace

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MINDSHADOW_HOST=0.0.0.0
ENV MINDSHADOW_PORT=8080

COPY server/requirements.txt /workspace/server/requirements.txt
COPY server/requirements-prod.txt /workspace/server/requirements-prod.txt

RUN pip install --no-cache-dir -r /workspace/server/requirements-prod.txt

COPY server /workspace/server

RUN mkdir -p /workspace/data/uploads

EXPOSE 8080

CMD ["gunicorn", "-c", "server/gunicorn.conf.py", "server.wsgi:app"]
