"""
ChessEcon Backend — Game Router
REST endpoints for game management + WebSocket game runner that
orchestrates full games between agents and streams events live.
"""
from __future__ import annotations
import asyncio
import random
import uuid
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from shared.models import (
    GameState, NewGameResponse, MoveRequest, MoveResponse,
    GameOutcome, EventType, WSEvent,
    CoachingRequest, ComplexityAnalysis, PositionComplexity,
)
from backend.chess_lib.engine import chess_engine
from backend.economy.ledger import ledger
from backend.agents.complexity import complexity_analyzer
from backend.agents.claude_coach import claude_coach
from backend.api.websocket import (
    ws_manager, emit_game_start, emit_move,
    emit_coaching_request, emit_coaching_result,
    emit_game_end, emit_economy_update,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/game", tags=["game"])

# Track cumulative P&L per agent across sessions
_cumulative_pnl: dict = {}


# ── REST endpoints ────────────────────────────────────────────────────────────

@router.post("/new", response_model=NewGameResponse)
async def new_game(white_id: str = "white", black_id: str = "black"):
    """Create a new chess game and register agents."""
    ledger.register_agent(white_id)
    ledger.register_agent(black_id)
    game = chess_engine.new_game()
    return game

@router.get("/{game_id}", response_model=GameState)
async def get_game(game_id: str):
    try:
        return chess_engine.get_state(game_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Game {game_id} not found")

@router.post("/move", response_model=GameState)
async def make_move(req: MoveRequest):
    try:
        state = chess_engine.make_move(req.game_id, req.move_uci)
        return state
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Game {req.game_id} not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{game_id}")
async def delete_game(game_id: str):
    chess_engine.delete_game(game_id)
    return {"deleted": game_id}

@router.get("/")
async def list_games():
    return {"games": chess_engine.list_games()}

@router.get("/economy/summary")
async def economy_summary():
    return ledger.summary()

@router.get("/economy/wallet/{agent_id}")
async def get_wallet(agent_id: str):
    return ledger.get_wallet(agent_id).model_dump()


# ── WebSocket game runner ─────────────────────────────────────────────────────

@router.websocket("/ws/game")
async def websocket_game_runner(ws: WebSocket):
    """
    WebSocket endpoint that runs a full game when connected.
    Streams all events (moves, coaching, economy) to all dashboard clients.
    """
    await ws_manager.connect(ws)
    try:
        while True:
            data = await ws.receive_text()
            msg = __import__("json").loads(data)
            if msg.get("action") == "start_game":
                white_id = msg.get("white_id", "white_agent")
                black_id = msg.get("black_id", "black_agent")
                asyncio.create_task(run_game(white_id, black_id))
    except WebSocketDisconnect:
        await ws_manager.disconnect(ws)


async def run_game(
    white_id: str = "white_agent",
    black_id: str = "black_agent",
    game_number: int = 1,
) -> Optional[GameOutcome]:
    """
    Run a complete game between two heuristic agents with economic tracking.
    Streams all events via the WebSocket manager.
    """
    # Register agents and open tournament
    ledger.register_agent(white_id)
    ledger.register_agent(black_id)

    game = chess_engine.new_game()
    game_id = game.game_id
    pool = ledger.open_game(game_id, white_id, black_id)

    white_wallet = ledger.get_balance(white_id)
    black_wallet = ledger.get_balance(black_id)

    await emit_game_start(ws_manager, {
        "game_id": game_id,
        "game_number": game_number,
        "white_agent": white_id,
        "black_agent": black_id,
        "white_wallet": white_wallet,
        "black_wallet": black_wallet,
        "entry_fee": ledger.config.entry_fee,
        "prize_pool": pool,
    })

    max_moves = 150
    move_count = 0
    coaching_calls = {"white": 0, "black": 0}
    coaching_costs = {"white": 0.0, "black": 0.0}

    while move_count < max_moves:
        state = chess_engine.get_state(game_id)
        if state.outcome != GameOutcome.ONGOING:
            break

        # Determine current player
        is_white_turn = (move_count % 2 == 0)
        current_agent = white_id if is_white_turn else black_id
        player_label = "white" if is_white_turn else "black"

        # Complexity analysis
        features = chess_engine.complexity_features(game_id)
        features["fen"] = state.fen
        analysis = complexity_analyzer.analyze(features)

        # Decide whether to use coaching
        used_coaching = False
        coaching_move: Optional[str] = None

        if (
            analysis.recommend_coaching
            and ledger.can_afford_coaching(current_agent)
            and claude_coach.available
            and random.random() < 0.3  # 30% chance when eligible
        ):
            await emit_coaching_request(ws_manager, {
                "game_id": game_id,
                "agent_id": current_agent,
                "player": player_label,
                "complexity": analysis.score,
                "complexity_level": analysis.level.value,
                "wallet": ledger.get_balance(current_agent),
            })

            fee = ledger.charge_coaching(current_agent, game_id)
            if fee > 0:
                coaching_req = CoachingRequest(
                    game_id=game_id,
                    agent_id=current_agent,
                    fen=state.fen,
                    legal_moves=state.legal_moves,
                    wallet_balance=ledger.get_balance(current_agent),
                    complexity=analysis,
                )
                coaching_resp = claude_coach.analyze(coaching_req)
                coaching_move = coaching_resp.recommended_move
                used_coaching = True
                coaching_calls[player_label] += 1
                coaching_costs[player_label] += fee

                await emit_coaching_result(ws_manager, {
                    "game_id": game_id,
                    "agent_id": current_agent,
                    "player": player_label,
                    "recommended_move": coaching_move,
                    "analysis_snippet": coaching_resp.analysis[:200],
                    "cost": fee,
                    "model": coaching_resp.model_used,
                })

        # Select move
        if coaching_move and coaching_move in state.legal_moves:
            move_uci = coaching_move
        else:
            move_uci = _heuristic_move(state.legal_moves, state.fen)

        # Execute move
        try:
            new_state = chess_engine.make_move(game_id, move_uci)
        except ValueError as e:
            logger.warning(f"Invalid move {move_uci}: {e} — using random")
            move_uci = random.choice(state.legal_moves)
            new_state = chess_engine.make_move(game_id, move_uci)

        move_count += 1
        white_wallet = ledger.get_balance(white_id)
        black_wallet = ledger.get_balance(black_id)

        await emit_move(ws_manager, {
            "game_id": game_id,
            "player": player_label,
            "move_uci": move_uci,
            "fen": new_state.fen,
            "move_number": new_state.move_number,
            "wallet_white": white_wallet,
            "wallet_black": black_wallet,
            "used_coaching": used_coaching,
            "complexity": analysis.score,
        })

        # Small delay for visual effect
        await asyncio.sleep(0.3)

    # Settle game
    final_state = chess_engine.get_state(game_id)
    outcome = final_state.outcome
    if outcome == GameOutcome.ONGOING:
        outcome = GameOutcome.DRAW  # Treat max-move games as draws

    result = ledger.settle_game(game_id, outcome)
    chess_engine.delete_game(game_id)

    white_final = ledger.get_balance(white_id)
    black_final = ledger.get_balance(black_id)

    # Compute P&L for economy update
    entry_fee = ledger.config.entry_fee
    prize_income = result.prize_paid if result.winner == white_id else (
        result.prize_paid if result.winner == black_id else result.prize_paid / 2
    )
    total_coaching = coaching_costs["white"] + coaching_costs["black"]
    net_pnl = prize_income - entry_fee - total_coaching

    # Track cumulative P&L
    for aid in [white_id, black_id]:
        _cumulative_pnl[aid] = _cumulative_pnl.get(aid, 0.0) + (
            (result.prize_paid - entry_fee - coaching_costs.get("white" if aid == white_id else "black", 0.0))
        )

    await emit_game_end(ws_manager, {
        "game_id": game_id,
        "game_number": game_number,
        "outcome": outcome.value,
        "winner": result.winner,
        "white_wallet_final": white_final,
        "black_wallet_final": black_final,
        "prize_paid": result.prize_paid,
        "total_moves": move_count,
        "coaching_calls_white": coaching_calls["white"],
        "coaching_calls_black": coaching_calls["black"],
    })

    await emit_economy_update(ws_manager, {
        "game_number": game_number,
        "white_wallet": white_final,
        "black_wallet": black_final,
        "prize_income": result.prize_paid,
        "coaching_cost": total_coaching,
        "entry_fee": entry_fee * 2,
        "net_pnl": net_pnl,
        "cumulative_pnl": _cumulative_pnl.get(white_id, 0.0),
    })

    return outcome


def _heuristic_move(legal_moves: list, fen: str) -> str:
    """Simple heuristic: prefer captures and center moves, else random."""
    import chess as _chess
    board = _chess.Board(fen)
    captures = [m.uci() for m in board.legal_moves if board.is_capture(m)]
    if captures:
        return random.choice(captures)
    center = ["e2e4", "d2d4", "e7e5", "d7d5", "g1f3", "b1c3"]
    center_moves = [m for m in center if m in legal_moves]
    if center_moves:
        return random.choice(center_moves)
    return random.choice(legal_moves)
