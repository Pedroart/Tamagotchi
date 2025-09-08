# Dockerfile para Tamagotchi - Aplicación de Escritorio con Audio
FROM python:3.12-slim

# Instalar dependencias del sistema para audio, GUI y OpenCV
RUN apt-get update && apt-get install -y \
    # Audio system
    pulseaudio \
    alsa-utils \
    libasound2-dev \
    portaudio19-dev \
    # GUI dependencies
    libgl1-mesa-dri \
    libglib2.0-0 \
    libgtk-3-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libfontconfig1 \
    libice6 \
    # SDL for pygame
    libsdl2-dev \
    libsdl2-image-dev \
    libsdl2-mixer-dev \
    libsdl2-ttf-dev \
    # OpenCV dependencies
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgtk-3-0 \
    # Build tools
    build-essential \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar requirements primero para aprovechar cache de Docker
COPY backend/requirements.txt .
COPY backend/.env .

# Instalar solo dependencias necesarias para STT
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir \
    websockets==15.0.1 \
    faster-whisper==1.1.1 \
    soundfile==0.13.1 \
    numpy==1.26.4 \
    torch==2.7.1 \
    torchaudio==2.7.1

# Copiar el código fuente
COPY backend/ .

# Script simple para solo STT
RUN echo '#!/bin/bash\n\
echo "📡 Iniciando servidor STT..."\n\
echo "🎯 Puerto: 55000"\n\
echo "🌐 Accesible desde: ws://localhost:55000"\n\
python STT/audio_transform_RealTime.py\n\
' > /app/start.sh && chmod +x /app/start.sh

# Exponer solo puerto STT
EXPOSE 55000

# Comando por defecto
CMD ["/app/start.sh"]
