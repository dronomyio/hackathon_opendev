"""
chess_engine.py
───────────────
Thin wrapper around python-chess providing:
  - Board state management
  - Legal move validation and parsing
  - FEN / SAN / UCI conversion helpers
  - Reward calculation after game end
"""

import chess
import chess.pgn
import random
from typing import Optional


class ChessEngine:
    """Manages a single game of chess and exposes helpers for the agent loop."""

    def __init__(self):
        self.board = chess.Board()

    # ── Board state ───────────────────────────────────────────────────────

    @property
    def fen(self) -> str:
        return self.board.fen()

    @property
    def turn(self) -> str:
        return "white" if self.board.turn == chess.WHITE else "black"

    @property
    def move_number(self) -> int:
        return self.board.fullmove_number

    @property
    def is_game_over(self) -> bool:
        return self.board.is_game_over()

    @property
    def result(self) -> Optional[str]:
        """Returns '1-0', '0-1', '1/2-1/2', or None if game is ongoing."""
        if not self.board.is_game_over():
            return None
        outcome = self.board.outcome()
        if outcome is None:
            return "1/2-1/2"
        if outcome.winner == chess.WHITE:
            return "1-0"
        if outcome.winner == chess.BLACK:
            return "0-1"
        return "1/2-1/2"

    @property
    def legal_moves_uci(self) -> list[str]:
        return [m.uci() for m in self.board.legal_moves]

    @property
    def legal_moves_san(self) -> list[str]:
        return [self.board.san(m) for m in self.board.legal_moves]

    def reset(self):
        self.board = chess.Board()

    # ── Move application ──────────────────────────────────────────────────

    def apply_move_uci(self, uci: str) -> Optional[str]:
        """
        Apply a UCI move (e.g. 'e2e4') to the board.
        Returns the SAN string on success, None if the move is illegal.
        """
        try:
            move = chess.Move.from_uci(uci)
            if move not in self.board.legal_moves:
                return None
            san = self.board.san(move)
            self.board.push(move)
            return san
        except (ValueError, chess.InvalidMoveError):
            return None

    def apply_move_san(self, san: str) -> Optional[str]:
        """
        Apply a SAN move (e.g. 'Nf3') to the board.
        Returns the UCI string on success, None if illegal.
        """
        try:
            move = self.board.parse_san(san)
            uci = move.uci()
            self.board.push(move)
            return uci
        except (ValueError, chess.InvalidMoveError, chess.AmbiguousMoveError):
            return None

    # ── Move parsing helpers ──────────────────────────────────────────────

    def parse_model_output(self, text: str) -> Optional[str]:
        """
        Extract the first plausible chess move from raw model output.
        Tries SAN first, then UCI.  Returns the SAN string if valid, else None.
        """
        # Clean up whitespace and take the first token
        tokens = text.strip().split()
        for token in tokens[:5]:  # check first 5 tokens
            clean = token.strip(".,!?;:()")
            # Try SAN
            try:
                move = self.board.parse_san(clean)
                if move in self.board.legal_moves:
                    return self.board.san(move)
            except Exception:
                pass
            # Try UCI
            try:
                move = chess.Move.from_uci(clean)
                if move in self.board.legal_moves:
                    return self.board.san(move)
            except Exception:
                pass
        return None

    def uci_to_san(self, uci: str) -> Optional[str]:
        """Convert a UCI move string (e.g. 'e2e4') to SAN if it is legal."""
        try:
            move = self.board.parse_uci(uci)
            if move in self.board.legal_moves:
                return self.board.san(move)
        except Exception:
            pass
        return None

    def san_to_uci(self, san: str) -> Optional[str]:
        """Convert a SAN move string (e.g. 'Nf3') to UCI if it is legal."""
        try:
            move = self.board.parse_san(san)
            if move in self.board.legal_moves:
                return move.uci()
        except Exception:
            pass
        return None

    def random_legal_move_san(self) -> Optional[str]:
        """Return a random legal move in SAN notation (fallback)."""
        legal = list(self.board.legal_moves)
        if not legal:
            return None
        move = random.choice(legal)
        return self.board.san(move)

    # ── Reward calculation ────────────────────────────────────────────────

    def compute_reward(self, agent_color: str) -> float:
        """
        Terminal reward for the agent after the game ends.
          +1.0  win
          -1.0  loss
           0.0  draw or game not over
        """
        result = self.result
        if result is None:
            return 0.0
        if result == "1-0":
            return 1.0 if agent_color == "white" else -1.0
        if result == "0-1":
            return 1.0 if agent_color == "black" else -1.0
        return 0.0  # draw

    # ── Position prompt ───────────────────────────────────────────────────

    def build_prompt(self, agent_color: str, move_history: list[str]) -> str:
        """
        Build the text prompt fed to Qwen for move generation.
        Keeps it short so the model stays focused on the move token.
        """
        history_str = " ".join(move_history[-20:]) if move_history else "(opening)"
        legal_sample = ", ".join(self.legal_moves_san[:10])
        return (
            f"You are a chess engine playing as {agent_color}.\n"
            f"Position (FEN): {self.fen}\n"
            f"Move history: {history_str}\n"
            f"Some legal moves: {legal_sample}\n"
            f"Reply with ONLY the single best next move in standard algebraic notation (SAN), "
            f"e.g. 'e4' or 'Nf3'. Do not explain."
        )

