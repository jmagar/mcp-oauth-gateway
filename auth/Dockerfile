FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv via pip for reproducible builds (pinned version, no curl | sh)
RUN pip install --no-cache-dir uv==0.5.29

ENV PATH="/root/.local/bin:$PATH"

# Copy pyproject.toml first for layer caching — deps only reinstall if this changes
COPY mcp-oauth-dynamicclient/pyproject.toml /app/mcp-oauth-dynamicclient/pyproject.toml

# Install dependencies with uv (cached unless pyproject.toml changes)
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

# Copy source after installing deps — code changes don't invalidate the install cache
COPY mcp-oauth-dynamicclient/src /app/mcp-oauth-dynamicclient/src

# Create keys directory for RS256
RUN mkdir -p /app/keys

# Create non-root user
RUN useradd -m -u 1000 authuser && chown -R authuser:authuser /app

USER authuser

EXPOSE 8000

ENV PYTHONPATH=/app/mcp-oauth-dynamicclient/src:/app:${PYTHONPATH}

CMD ["python", "-m", "mcp_oauth_dynamicclient.cli", "--host", "0.0.0.0", "--port", "8000"]
