"""
openenv/router.py
─────────────────
FastAPI router that exposes the OpenEnv 0.1 HTTP API:

  POST /reset         → start a new episode
  POST /step          → advance the environment by one action
  GET  /state         → inspect current episode state (no side-effects)
  GET  /env_info      → environment metadata (for HF Hub discoverability)

All endpoints are prefixed with /env so the full paths are:
  /env/reset, /env/step, /env/state, /env/env_info

A single global ChessEconEnv instance is shared across all HTTP requests.
An asyncio.Lock ensures that concurrent step() calls don't race.

The auto-play game loop (websocket_server.py) runs in parallel and calls
env.reset() / env.step() internally — it does NOT go through these HTTP
endpoints.  The HTTP endpoints are for external RL trainers (TRL, verl,
SkyRL etc.) that want to drive the environment themselves.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status

from backend.openenv.models import (
    ResetRequest, StepRequest,
    ResetResponse, StepResponse, StateResponse, EnvInfo,
)
from backend.openenv.env import ChessEconEnv
from backend.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/env", tags=["OpenEnv"])

# ── Singleton environment + lock ──────────────────────────────────────────────
_env: Optional[ChessEconEnv] = None
_env_lock: asyncio.Lock = asyncio.Lock()


def get_env() -> ChessEconEnv:
    """Return the global environment instance (initialised at app startup)."""
    global _env
    if _env is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Environment not initialised yet. Models still loading.",
        )
    return _env


def init_env(white_model_id: str, black_model_id: str) -> ChessEconEnv:
    """Called once at app lifespan startup after models are loaded."""
    global _env
    _env = ChessEconEnv(
        white_model_id=white_model_id,
        black_model_id=black_model_id,
        starting_wallet=settings.starting_wallet,
        entry_fee=settings.entry_fee,
        prize_pool_fraction=settings.prize_pool_fraction,
        max_moves=settings.max_moves,
    )
    logger.info(
        "ChessEconEnv initialised. White=%s Black=%s",
        white_model_id, black_model_id,
    )
    return _env


# ── OpenEnv endpoints ─────────────────────────────────────────────────────────

@router.post(
    "/reset",
    response_model=ResetResponse,
    summary="Reset — start a new episode",
    description=(
        "Initialises a new chess game, deducts entry fees from both agent wallets, "
        "and returns the initial observation. Compatible with OpenEnv 0.1 spec."
    ),
)
async def reset(request: Optional[ResetRequest] = None) -> ResetResponse:
    env = get_env()
    async with _env_lock:
        try:
            return env.reset(request)
        except Exception as exc:
            logger.exception("reset() failed")
            raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/step",
    response_model=StepResponse,
    summary="Step — apply one action",
    description=(
        "Applies a chess move (UCI or SAN) to the current board and returns "
        "the next observation, per-step reward, and termination flags. "
        "Returns reward=-0.1 for illegal moves (episode continues). "
        "Compatible with OpenEnv 0.1 spec."
    ),
)
async def step(request: StepRequest) -> StepResponse:
    env = get_env()
    async with _env_lock:
        try:
            return env.step(request.action)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            )
        except Exception as exc:
            logger.exception("step() failed")
            raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/state",
    response_model=StateResponse,
    summary="State — current episode state (read-only)",
    description=(
        "Returns the current episode state without advancing it. "
        "Safe to call at any time, even before reset(). "
        "Compatible with OpenEnv 0.1 spec."
    ),
)
async def state() -> StateResponse:
    env = get_env()
    try:
        return env.state()
    except Exception as exc:
        logger.exception("state() failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/env_info",
    response_model=EnvInfo,
    summary="Environment metadata",
    description=(
        "Returns environment metadata used by the HuggingFace OpenEnv Hub "
        "for discoverability. Lists action/observation spaces, agent models, "
        "reward range, and OpenEnv version."
    ),
)
async def env_info() -> EnvInfo:
    env = get_env()
    return EnvInfo(
        agents=[
            {"id": "white", "model": env.white_model_id, "role": "White player (Qwen)"},
            {"id": "black", "model": env.black_model_id, "role": "Black player (Llama)"},
        ]
    )
