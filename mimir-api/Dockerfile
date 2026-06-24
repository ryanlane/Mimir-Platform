FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System runtime deps — cached independently of Python packages
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      git \
      ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Playwright browser in its own layer, isolated from the rest of requirements.
# Copying playwright-version.txt separately means changes to requirements.txt
# (other packages) don't re-download Chromium (~150 MB, ~5 min on arm64).
# This layer only busts when the playwright version pin itself changes.
COPY playwright-version.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r playwright-version.txt \
    && playwright install --with-deps chromium

# Install remaining Python dependencies
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create expected writable directories (bind/volumes can override)
RUN mkdir -p /var/lib/mimir-api \
    /var/opt/mimir/mimir-api/uploads \
    /var/opt/mimir/mimir-api/channels

EXPOSE 5000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5000"]
