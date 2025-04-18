FROM ubuntu:latest

# Установка системных зависимостей
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        wget \
        dpkg \
        ca-certificates \
        fonts-liberation \
        build-essential \
        python3-dev \
        python3-pip \
        poppler-utils \
        tesseract-ocr \
        tesseract-ocr-rus \
        tesseract-ocr-eng \
        libgl1 \
        libsm6 \
        libxext6 \
        libxrender-dev \
        libreoffice \
        postgresql-client \
        # WKHTMLTOPDF зависимости
        libfontconfig1 \
        libjpeg-turbo8 \
        libpng16-16 \
        libssl3 \
        libx11-6 \
        libxcb1 \
        libxext6 \
        libxrender1 \
        xfonts-75dpi \
        xfonts-base && \
    rm -rf /var/lib/apt/lists/*

# Скачивание WKHTMLTOPDF 
RUN wget -q https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.focal_amd64.deb && \
    apt-get update && \
    apt-get install -y --no-install-recommends ./wkhtmltox_0.12.6-1.focal_amd64.deb && \
    rm -f wkhtmltox_0.12.6-1.focal_amd64.deb

# Рабочая директория
WORKDIR /app

# Установка Python-зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY requirements.txt .
COPY Data2.py .
COPY DS1.py .
COPY WorkWithDb/ ./WorkWithDb/


COPY WorkWithDb/DumpFiles/ ./WorkWithDb/DumpFiles/


# Создаем папки для данных 
RUN mkdir -p /app/data /app/output /app/logs

# Настройка окружения
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata
ENV POPPLER_PATH=/usr/bin
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app



