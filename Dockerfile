FROM nvidia/cuda:12.2.2-base-ubuntu22.04 

ENV DEBIAN_FRONTEND=noninteractive

# Add PostgreSQL repository for version 17
RUN apt-get update && apt-get install -y gnupg2 lsb-release wget && \
    echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list && \
    wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-dev \
        wget \
        dpkg \
        ca-certificates \
        fonts-liberation \
        build-essential \
        poppler-utils \
        tesseract-ocr \
        tesseract-ocr-rus \
        tesseract-ocr-eng \
        libgl1 \
        libsm6 \
        libxext6 \
        libxrender-dev \
        libreoffice \
        postgresql-client-17 \
        libfontconfig1 \
        libjpeg-turbo8 \
        libpng16-16 \
        libssl3 \
        libx11-6 \
        libxcb1 \
        libxrender1 \
        xfonts-75dpi \
        xfonts-base \
        git \
        cmake &&\
    ln -s /usr/bin/python3 /usr/bin/python && \
    apt-get purge -y postgresql-client-12 postgresql-client-13 postgresql-client-14 postgresql-client-15 postgresql-client-16 && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install wkhtmltopdf
RUN wget -q https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.jammy_amd64.deb && \
    dpkg -i wkhtmltox_0.12.6-1.jammy_amd64.deb || apt-get install -f -y && \
    rm -f wkhtmltox_0.12.6-1.jammy_amd64.deb

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy project files
COPY Data2.py .
COPY DS2plusTG.py .
COPY WorkWithDb/ ./WorkWithDb/
COPY app/ ./app/

# Create directories
RUN mkdir -p /app/data /app/output /app/logs

# Environment variables
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5.00/tessdata
ENV POPPLER_PATH=/usr/bin
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

CMD ["bash"]

# FROM ubuntu:22.04

# ENV DEBIAN_FRONTEND=noninteractive

# # Add PostgreSQL repository for version 17
# RUN apt-get update && apt-get install -y gnupg2 lsb-release wget && \
#     echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list && \
#     wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - && \
#     apt-get update && \
#     apt-get install -y --no-install-recommends \
#         python3 \
#         python3-pip \
#         python3-dev \
#         wget \
#         dpkg \
#         ca-certificates \
#         fonts-liberation \
#         build-essential \
#         poppler-utils \
#         tesseract-ocr \
#         tesseract-ocr-rus \
#         tesseract-ocr-eng \
#         libgl1 \
#         libsm6 \
#         libxext6 \
#         libxrender-dev \
#         libreoffice \
#         postgresql-client-17 \
#         libfontconfig1 \
#         libjpeg-turbo8 \
#         libpng16-16 \
#         libssl3 \
#         libx11-6 \
#         libxcb1 \
#         libxrender1 \
#         xfonts-75dpi \
#         xfonts-base && \
#     ln -s /usr/bin/python3 /usr/bin/python && \
#     apt-get purge -y postgresql-client-12 postgresql-client-13 postgresql-client-14 postgresql-client-15 postgresql-client-16 && \
#     apt-get autoremove -y && \
#     apt-get clean && \
#     rm -rf /var/lib/apt/lists/*

# # Install wkhtmltopdf
# RUN wget -q https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.jammy_amd64.deb && \
#     dpkg -i wkhtmltox_0.12.6-1.jammy_amd64.deb || apt-get install -f -y && \
#     rm -f wkhtmltox_0.12.6-1.jammy_amd64.deb

# WORKDIR /app

# # Install Python dependencies
# COPY requirements.txt .
# RUN pip3 install --no-cache-dir -r requirements.txt

# # Copy project files
# COPY Data2.py .
# COPY DS1.py .
# COPY WorkWithDb/ ./WorkWithDb/
# COPY app/ ./app/

# # Create directories
# RUN mkdir -p /app/data /app/output /app/logs

# # Environment variables
# ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5.00/tessdata
# ENV POPPLER_PATH=/usr/bin
# ENV PYTHONUNBUFFERED=1
# ENV PYTHONPATH=/app

# CMD ["bash"]