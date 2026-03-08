"""
ChessEcon Backend — Training Status Router
REST endpoints for monitoring training progress.
The actual training runs in the separate training/ service.
"""
from __future__ import annotations
import os
import json
import glob
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/training", tags=["training"])

CHECKPOINT_DIR   = os.getenv("CHECKPOINT_DIR", "./training/checkpoints")
SELFPLAY_DATA_DIR = os.getenv("SELFPLAY_DATA_DIR", "./training/data")


@router.get("/status")
async def training_status():
    """Return current training status from checkpoint directory."""
    checkpoint_dir = Path(CHECKPOINT_DIR)
    if not checkpoint_dir.exists():
        return {"status": "not_started", "checkpoints": [], "latest_step": 0}

    checkpoints = sorted(checkpoint_dir.glob("step_*"), key=lambda p: p.stat().st_mtime)
    latest_step = 0
    latest_metrics = {}

    if checkpoints:
        latest = checkpoints[-1]
        metrics_file = latest / "metrics.json"
        if metrics_file.exists():
            with open(metrics_file) as f:
                latest_metrics = json.load(f)
        latest_step = int(latest.name.replace("step_", ""))

    return {
        "status": "running" if checkpoints else "not_started",
        "latest_step": latest_step,
        "checkpoints": [str(c.name) for c in checkpoints[-5:]],
        "latest_metrics": latest_metrics,
    }

@router.get("/metrics")
async def training_metrics():
    """Return all training metrics from saved checkpoints."""
    checkpoint_dir = Path(CHECKPOINT_DIR)
    if not checkpoint_dir.exists():
        return {"metrics": []}

    all_metrics = []
    for metrics_file in sorted(checkpoint_dir.glob("*/metrics.json")):
        try:
            with open(metrics_file) as f:
                all_metrics.append(json.load(f))
        except Exception:
            pass

    return {"metrics": all_metrics}

@router.get("/episodes")
async def episode_count():
    """Return count of collected self-play episodes."""
    data_dir = Path(SELFPLAY_DATA_DIR)
    if not data_dir.exists():
        return {"count": 0, "files": []}

    files = list(data_dir.glob("*.jsonl"))
    total = sum(
        sum(1 for _ in open(f)) for f in files
    )
    return {"count": total, "files": [f.name for f in files[-5:]]}
