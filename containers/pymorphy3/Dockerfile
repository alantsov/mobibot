# Minimal image to run pymorphy3 base form extraction
FROM python:3.11-slim

# Install dependencies
RUN python -m pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir pymorphy3 pymorphy3-dicts-ru \
    && rm -rf /root/.cache/pip

# Copy entrypoint
WORKDIR /app
COPY entrypoint.py /app/entrypoint.py

# Default entrypoint expects a single JSON argument
ENTRYPOINT ["python", "/app/entrypoint.py"]
