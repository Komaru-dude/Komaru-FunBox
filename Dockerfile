# Сборка
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels -r requirements.txt

# Финал
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    git \
    libmagic1 \
    libpq5 \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

ARG APP_DIR=/opt/Komaru-FunBox
WORKDIR ${APP_DIR}

COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

RUN curl -sL https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_linux -o /usr/local/bin/yt-dlp && \
    chmod +x /usr/local/bin/yt-dlp

COPY . .

RUN chmod +x docker-entrypoint.sh force-pull.sh

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["python", "-u", "-m", "bot"]