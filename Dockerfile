FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends smartmontools util-linux \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY scripts/docker-entrypoint.sh ./scripts/docker-entrypoint.sh

RUN pip install --no-cache-dir . \
    && chmod +x /app/scripts/docker-entrypoint.sh

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]