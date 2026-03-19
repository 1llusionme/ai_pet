import os

bind = f"0.0.0.0:{os.getenv('MINDSHADOW_PORT', '5001')}"
workers = int(os.getenv("MINDSHADOW_GUNICORN_WORKERS", "2"))
threads = int(os.getenv("MINDSHADOW_GUNICORN_THREADS", "4"))
timeout = int(os.getenv("MINDSHADOW_GUNICORN_TIMEOUT", "120"))
graceful_timeout = int(os.getenv("MINDSHADOW_GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("MINDSHADOW_GUNICORN_KEEPALIVE", "5"))
accesslog = "-"
errorlog = "-"
worker_class = "gthread"
