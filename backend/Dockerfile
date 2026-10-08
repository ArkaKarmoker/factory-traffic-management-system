FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies if required
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . /app/

EXPOSE 8000

# Production entrypoint runs migrations, seeds default data, and boots gunicorn
CMD ["sh", "-c", "python manage.py migrate && python manage.py seed_junction && gunicorn core.wsgi:application --bind 0.0.0.0:${PORT:-8000}"]
