# ─────────────────────────────────────────────────────────────────────────────
# ChessEcon Backend — GPU Docker image (OpenEnv 0.1 compliant)
# ─────────────────────────────────────────────────────────────────────────────

FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-dev python3-pip git curl \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 \
 && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
 && update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1

# Install deps from requirements.txt before copying the full source
# so this layer is cached independently of code changes.
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir torch==2.4.1 --index-url https://download.pytorch.org/whl/cu121 \
 && pip install --no-cache-dir -r requirements.txt

# Copy source into /backend so "from backend.X" resolves correctly.
# PYTHONPATH=/ means Python sees /backend as the top-level package.
COPY . /backend

WORKDIR /backend

# / on PYTHONPATH → "import backend" resolves to /backend
ENV PYTHONPATH=/

ENV HF_HOME=/root/.cache/huggingface
ENV TRANSFORMERS_CACHE=/root/.cache/huggingface
ENV HF_HUB_OFFLINE=0

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "websocket_server.py"]
