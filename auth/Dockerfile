FROM python:3.11-slim

WORKDIR /app

# Install system dependencies and uv
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh

ENV PATH="/root/.local/bin:$PATH"

# Copy dependency files first for layer caching
COPY mcp-oauth-dynamicclient/pyproject.toml /app/mcp-oauth-dynamicclient/pyproject.toml
COPY mcp-oauth-dynamicclient/src /app/mcp-oauth-dynamicclient/src

# Install dependencies with uv
RUN uv pip install --system \
    fastapi \
    "uvicorn[standard]" \
    authlib \
    httpx \
    redis \
    pydantic-settings \
    PyJWT \
    cryptography \
    python-multipart

# Create keys directory for RS256
RUN mkdir -p /app/keys

# Create non-root user
RUN useradd -m -u 1000 authuser && chown -R authuser:authuser /app

USER authuser

EXPOSE 8000

ENV PYTHONPATH=/app/mcp-oauth-dynamicclient/src:/app:${PYTHONPATH}

CMD ["python", "-m", "mcp_oauth_dynamicclient.cli", "--host", "0.0.0.0", "--port", "8000"]
