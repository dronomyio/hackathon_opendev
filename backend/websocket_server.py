"""
websocket_server.py  (v2 — OpenEnv + Dual Agent)
─────────────────────────────────────────────────
FastAPI application that:
  1. Loads TWO models at startup:
       White → Qwen/Qwen2.5-0.5B-Instruct
       Black → meta-llama/Llama-3.2-1B-Instruct
  2. Registers the OpenEnv 0.1 HTTP API at /env/*
  3. Runs continuous self-play games (white=Qwen vs black=Llama).
  4. Streams every game event to all connected WebSocket clients.
  5. Runs GRPO on the WHITE model only (Qwen) — Llama acts as fixed opponent.

OpenEnv endpoints (for external RL trainers):
  POST /env/reset      start a new episode
  POST /env/step       apply one action
  GET  /env/state      inspect current state
  GET  /env/env_info   environment metadata (HF Hub discoverability)

WebSocket endpoint:  /ws
Health check:        /health
API docs:            /docs
"""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from settings import settings
from chess_engine import ChessEngine
from agents.model_agent import ModelAgent
from grpo_trainer import GRPOTrainer
from openenv.router import router as openenv_router, init_env

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Global state ──────────────────────────────────────────────────────────────
connected_clients: set[WebSocket] = set()
paused = False
game_count = 0
wallet_white = settings.starting_wallet
wallet_black = settings.starting_wallet

# Initialised in lifespan
white_agent: ModelAgent | None = None
black_agent: ModelAgent | None = None
trainer: GRPOTrainer | None = None


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global white_agent, black_agent, trainer

    logger.info("Loading WHITE model (%s) …", settings.white_model)
    white_agent = ModelAgent(settings.white_model).load()

    logger.info("Loading BLACK model (%s) …", settings.black_model)
    black_agent = ModelAgent(settings.black_model).load()

    # GRPO trains the WHITE agent (Qwen); Llama is a fixed opponent
    trainer = GRPOTrainer(white_agent.model, white_agent.tokenizer)

    # Initialise the OpenEnv environment (used by /env/* HTTP endpoints)
    init_env(
        white_model_id=settings.white_model,
        black_model_id=settings.black_model,
    )

    logger.info("Both models ready. Starting auto-play loop …")
    asyncio.create_task(game_loop())
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="ChessEcon",
    description=(
        "Multi-Agent Chess Economy — OpenEnv 0.1 compliant environment. "
        "White: Qwen2.5-0.5B  |  Black: Llama-3.2-1B  |  Training: GRPO"
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register OpenEnv HTTP router at /env/*
app.include_router(openenv_router)


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "chessecon",
        "version": "2.0.0",
        "openenv_version": "0.1",
        "white_model": settings.white_model,
        "black_model": settings.black_model,
        "ws_clients": len(connected_clients),
        "games_played": game_count,
    }


# ── WebSocket endpoint ────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.add(ws)
    logger.info("WS client connected (%d total)", len(connected_clients))
    # Send current state snapshot to new client immediately
    try:
        await ws.send_text(json.dumps({
            "type": "status",
            "data": {
                "game_id": game_count,
                "wallet_white": round(wallet_white, 2),
                "wallet_black": round(wallet_black, 2),
                "grpo_step": trainer._step if trainer else 0,
                "message": f"Connected — game #{game_count} in progress",
            }
        }))
    except Exception:
        pass
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
                await handle_client_message(ws, msg)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        connected_clients.discard(ws)
        logger.info("WS client disconnected (%d total)", len(connected_clients))


async def handle_client_message(ws: WebSocket, msg: dict):
    global paused
    action = msg.get("action", "")
    if action == "ping":
        await ws.send_text(json.dumps({"type": "pong", "data": {}}))
    elif action == "pause":
        paused = True
        logger.info("Game loop paused")
    elif action == "resume":
        paused = False
        logger.info("Game loop resumed")


# ── Broadcast helper ──────────────────────────────────────────────────────────
async def broadcast(event_type: str, data: dict[str, Any]):
    if not connected_clients:
        return
    payload = json.dumps({"type": event_type, "data": data})
    dead: set[WebSocket] = set()
    for ws in list(connected_clients):
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    connected_clients.difference_update(dead)


# ── Main game loop ────────────────────────────────────────────────────────────
async def game_loop():
    global game_count, wallet_white, wallet_black, paused

    while True:
        while paused:
            await asyncio.sleep(0.5)

        game_count += 1
        engine = ChessEngine()

        wallet_white -= settings.entry_fee
        wallet_black -= settings.entry_fee
        prize_pool = settings.entry_fee * 2 * settings.prize_pool_fraction

        await broadcast("game_start", {
            "game_id": game_count,
            "wallet_white": round(wallet_white, 2),
            "wallet_black": round(wallet_black, 2),
            "prize_pool": round(prize_pool, 2),
            "white_model": settings.white_model,
            "black_model": settings.black_model,
            "message": (
                f"Game #{game_count} — "
                f"Qwen(W) vs Llama(B) — "
                f"Prize pool: {prize_pool:.1f} units"
            ),
        })

        trainer.start_game("white")  # type: ignore[union-attr]
        move_history: list[str] = []

        # ── Play the game ─────────────────────────────────────────────────
        while not engine.is_game_over and engine.move_number <= settings.max_moves:
            while paused:
                await asyncio.sleep(0.5)

            current_color = engine.turn
            # Select the right agent
            active_agent = white_agent if current_color == "white" else black_agent

            san, log_prob = await asyncio.get_event_loop().run_in_executor(
                None,
                active_agent.get_move,  # type: ignore[union-attr]
                engine, current_color, move_history,
            )

            # KL reference: only needed for WHITE (GRPO training target)
            if current_color == "white":
                ref_log_prob = await asyncio.get_event_loop().run_in_executor(
                    None,
                    white_agent.get_move_log_prob_only,  # type: ignore[union-attr]
                    engine, current_color, move_history, san,
                )
            else:
                ref_log_prob = log_prob  # Black is fixed; KL = 0

            uci = engine.apply_move_san(san)
            if uci is None:
                fallback = engine.random_legal_move_san()
                if fallback is None:
                    break
                san = fallback
                uci = engine.apply_move_san(san) or ""
                log_prob = 0.0
                ref_log_prob = 0.0

            trainer.record_move(log_prob, ref_log_prob)  # type: ignore[union-attr]
            move_history.append(san)

            await broadcast("move", {
                "game_id": game_count,
                "player": current_color,
                "model": settings.white_model if current_color == "white" else settings.black_model,
                "move": san,
                "uci": uci,
                "fen": engine.fen,
                "move_number": engine.move_number,
                "turn": engine.turn,
                "wallet_white": round(wallet_white, 2),
                "wallet_black": round(wallet_black, 2),
                "message": f"{'Qwen' if current_color == 'white' else 'Llama'} plays {san}",
            })

            await asyncio.sleep(settings.move_delay)

        # ── Game over ─────────────────────────────────────────────────────
        # If game ended by chess rules use that result; otherwise adjudicate by material
        if engine.result:
            result = engine.result
        else:
            # Count material: Q=9 R=5 B=3 N=3 P=1
            piece_values = {1: 1, 2: 3, 3: 3, 4: 5, 5: 9}  # pawn,knight,bishop,rook,queen
            import chess as _chess
            white_mat = sum(
                piece_values.get(pt, 0)
                for pt in range(1, 6)
                for _ in engine.board.pieces(pt, _chess.WHITE)
            )
            black_mat = sum(
                piece_values.get(pt, 0)
                for pt in range(1, 6)
                for _ in engine.board.pieces(pt, _chess.BLACK)
            )
            result = '1-0' if white_mat >= black_mat else '0-1'  # always decisive
        white_reward = 1.0 if result == "1-0" else (-1.0 if result == "0-1" else 0.0)
        black_reward = 1.0 if result == "0-1" else (-1.0 if result == "1-0" else 0.0)

        if result == "1-0":
            wallet_white += prize_pool
        elif result == "0-1":
            wallet_black += prize_pool
        else:
            wallet_white += prize_pool / 2
            wallet_black += prize_pool / 2

        white_pnl = (
            prize_pool if result == "1-0"
            else prize_pool / 2 if result == "1/2-1/2"
            else 0
        ) - settings.entry_fee
        black_pnl = (
            prize_pool if result == "0-1"
            else prize_pool / 2 if result == "1/2-1/2"
            else 0
        ) - settings.entry_fee

        await broadcast("game_end", {
            "game_id": game_count,
            "result": result,
            "reward": white_reward,
            "wallet_white": round(wallet_white, 2),
            "wallet_black": round(wallet_black, 2),
            "prize_income": round(
                prize_pool if result == "1-0"
                else prize_pool / 2 if result == "1/2-1/2"
                else 0, 2
            ),
            "coaching_cost": 0,
            "entry_fee": settings.entry_fee,
            "net_pnl_white": round(white_pnl, 2),
            "net_pnl_black": round(black_pnl, 2),
            "move_count": len(move_history),
            "white_model": settings.white_model,
            "black_model": settings.black_model,
            "message": f"Game #{game_count} ended — {result}",
        })

        # GRPO update (WHITE model only)
        training_metrics = trainer.end_game(  # type: ignore[union-attr]
            reward=white_reward,
            profit=white_pnl,
            coaching_calls=0,
        )

        if training_metrics is not None:
            await broadcast("training_step", {
                "step": training_metrics.step,
                "loss": round(training_metrics.loss, 6),
                "reward": round(training_metrics.policy_reward, 4),
                "kl_div": round(training_metrics.kl_div, 6),
                "win_rate": round(training_metrics.win_rate, 4),
                "avg_profit": round(training_metrics.avg_profit, 4),
                "coaching_rate": round(training_metrics.coaching_rate, 4),
                "model": settings.white_model,
                "message": (
                    f"GRPO step {training_metrics.step} | "
                    f"loss={training_metrics.loss:.4f} "
                    f"win_rate={training_metrics.win_rate:.2%}"
                ),
            })

        await asyncio.sleep(1.0)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "websocket_server:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info",
    )
