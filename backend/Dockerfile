FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

# System deps for the parser stack (scope §7.1):
#  - poppler-utils : pdf2image rasterisation
#  - ghostscript   : camelot table extraction
#  - libgl1/libglib: opencv (camelot / deskew)
#  - libreoffice   : legacy .doc/.ppt pre-conversion
RUN apt-get update && apt-get install -y --no-install-recommends \
        poppler-utils ghostscript libgl1 libglib2.0-0 libreoffice \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Playwright browser for web-link extraction (scope §3).
RUN python -m playwright install --with-deps chromium

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
