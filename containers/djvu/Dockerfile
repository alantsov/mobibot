# Minimal ddjvu image based on Debian slim
FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       djvulibre-bin \
    && rm -rf /var/lib/apt/lists/*

# Use ddjvu as entrypoint to simplify wrapper code
ENTRYPOINT ["ddjvu"]
