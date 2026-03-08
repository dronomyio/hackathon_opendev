# ─────────────────────────────────────────────────────────────────────────────
# ChessEcon — Unified Multi-Stage Dockerfile
#
# Stages:
#   1. frontend-builder  — builds the React TypeScript dashboard (Node.js)
#   2. backend-cpu       — Python FastAPI backend, serves built frontend as static
#   3. backend-gpu       — same as backend-cpu but with CUDA PyTorch
#
# Usage:
#   CPU:  docker build --target backend-cpu -t chessecon:cpu .
#   GPU:  docker build --target backend-gpu -t chessecon:gpu .
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Build the React frontend ────────────────────────────────────────
FROM node:22-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy package files AND patches dir (required by pnpm for patched dependencies)
COPY frontend/package.json frontend/pnpm-lock.yaml* ./
COPY frontend/patches/ ./patches/
RUN npm install -g pnpm && pnpm install --frozen-lockfile

# Copy the full frontend source
COPY frontend/ ./

# Build the production bundle (frontend only — no Express server build)
# vite.config.ts outputs to dist/public/ relative to the project root
RUN pnpm build:docker

# ── Stage 2: CPU backend ──────────────────────────────────────────────────────
FROM python:3.11-slim AS backend-cpu

LABEL maintainer="ChessEcon Team"
LABEL description="ChessEcon — Multi-Agent Chess RL System (CPU)"

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    stockfish \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy the backend source
COPY backend/ ./backend/
COPY shared/ ./shared/

# Copy the built frontend into the backend's static directory
# vite.config.ts outputs to dist/public/ (see build.outDir in vite.config.ts)
COPY --from=frontend-builder /app/frontend/dist/public ./backend/static/

# Copy entrypoint
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

# Create directories for model cache and training data
RUN mkdir -p /app/models /app/data/games /app/data/training /app/logs \
    /app/models/Qwen_Qwen2.5-0.5B-Instruct \
    /app/models/meta-llama_Llama-3.2-1B-Instruct

# ── Download models at build time ────────────────────────────────────────────
# Qwen2.5-0.5B — no token required
RUN pip install --no-cache-dir huggingface_hub && \
    python3 -c " \
from huggingface_hub import snapshot_download; \
snapshot_download( \
    repo_id='Qwen/Qwen2.5-0.5B-Instruct', \
    local_dir='/app/models/Qwen_Qwen2.5-0.5B-Instruct', \
    local_dir_use_symlinks=False, \
    ignore_patterns=['*.msgpack','*.h5','flax_model*','tf_model*'] \
)"

# Llama-3.2-1B — requires HF token (pass as build arg: --build-arg HF_TOKEN=hf_...)
ARG HF_TOKEN=""
RUN if [ -n "$HF_TOKEN" ]; then \
    python3 -c " \
from huggingface_hub import snapshot_download; \
snapshot_download( \
    repo_id='meta-llama/Llama-3.2-1B-Instruct', \
    local_dir='/app/models/meta-llama_Llama-3.2-1B-Instruct', \
    local_dir_use_symlinks=False, \
    token='${HF_TOKEN}', \
    ignore_patterns=['*.msgpack','*.h5','flax_model*','tf_model*'] \
)"; \
fi

ENV WHITE_MODEL=/app/models/Qwen_Qwen2.5-0.5B-Instruct
ENV BLACK_MODEL=/app/models/meta-llama_Llama-3.2-1B-Instruct

# Expose the application port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["backend"]

# ── Stage 3: GPU backend ──────────────────────────────────────────────────────
FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04 AS backend-gpu

LABEL maintainer="ChessEcon Team"
LABEL description="ChessEcon — Multi-Agent Chess RL System (GPU/CUDA)"

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-dev \
    python3-pip \
    stockfish \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
    && ln -sf /usr/bin/python3 /usr/bin/python

WORKDIR /app

# Install PyTorch with CUDA support first (separate layer for caching)
RUN pip install --no-cache-dir torch==2.3.0 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install remaining Python dependencies
COPY backend/requirements.txt ./backend/requirements.txt
COPY training/requirements.txt ./training/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
RUN pip install --no-cache-dir -r training/requirements.txt

# Copy source
COPY backend/ ./backend/
COPY training/ ./training/
COPY shared/ ./shared/

# Copy the built frontend
COPY --from=frontend-builder /app/frontend/dist/public ./backend/static/

# Copy entrypoint
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

# Create directories
RUN mkdir -p /app/models /app/data/games /app/data/training /app/logs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["backend"]
