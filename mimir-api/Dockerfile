FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Runtime deps (keep minimal; add build-essential only if needed)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create expected writable directories (bind/volumes can override)
RUN mkdir -p /var/lib/mimir-api \
    /var/opt/mimir/mimir-api/uploads \
    /var/opt/mimir/mimir-api/channels

EXPOSE 5000

# Default: run API on 5000; override in compose if desired
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5000"]
