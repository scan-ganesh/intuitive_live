# === Builder Stage ===
FROM python:3.12-slim-bookworm AS builder
WORKDIR /app

# Install build dependencies required for compiling some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fastest way)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Set UV environment variables
ENV UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Create a virtual environment to house all dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies using the cache mount
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install -r requirements.txt

# === Runtime Stage ===
FROM python:3.12-slim-bookworm
WORKDIR /app

# Copy the virtual environment from the builder
COPY --from=builder /opt/venv /opt/venv

# Ensure the runtime uses the virtual environment
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy your application code
COPY . .

# Cloud Run listens on 8080 by default
EXPOSE 8080

# Using uvicorn from the virtual environment
CMD ["uvicorn", "intuitive:app", "--host", "0.0.0.0", "--port", "8080"]
