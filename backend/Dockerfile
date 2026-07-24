FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

ARG PEPPI_PY_REF=feat/partial-read

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir uv

COPY pyproject.toml /app/pyproject.toml
RUN uv sync --no-dev --no-install-project \
    && uv pip install --python /opt/venv/bin/python --force-reinstall "https://github.com/agiera/peppi-py/archive/refs/heads/${PEPPI_PY_REF}.zip"

COPY . /app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
