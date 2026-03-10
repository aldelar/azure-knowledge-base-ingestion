# ---------------------------------------------------------------------------
# Dockerfile — KB Agent (Azure Container App)
# ---------------------------------------------------------------------------
FROM python:3.12-slim

WORKDIR /app

# Install dependencies from the locked requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

EXPOSE 8088

CMD ["python", "main.py"]
