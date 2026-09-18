# Dockerfile — dev/demo image for OportunizaVaga (Linux containers / WSL2).
# Base: Node 22 on Debian bookworm with bash, git, python3 and the minimal
# system libs Playwright/Chromium needs. The bot itself runs on the HOST
# (it drives YOUR real Chrome over CDP :9222), so this image is for editing,
# validating and previewing the optional monitor/ dashboard with sample data.
# Build:  docker build -t oportunizavaga .
# Demo:   docker compose up monitor   (see docker-compose.yml + monitor/README.md)
FROM node:22-bookworm

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    git \
    python3 \
    ca-certificates \
    libnss3 libnspr4 libatk1.0-0t64 libatk-bridge2.0-0 libcups2t64 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2t64 \
 && rm -rf /var/lib/apt/lists/*

# NOTE (example only — keep commented: opencode is heavy and host-specific,
# install it on the HOST per https://opencode.ai instead):
# RUN npm install -g opencode-ai

WORKDIR /work
CMD ["/bin/bash"]
