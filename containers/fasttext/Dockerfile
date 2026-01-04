# FastText Language Identification Dockerfile
# CLI-style container similar to whisperx pattern
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FASTTEXT_MODEL_PATH=/models/lid.176.bin

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        g++ \
        make \
        libomp-dev \
        curl \
        python3-dev \
    && rm -rf /var/lib/apt/lists/*

RUN  pip install --no-cache-dir "pip<25" pybind11 setuptools wheel && \
     pip install --no-cache-dir --no-build-isolation "numpy<2.0" fasttext-wheel==0.9.2

RUN mkdir -p /models && \
    curl -L -o /models/lid.176.bin \
      https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin && \
    ls -lh /models

WORKDIR /app
COPY app.py /app/app.py

ENTRYPOINT ["python", "/app/app.py"]
