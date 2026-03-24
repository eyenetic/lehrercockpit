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

CMD ["python3", "server.py"]
