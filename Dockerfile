FROM python:3.13-slim

# System dependencies:
#   libpq-dev + gcc      → psycopg2-binary
#   postgresql-client    → pg_isready used in the entrypoint health-wait
#   gettext              → django compilemessages (Slovak / English translations)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    postgresql-client \
    gettext \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies before copying the full project
# so changes to source code don't invalidate this layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project source
COPY . .

# Pre-create directories that are mounted as volumes or written to at runtime.
# Docker will use the bind-mount paths on the host; these just ensure they exist
# inside the image as a fallback.
RUN mkdir -p /app/models /app/django_cache /app/staticfiles /app/locale

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]
