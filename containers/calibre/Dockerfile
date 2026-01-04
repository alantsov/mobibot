FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    calibre \
    && rm -rf /var/lib/apt/lists/*

CMD ["bash"]