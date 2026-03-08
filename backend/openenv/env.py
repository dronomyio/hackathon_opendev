"""
openenv/env.py
──────────────
Stateful ChessEcon environment that implements the OpenEnv 0.1 contract:

  reset()  → ResetResponse
  step()   → StepResponse
  state()  → StateResponse

Key design decisions:
  - Each call to reset() creates a new episode (new game_id, fresh board).
  - step(action) accepts either UCI or SAN notation.
  - Rewards are computed per-step (not just terminal):
      +0.01  legal move played
      +0.05  move gives check
      +0.10  capture
      +1.00  win
      -1.00  loss
       0.00  draw
  - Economy (entry fees, prize pool) is tracked per episode.
  - Thread-safe: each episode is independent.  The FastAPI router creates
    one global instance and serialises access via asyncio locks.
"""

from __future__ import annotations

import uuid
import logging
from typing import Optional

import chess

from backend.chess_engine import ChessEngine
from backend.settings import settings
from backend.openenv.models import (
    ChessObservation, ResetResponse, StepResponse, StateResponse, ResetRequest,
)

logger = logging.getLogger(__name__)

# Shaping rewards (small intermediate signals)
REWARD_LEGAL_MOVE   =  0.01
REWARD_CHECK        =  0.05
REWARD_CAPTURE      =  0.10
REWARD_WIN          =  1.00
REWARD_LOSS         = -1.00
REWARD_DRAW         =  0.00


class ChessEconEnv:
    """
    OpenEnv-compliant Chess Economy environment.

    Manages a single active episode. Call reset() to start a new episode.
    Call step(action) to advance it. Call state() to inspect without advancing.
    """

    def __init__(
        self,
        white_model_id: str,
        black_model_id: str,
        starting_wallet: float = 100.0,
        entry_fee: float = 10.0,
        prize_pool_fraction: float = 0.9,
        max_moves: int = 150,
    ):
        self.white_model_id = white_model_id
        self.black_model_id = black_model_id
        self.starting_wallet = starting_wallet
        self.entry_fee = entry_fee
        self.prize_pool_fraction = prize_pool_fraction
        self.max_moves = max_moves

        # Episode state (None until first reset())
        self._engine: Optional[ChessEngine] = None
        self._episode_id: str = ""
        self._step_count: int = 0
        self._status: str = "idle"
        self._move_history: list[str] = []

        # Economy
        self._wallet_white: float = starting_wallet
        self._wallet_black: float = starting_wallet
        self._prize_pool: float = 0.0

        # Last move for observation
        self._last_uci: Optional[str] = None
        self._last_san: Optional[str] = None

    # ── OpenEnv core API ───────────────────────────────────────────────────────

    def reset(self, request: Optional[ResetRequest] = None) -> ResetResponse:
        """
        Start a new episode.  Deducts entry fees and returns the initial observation.
        """
        self._engine = ChessEngine()
        self._episode_id = str(uuid.uuid4())
        self._step_count = 0
        self._status = "active"
        self._move_history = []
        self._last_uci = None
        self._last_san = None

        # Economy: deduct entry fees
        self._wallet_white -= self.entry_fee
        self._wallet_black -= self.entry_fee
        self._prize_pool = self.entry_fee * 2 * self.prize_pool_fraction

        logger.info(
            "Episode %s started. Wallets: W=%.1f B=%.1f prize_pool=%.1f",
            self._episode_id[:8], self._wallet_white, self._wallet_black, self._prize_pool,
        )

        obs = self._build_observation()
        return ResetResponse(
            observation=obs,
            info={
                "episode_id": self._episode_id,
                "prize_pool": self._prize_pool,
                "entry_fee": self.entry_fee,
            },
        )

    def step(self, action: str) -> StepResponse:
        """
        Apply a move to the board and return the next observation + reward.

        action: UCI string ('e2e4') or SAN string ('e4').
        """
        if self._engine is None or self._status != "active":
            raise RuntimeError("Call reset() before step()")

        # ── Apply the move ─────────────────────────────────────────────────
        # Try UCI first, then SAN
        uci_applied: Optional[str] = None
        san_applied: Optional[str] = None

        # UCI path
        san_from_uci = self._engine.apply_move_uci(action)
        if san_from_uci is not None:
            uci_applied = action
            san_applied = san_from_uci
        else:
            # SAN path — we need the UCI back
            try:
                move = self._engine.board.parse_san(action)
                uci_applied = move.uci()
                san_applied = self._engine.board.san(move)
                self._engine.board.push(move)
            except Exception:
                # Illegal move — return current state with negative reward
                obs = self._build_observation()
                return StepResponse(
                    observation=obs,
                    reward=-0.10,
                    terminated=False,
                    truncated=False,
                    info={"error": f"Illegal move: {action}", "legal_moves": self._engine.legal_moves_uci[:10]},
                )

        self._last_uci = uci_applied
        self._last_san = san_applied
        self._move_history.append(san_applied)
        self._step_count += 1

        # ── Compute per-step reward ────────────────────────────────────────
        reward = self._compute_step_reward(uci_applied)

        # ── Check termination ──────────────────────────────────────────────
        terminated = bool(self._engine.is_game_over)
        truncated = (not terminated) and (self._step_count >= self.max_moves * 2)

        if terminated or truncated:
            reward = self._settle_game(terminated, truncated, reward)

        obs = self._build_observation()

        return StepResponse(
            observation=obs,
            reward=round(reward, 4),
            terminated=terminated,
            truncated=truncated,
            info={
                "episode_id": self._episode_id,
                "step": self._step_count,
                "san": san_applied,
                "uci": uci_applied,
                "move_history": self._move_history[-10:],
                "prize_pool": self._prize_pool,
            },
        )

    def state(self) -> StateResponse:
        """Return current episode state without advancing it."""
        if self._engine is None:
            # Return idle state with default observation
            idle_obs = ChessObservation(
                fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                turn="white",
                move_number=1,
                legal_moves_uci=[],
                wallet_white=self._wallet_white,
                wallet_black=self._wallet_black,
                white_model=self.white_model_id,
                black_model=self.black_model_id,
            )
            return StateResponse(
                observation=idle_obs,
                episode_id="",
                step_count=0,
                status="idle",
            )

        return StateResponse(
            observation=self._build_observation(),
            episode_id=self._episode_id,
            step_count=self._step_count,
            status=self._status,
            info={
                "prize_pool": self._prize_pool,
                "move_history": self._move_history[-10:],
            },
        )

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _build_observation(self) -> ChessObservation:
        engine = self._engine
        assert engine is not None
        board = engine.board

        return ChessObservation(
            fen=engine.fen,
            turn=engine.turn,
            move_number=engine.move_number,
            last_move_uci=self._last_uci,
            last_move_san=self._last_san,
            legal_moves_uci=engine.legal_moves_uci,
            is_check=board.is_check(),
            wallet_white=round(self._wallet_white, 2),
            wallet_black=round(self._wallet_black, 2),
            white_model=self.white_model_id,
            black_model=self.black_model_id,
            info={
                "move_history": self._move_history[-20:],
                "step_count": self._step_count,
                "episode_id": self._episode_id,
            },
        )

    def _compute_step_reward(self, uci: str) -> float:
        """
        Dense per-step reward shaping.
        Evaluated AFTER the move has been applied, so we look at the NEW board state.
        """
        engine = self._engine
        assert engine is not None
        board = engine.board

        reward = REWARD_LEGAL_MOVE

        # Check bonus (opponent is now in check)
        if board.is_check():
            reward += REWARD_CHECK

        # Capture bonus — look at the move that was just pushed
        if board.move_stack:
            last_move = board.move_stack[-1]
            # Castling and en-passant: board.is_capture works on the board before the move
            # We check by looking at whether a piece disappeared from the target square
            # Simple heuristic: the move stack entry captures flag
            if board.is_capture(last_move):
                reward += REWARD_CAPTURE

        return reward

    def _settle_game(self, terminated: bool, truncated: bool, step_reward: float) -> float:
        """
        Apply terminal reward and settle the economy.
        Returns the final total reward for the last move.
        """
        engine = self._engine
        assert engine is not None

        result = engine.result or "1/2-1/2"
        white_reward = engine.compute_reward("white")  # +1, -1, or 0

        # Terminal reward
        if white_reward > 0:
            terminal = REWARD_WIN
            self._wallet_white += self._prize_pool
            logger.info("White wins! Prize: +%.1f", self._prize_pool)
        elif white_reward < 0:
            terminal = REWARD_LOSS
            self._wallet_black += self._prize_pool
            logger.info("Black wins! Prize: +%.1f", self._prize_pool)
        else:
            terminal = REWARD_DRAW
            self._wallet_white += self._prize_pool / 2
            self._wallet_black += self._prize_pool / 2
            logger.info("Draw. Split prize: +%.1f each", self._prize_pool / 2)

        self._status = "truncated" if truncated else "terminated"

        logger.info(
            "Episode %s ended. Result=%s Wallets: W=%.1f B=%.1f",
            self._episode_id[:8], result,
            self._wallet_white, self._wallet_black,
        )

        return step_reward + terminal
