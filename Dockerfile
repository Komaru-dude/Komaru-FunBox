# Сборка
FROM python:3.12-alpine AS builder

RUN apk add --no-cache gcc musl-dev linux-headers g++ libffi-dev openssl-dev postgresql-dev ffmpeg

WORKDIR /build
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels -r requirements.txt

# Финал
FROM python:3.12-alpine

ARG APP_DIR=/opt/Komaru-FunBox
WORKDIR ${APP_DIR}

RUN apk add --no-cache ffmpeg curl git postgresql-client libmagic

COPY --from=builder /build/wheels /wheels
COPY --from=builder /build/requirements.txt .

RUN pip install --no-cache-dir /wheels/*

RUN curl -sL https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_linux -o /usr/local/bin/yt-dlp && chmod +x /usr/local/bin/yt-dlp

COPY . .

RUN chmod +x docker-entrypoint.sh force-pull.sh && sed -i 's/\r$//' docker-entrypoint.sh

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["python", "-u", "-m", "bot"]