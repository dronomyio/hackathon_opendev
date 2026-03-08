#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# ChessEcon Docker Entrypoint
#
# Modes (CMD argument):
#   backend       — Start the FastAPI server (default)
#   train         — Run the RL training loop
#   selfplay      — Run self-play data collection only (no training)
#   download      — Download the HuggingFace model and exit
#   demo          — Run a quick 3-game demo and exit
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

MODE="${1:-backend}"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║              ChessEcon — Multi-Agent Chess RL                ║"
echo "║  TextArena + Meta OpenEnv + GRPO | Hackathon 2026            ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Mode: $MODE"
echo "Model: ${PLAYER_MODEL:-Qwen/Qwen2.5-0.5B-Instruct}"
echo "RL Method: ${RL_METHOD:-grpo}"
echo ""

# ── Validate required environment variables ───────────────────────────────
check_env() {
    local var_name="$1"
    local required="${2:-false}"
    if [ -z "${!var_name:-}" ]; then
        if [ "$required" = "true" ]; then
            echo "ERROR: Required environment variable $var_name is not set."
            echo "       Please set it in your .env file or Docker environment."
            exit 1
        else
            echo "WARNING: Optional variable $var_name is not set."
        fi
    fi
}

# Always required
check_env "HF_TOKEN" "true"

# Required for Claude coaching
if [ "${ENABLE_CLAUDE_COACHING:-true}" = "true" ]; then
    check_env "ANTHROPIC_API_KEY" "true"
fi

# ── Download model from HuggingFace if not cached ────────────────────────
MODEL_NAME="${PLAYER_MODEL:-Qwen/Qwen2.5-0.5B-Instruct}"
MODEL_CACHE_DIR="/app/models/$(echo $MODEL_NAME | tr '/' '_')"

if [ ! -d "$MODEL_CACHE_DIR" ] || [ "${FORCE_DOWNLOAD:-false}" = "true" ]; then
    echo "Downloading model: $MODEL_NAME"
    echo "Cache directory: $MODEL_CACHE_DIR"
    python3 -c "
from huggingface_hub import snapshot_download
import os
snapshot_download(
    repo_id='${MODEL_NAME}',
    local_dir='${MODEL_CACHE_DIR}',
    token=os.environ.get('HF_TOKEN'),
    ignore_patterns=['*.bin', '*.pt'] if os.environ.get('USE_SAFETENSORS', 'true') == 'true' else []
)
print('Model downloaded successfully.')
"
    echo "Model ready at: $MODEL_CACHE_DIR"
else
    echo "Model already cached at: $MODEL_CACHE_DIR"
fi

export MODEL_LOCAL_PATH="$MODEL_CACHE_DIR"

# ── Execute the requested mode ────────────────────────────────────────────
case "$MODE" in
    backend)
        echo ""
        echo "Starting ChessEcon API server on port ${PORT:-8000}..."
        echo "Dashboard: http://localhost:${PORT:-8000}"
        echo "API docs:  http://localhost:${PORT:-8000}/docs"
        echo "WebSocket: ws://localhost:${PORT:-8000}/ws"
        echo ""
        exec python3 -m uvicorn backend.main:app \
            --host 0.0.0.0 \
            --port "${PORT:-8000}" \
            --workers "${WORKERS:-1}" \
            --log-level "${LOG_LEVEL:-info}"
        ;;

    train)
        echo ""
        echo "Starting RL training..."
        echo "Method: ${RL_METHOD:-grpo}"
        echo "Games per batch: ${GAMES_PER_BATCH:-8}"
        echo "Training steps: ${MAX_TRAINING_STEPS:-1000}"
        echo ""
        exec python3 -m training.run \
            --method "${RL_METHOD:-grpo}" \
            --model-path "$MODEL_LOCAL_PATH" \
            --games-per-batch "${GAMES_PER_BATCH:-8}" \
            --max-steps "${MAX_TRAINING_STEPS:-1000}" \
            --output-dir "/app/data/training" \
            --log-dir "/app/logs"
        ;;

    selfplay)
        echo ""
        echo "Starting self-play data collection..."
        echo "Games: ${SELFPLAY_GAMES:-100}"
        echo ""
        exec python3 -m training.run \
            --method selfplay \
            --model-path "$MODEL_LOCAL_PATH" \
            --games "${SELFPLAY_GAMES:-100}" \
            --output-dir "/app/data/games"
        ;;

    download)
        echo "Model download complete. Exiting."
        exit 0
        ;;

    demo)
        echo ""
        echo "Running 3-game demo..."
        exec python3 -c "
import asyncio
import sys
sys.path.insert(0, '/app')
from backend.chess.engine import ChessEngine
from backend.economy.ledger import EconomicConfig, WalletManager, TournamentOrganizer

async def run_demo():
    config = EconomicConfig()
    wallets = WalletManager(config)
    wallets.create_wallet('white', 100.0)
    wallets.create_wallet('black', 100.0)
    organizer = TournamentOrganizer(config, wallets)

    for game_num in range(1, 4):
        print(f'\n--- Game {game_num} ---')
        engine = ChessEngine()
        game_id = organizer.open_game('white', 'black')
        print(f'Game ID: {game_id}')
        print(f'Prize pool: {organizer.games[game_id].prize_pool}')

        move_count = 0
        while not engine.is_game_over() and move_count < 20:
            legal = engine.get_legal_moves()
            if not legal:
                break
            import random
            move = random.choice(legal)
            engine.make_move(move)
            move_count += 1

        result = engine.get_result() or '1/2-1/2'
        winner = 'white' if result == '1-0' else ('black' if result == '0-1' else None)
        payout = organizer.close_game(game_id, winner)
        print(f'Result: {result} | White: {payout[\"white\"]:.1f} | Black: {payout[\"black\"]:.1f}')
        print(f'Wallets — White: {wallets.get_balance(\"white\"):.1f} | Black: {wallets.get_balance(\"black\"):.1f}')

    print('\nDemo complete.')

asyncio.run(run_demo())
"
        ;;

    *)
        echo "Unknown mode: $MODE"
        echo "Valid modes: backend | train | selfplay | download | demo"
        exit 1
        ;;
esac
