# ==============================================================================
# Dockerfile — Azure Functions (KB Ingestion Pipeline)
# ==============================================================================
# Custom container to support Playwright + Chromium for HTML→PDF rendering
# used by the Mistral Document AI converter (fn_convert_mistral).
# ==============================================================================

FROM mcr.microsoft.com/azure-functions/python:4-python3.11

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true

WORKDIR /home/site/wwwroot

# Copy everything
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir .

# Install Playwright Chromium with all required system libraries
RUN playwright install --with-deps chromium
