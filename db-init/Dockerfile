FROM python:3.11-slim
WORKDIR /app

# Install libpq for psycopg2 and pg_isready
RUN apt-get update \
	&& apt-get install -y --no-install-recommends postgresql-client gcc libpq-dev build-essential \
	&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . /app

# Place entrypoint
COPY db-init/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
