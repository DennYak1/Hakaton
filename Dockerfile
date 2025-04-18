# Базовый образ с поддержкой GPU (удалите строку ниже если GPU не требуется)
FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

# Установка системных зависимостей
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    python3-pip \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-rus \
    libgl1 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libreoffice \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Установка Poppler
RUN wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.focal_amd64.deb && \
    dpkg -i wkhtmltox_0.12.6-1.focal_amd64.deb && \
    apt-get install -f

# Рабочая директория
WORKDIR /app

# Копируем зависимости первыми для кэширования
COPY requirements.txt .

# Установка Python-зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY DS1.py Data2.py "Model1 для отладки.py" data.json ./

# Настройка окружения
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata
ENV POPPLER_PATH=/usr/bin
ENV PYTHONUNBUFFERED=1

# Точка входа (можно переопределить в docker-compose)
CMD ["python", "DS1.py"]
