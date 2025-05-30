######################################################################
# Azure Functions - Python - Playwright container
######################################################################
FROM mcr.microsoft.com/azure-functions/python:4-python3.12

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/home/pw-browsers

# ─── 1️⃣  OS libs for Chromium ───────────────────────────────────────
USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        libnss3 libatk-bridge2.0-0 libatk1.0-0 \
        libcups2 libxss1 libdrm2 libgbm1 \
        libgtk-3-0 libasound2 libx11-xcb1 \
        libxcb1 libxcomposite1 libxdamage1 libxrandr2 \
        xdg-utils fonts-liberation && \
    rm -rf /var/lib/apt/lists/*

# ─── 2️⃣  Python deps (add setuptools!) ───────────────────────────────
COPY requirements.txt /
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r /requirements.txt && \
    pip install --no-cache-dir setuptools

# ─── 3️⃣  Download Chromium once at build time ───────────────────────
RUN python -m playwright install chromium && \
    python -m playwright install-deps chromium

# ─── 4️⃣  Copy your functions code ───────────────────────────────────
COPY . /home/site/wwwroot
WORKDIR /home/site/wwwroot

# ─── 5️⃣  ⚠️ Keep running as **root** in local dev so port-80 bind works
#          In production you can switch back to www-data if you prefer.
# USER www-data

CMD ["bash"]
