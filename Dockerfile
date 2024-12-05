FROM python:3.11-alpine

# Setup running as non root user
RUN addgroup nonroot && \
    adduser --system -G nonroot --disabled-password nonroot && \
    apk add --no-cache gosu --repository https://dl-cdn.alpinelinux.org/alpine/edge/testing/

WORKDIR /app

# Setup entrypoint
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

# Install dependencies
COPY requirements.lock ./
RUN PYTHONDONTWRITEBYTECODE=1 pip install --no-cache-dir -r requirements.lock

COPY somnus/ somnus/

VOLUME [ "/app/data" ]

ENTRYPOINT "./docker-entrypoint.sh"