# syntax=docker/dockerfile:1.6
# ---------------------------------------------------------------------------
# Sahay — AI Welfare Navigator for Bharat
# Single-stage image. Runs on macOS, Windows, Linux via Docker / Docker Desktop.
# ---------------------------------------------------------------------------

FROM python:3.12-slim

# Don't write .pyc; flush stdout so logs appear in `docker logs` immediately.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SAHAY_HOST=0.0.0.0 \
    SAHAY_PORT=5000 \
    SAHAY_DEBUG=0

WORKDIR /app

# Install Python deps first (better layer caching — deps rarely change).
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the app.
COPY . .

EXPOSE 5000

# Tiny healthcheck so `docker ps` shows green and orchestrators know we're up.
HEALTHCHECK --interval=30s --timeout=4s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; \
      sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/api/schemes', timeout=3).status == 200 else 1)" \
  || exit 1

# Gunicorn for production. 2 workers handles the demo load comfortably.
# --timeout 60 because Claude API calls can take a few seconds.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", \
     "--workers", "2", \
     "--threads", "4", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "server:app"]
