FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md .
COPY src ./src
COPY docs ./docs

RUN pip install --no-cache-dir .[docs]

ENTRYPOINT ["envkeep"]
