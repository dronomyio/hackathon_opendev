"""
ChessEcon Backend — Chess Engine
Wraps python-chess to manage game state, validate moves, and detect outcomes.
"""
from __future__ import annotations
import uuid
import chess
import chess.pgn
from typing import Dict, Optional, List
from shared.models import GameState, GameOutcome, GameStatus, NewGameResponse


class ChessEngine:
    """Thread-safe chess game manager. Stores all active games in memory."""

    def __init__(self):
        self._games: Dict[str, chess.Board] = {}

    # ── Game lifecycle ────────────────────────────────────────────────────────

    def new_game(self, game_id: Optional[str] = None) -> NewGameResponse:
        gid = game_id or str(uuid.uuid4())
        board = chess.Board()
        self._games[gid] = board
        return NewGameResponse(
            game_id=gid,
            fen=board.fen(),
            legal_moves=[m.uci() for m in board.legal_moves],
            status=GameStatus.ACTIVE,
        )

    def get_state(self, game_id: str) -> GameState:
        board = self._get_board(game_id)
        return GameState(
            game_id=game_id,
            fen=board.fen(),
            legal_moves=[m.uci() for m in board.legal_moves],
            outcome=self._outcome(board),
            move_number=board.fullmove_number,
            move_history=[m.uci() for m in board.move_stack],
            status=GameStatus.FINISHED if board.is_game_over() else GameStatus.ACTIVE,
        )

    def make_move(self, game_id: str, move_uci: str) -> GameState:
        board = self._get_board(game_id)
        if board.is_game_over():
            raise ValueError(f"Game {game_id} is already over")
        try:
            move = chess.Move.from_uci(move_uci)
        except ValueError:
            raise ValueError(f"Invalid UCI move format: {move_uci}")
        if move not in board.legal_moves:
            legal = [m.uci() for m in board.legal_moves]
            raise ValueError(
                f"Illegal move {move_uci} in position {board.fen()}. "
                f"Legal moves: {legal[:10]}{'...' if len(legal) > 10 else ''}"
            )
        board.push(move)
        return self.get_state(game_id)

    def delete_game(self, game_id: str) -> None:
        self._games.pop(game_id, None)

    def list_games(self) -> List[str]:
        return list(self._games.keys())

    # ── Position analysis ─────────────────────────────────────────────────────

    def get_legal_moves(self, game_id: str) -> List[str]:
        board = self._get_board(game_id)
        return [m.uci() for m in board.legal_moves]

    def get_fen(self, game_id: str) -> str:
        return self._get_board(game_id).fen()

    def is_game_over(self, game_id: str) -> bool:
        return self._get_board(game_id).is_game_over()

    def complexity_features(self, game_id: str) -> dict:
        """Return raw features used by the complexity analyzer."""
        board = self._get_board(game_id)
        legal = list(board.legal_moves)
        return {
            "num_legal_moves": len(legal),
            "is_check": board.is_check(),
            "has_captures": any(board.is_capture(m) for m in legal),
            "num_pieces": len(board.piece_map()),
            "fullmove_number": board.fullmove_number,
            "material_balance": self._material_balance(board),
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_board(self, game_id: str) -> chess.Board:
        if game_id not in self._games:
            raise KeyError(f"Game {game_id} not found")
        return self._games[game_id]

    @staticmethod
    def _outcome(board: chess.Board) -> GameOutcome:
        if not board.is_game_over():
            return GameOutcome.ONGOING
        result = board.result()
        if result == "1-0":
            return GameOutcome.WHITE_WIN
        elif result == "0-1":
            return GameOutcome.BLACK_WIN
        return GameOutcome.DRAW

    @staticmethod
    def _material_balance(board: chess.Board) -> float:
        """Positive = white advantage."""
        piece_values = {
            chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
            chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0,
        }
        balance = 0.0
        for piece_type, value in piece_values.items():
            balance += value * len(board.pieces(piece_type, chess.WHITE))
            balance -= value * len(board.pieces(piece_type, chess.BLACK))
        return balance


# Singleton instance
chess_engine = ChessEngine()
