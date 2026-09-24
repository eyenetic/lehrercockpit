FROM python:3.11-slim
# Flask + gunicorn WSGI stack (replaces ThreadingHTTPServer for Render compatibility)

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory for caches
RUN mkdir -p data

EXPOSE 8080

# Same start command as the Procfile (Render). server.py is the local-only
# stdlib server without the multi-user /api/v2 endpoints.
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-8080} --workers 1 --timeout 120"]
