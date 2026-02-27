# ---------------------------------------------------------------------------
# Dockerfile — KB Agent (Foundry hosted agent)
# ---------------------------------------------------------------------------
# Matches the Foundry hosted-agent reference layout exactly:
#   - User code lives under /app/user_agent/
#   - Dependencies installed to system Python via pip
#   - CMD starts the agent server (required — platform does NOT inject one)
#
# Reference: github.com/microsoft-foundry/foundry-samples/…/echo-agent/Dockerfile
# ---------------------------------------------------------------------------

FROM python:3.12-slim

WORKDIR /app

# Copy everything into the user_agent/ subdirectory (Foundry convention)
COPY . user_agent/

# Set working directory to user_agent
WORKDIR /app/user_agent

# Install dependencies from the locked requirements.txt
RUN if [ -f requirements.txt ]; then \
        pip install --no-cache-dir -r requirements.txt; \
    else \
        echo "No requirements.txt found"; \
    fi

EXPOSE 8088

CMD ["python", "main.py"]
