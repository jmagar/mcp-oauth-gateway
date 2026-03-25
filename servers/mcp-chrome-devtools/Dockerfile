FROM python:3.11-slim

WORKDIR /app

# Install curl for healthchecks and Node.js for npx
RUN apt-get update && apt-get install -y curl gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

COPY mcp-streamablehttp-proxy /tmp/mcp-streamablehttp-proxy
RUN pip install --no-cache-dir /tmp/mcp-streamablehttp-proxy && rm -rf /tmp/mcp-streamablehttp-proxy

RUN useradd -m -u 1000 proxyuser
USER proxyuser

EXPOSE 3000

CMD ["mcp-streamablehttp-proxy", "--host", "0.0.0.0", "--port", "3000", "--timeout", "3600", "npx", "-y", "chrome-devtools-mcp@latest", "--browserUrl=http://100.120.242.29:9222", "--remote-allow-origins=*"]
