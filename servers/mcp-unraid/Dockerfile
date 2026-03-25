FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl openssh-client && rm -rf /var/lib/apt/lists/*

COPY mcp-streamablehttp-proxy /tmp/mcp-streamablehttp-proxy
RUN pip install --no-cache-dir /tmp/mcp-streamablehttp-proxy && rm -rf /tmp/mcp-streamablehttp-proxy

RUN useradd -m -u 1000 proxyuser && mkdir -p /home/proxyuser/.ssh && chown -R proxyuser:proxyuser /home/proxyuser

USER proxyuser

EXPOSE 3000

CMD ["mcp-streamablehttp-proxy", "--host", "0.0.0.0", "--port", "3000", "--timeout", "3600", "ssh", "-o", "StrictHostKeyChecking=accept-new", "-o", "ControlMaster=no", "-o", "BatchMode=yes", "-o", "SendEnv=UNRAID_MCP_TRANSPORT", "jmagar@dookie", "env", "UNRAID_MCP_TRANSPORT=stdio", "uv", "run", "--directory", "/home/jmagar/workspace/unraid-mcp", "unraid-mcp"]
