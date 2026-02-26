# ---------------------------------------------------------------------------
# Dockerfile — KB Agent (FastAPI + uvicorn)
# ---------------------------------------------------------------------------
# Python 3.11 + UV for dependency management.
# Runs the agent server on port 8088.
# ---------------------------------------------------------------------------

FROM python:3.11-slim

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock .python-version ./

# Install dependencies (production only)
RUN uv sync --no-dev --frozen

# Copy application code
COPY main.py ./
COPY agent/ ./agent/

# Expose the server port
EXPOSE 8088

# Run the agent server
CMD ["uv", "run", "python", "main.py"]
