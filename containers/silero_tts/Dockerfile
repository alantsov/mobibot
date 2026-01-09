FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV OMP_NUM_THREADS=8
ENV MKL_NUM_THREADS=8

RUN apt-get update && apt-get install -y \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY tts_md_to_audio.py .

# Declare mount points
VOLUME ["/models", "/data"]

ENTRYPOINT ["python", "tts_md_to_audio.py"]
