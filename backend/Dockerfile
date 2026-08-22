FROM python:3.12.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && addgroup --system sqlrefine \
    && adduser --system --ingroup sqlrefine sqlrefine

COPY . .
USER sqlrefine
EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/ready', timeout=2)"

# One worker is intentional: credentials are stored in this process's expiring memory.
CMD ["gunicorn", "--workers=1", "--threads=4", "--timeout=45", "--bind=0.0.0.0:5000", "app:app"]

