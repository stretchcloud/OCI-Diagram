FROM python:3.12-slim

# Install Chrome dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg2 ca-certificates \
    fonts-liberation libasound2 libatk-bridge2.0-0 libatk1.0-0 \
    libcups2 libdbus-1-3 libdrm2 libgbm1 libgtk-3-0 \
    libnspr4 libnss3 libxcomposite1 libxdamage1 libxrandr2 \
    libxss1 xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome
RUN wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && dpkg -i /tmp/chrome.deb || apt-get install -f -y \
    && rm /tmp/chrome.deb

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY src/ src/
COPY config/ config/

RUN mkdir -p data

VOLUME ["/app/data", "/app/config"]

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import sqlite3; c=sqlite3.connect('data/vfs_monitor.db'); c.execute('SELECT 1'); print('ok')"

CMD ["python", "-m", "vfs_monitor"]
