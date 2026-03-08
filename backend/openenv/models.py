"""
openenv/models.py
─────────────────
Pydantic schemas that exactly match the OpenEnv 0.1 HTTP spec.

  POST /reset  → ResetResponse
  POST /step   → StepResponse
  GET  /state  → StateResponse

All three wrap a shared Observation object that carries chess-specific
fields inside the `info` dict so the core contract stays generic.
"""

from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field


# ── Request bodies ─────────────────────────────────────────────────────────────

class StepRequest(BaseModel):
    """Action sent by the RL trainer to advance the environment by one move."""
    action: str = Field(
        ...,
        description="Chess move in UCI notation (e.g. 'e2e4') or SAN (e.g. 'e4')",
        examples=["e2e4", "Nf3", "O-O"],
    )


class ResetRequest(BaseModel):
    """Optional seed / config passed on reset. All fields optional."""
    seed: Optional[int] = Field(None, description="RNG seed for reproducibility")
    config: Optional[dict[str, Any]] = Field(
        None, description="Override environment config for this episode"
    )


# ── Core observation ───────────────────────────────────────────────────────────

class ChessObservation(BaseModel):
    """
    Chess-specific observation.  Returned inside every response as `observation`.
    The `info` dict carries auxiliary data (legal moves, last move, etc.) so that
    the outer schema stays OpenEnv-generic.
    """
    fen: str = Field(..., description="Current board position in FEN notation")
    turn: str = Field(..., description="'white' or 'black'")
    move_number: int = Field(..., description="Full-move number (1-indexed)")
    last_move_uci: Optional[str] = Field(None, description="Last move in UCI notation")
    last_move_san: Optional[str] = Field(None, description="Last move in SAN notation")
    legal_moves_uci: list[str] = Field(..., description="All legal moves in UCI notation")
    is_check: bool = Field(False, description="Whether the current side is in check")
    # Economy
    wallet_white: float = Field(..., description="White agent wallet balance (units)")
    wallet_black: float = Field(..., description="Black agent wallet balance (units)")
    # Agent identities
    white_model: str = Field(..., description="Model ID playing White")
    black_model: str = Field(..., description="Model ID playing Black")
    # Info dict for auxiliary / extensible data
    info: dict[str, Any] = Field(default_factory=dict)


# ── OpenEnv response bodies ────────────────────────────────────────────────────

class ResetResponse(BaseModel):
    """
    Returned by POST /reset.
    OpenEnv spec: { observation, info }
    """
    observation: ChessObservation
    info: dict[str, Any] = Field(default_factory=dict)


class StepResponse(BaseModel):
    """
    Returned by POST /step.
    OpenEnv spec: { observation, reward, terminated, truncated, info }
    """
    observation: ChessObservation
    reward: float = Field(..., description="Per-step reward signal")
    terminated: bool = Field(..., description="True if the episode ended naturally (checkmate/stalemate/draw)")
    truncated: bool = Field(..., description="True if the episode was cut short (move limit)")
    info: dict[str, Any] = Field(default_factory=dict)


class StateResponse(BaseModel):
    """
    Returned by GET /state.
    OpenEnv spec: { observation, info, episode_id, step_count, status }
    """
    observation: ChessObservation
    info: dict[str, Any] = Field(default_factory=dict)
    episode_id: str = Field(..., description="Unique identifier for the current episode")
    step_count: int = Field(..., description="Number of moves played so far")
    status: str = Field(..., description="'active' | 'terminated' | 'truncated' | 'idle'")


# ── Environment info ──────────────────────────────────────────────────────────

class EnvInfo(BaseModel):
    """Returned by GET /env_info — describes environment capabilities."""
    name: str = "chessecon"
    version: str = "1.0.0"
    description: str = (
        "Two-agent chess economy environment. White plays Qwen2.5-0.5B-Instruct, "
        "Black plays Llama-3.2-1B-Instruct. Agents earn/lose economic units based "
        "on game outcomes. Compatible with OpenEnv 0.1 spec."
    )
    openenv_version: str = "0.1"
    action_space: dict = Field(
        default_factory=lambda: {
            "type": "text",
            "description": "Chess move in UCI (e2e4) or SAN (e4) notation",
        }
    )
    observation_space: dict = Field(
        default_factory=lambda: {
            "type": "structured",
            "fields": ["fen", "turn", "move_number", "legal_moves_uci",
                       "wallet_white", "wallet_black", "is_check"],
        }
    )
    reward_range: list[float] = Field(default_factory=lambda: [-1.0, 1.0])
    max_episode_steps: int = 300
    agents: list[dict] = Field(
        default_factory=lambda: [
            {"id": "white", "model": "Qwen/Qwen2.5-0.5B-Instruct", "role": "White player"},
            {"id": "black", "model": "meta-llama/Llama-3.2-1B-Instruct", "role": "Black player"},
        ]
    )
    tags: list[str] = Field(
        default_factory=lambda: [
            "chess", "multi-agent", "rl", "grpo", "economy",
            "openenv", "two-player", "game",
        ]
    )
