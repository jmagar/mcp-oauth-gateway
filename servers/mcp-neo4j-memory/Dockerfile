FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY mcp-streamablehttp-proxy /tmp/mcp-streamablehttp-proxy
RUN pip install --no-cache-dir /tmp/mcp-streamablehttp-proxy && rm -rf /tmp/mcp-streamablehttp-proxy

# Install uv for uvx support
RUN pip install --no-cache-dir uv

RUN useradd -m -u 1000 proxyuser
USER proxyuser

EXPOSE 3000

CMD ["mcp-streamablehttp-proxy", "--host", "0.0.0.0", "--port", "3000", "--timeout", "3600", "uvx", "mcp-neo4j-memory"]
