# ChessEcon v2 — Monorepo TODO

## Phase 1: Scaffold
- [x] Create monorepo directory structure
- [x] Write shared/models.py (Pydantic data models shared across backend + training)
- [x] Write .env.example with all keys documented

## Phase 2: Backend (Python FastAPI)
- [x] backend/main.py — FastAPI app entry point, mounts static frontend
- [x] backend/chess/engine.py — python-chess game logic
- [x] backend/api/game_router.py — game management REST API
- [x] backend/economy/ledger.py — wallets, tournament organizer, transactions
- [x] backend/agents/complexity.py — position complexity analyzer
- [x] backend/agents/claude_coach.py — Anthropic API integration (minimal usage)
- [x] backend/api/websocket.py — WebSocket event bus (game events, training metrics)
- [x] backend/api/training_router.py — training status REST API
- [x] backend/requirements.txt

## Phase 3: Training (Standalone Python)
- [x] training/config.py — training configuration from .env
- [x] training/self_play.py — self-play game loop, episode collection
- [x] training/trainers/grpo.py — GRPO trainer
- [x] training/trainers/ppo.py — PPO trainer
- [x] training/trainers/rloo.py — RLOO trainer
- [x] training/trainers/base.py — abstract base trainer
- [x] training/model_loader.py — HuggingFace model download + load
- [x] training/reward.py — combined chess + economic reward function
- [x] training/run.py — training entry point CLI
- [x] training/requirements.txt

## Phase 4: Frontend (React TypeScript)
- [x] frontend/package.json + vite.config.ts
- [x] frontend/src/lib/useBackendWS.ts — WebSocket client hook (real backend mode)
- [x] frontend/src/lib/simulation.ts — browser simulation (offline mode)
- [x] frontend/src/components/ChessBoard.tsx — live chess board
- [x] frontend/src/components/TrainingCharts.tsx — GRPO metrics charts
- [x] frontend/src/components/WalletChart.tsx — wallet history chart
- [x] frontend/src/components/EconomicPerformance.tsx — P&L chart (full-width bottom row)
- [x] frontend/src/components/EventFeed.tsx — live event log
- [x] frontend/src/components/Panel.tsx — shared panel wrapper
- [x] frontend/src/pages/Home.tsx — main dashboard with simulation + backend modes

## Phase 5: Docker
- [x] Dockerfile — multi-stage: frontend build → backend serve
- [x] docker-compose.yml — app + trainer services
- [x] docker-compose.gpu.yml — GPU override for trainer
- [x] .env.example — all keys documented (ANTHROPIC_API_KEY, HF_TOKEN, PLAYER_MODEL, RL_METHOD)
- [x] Makefile — common commands
- [x] .dockerignore
- [x] docker-entrypoint.sh — model download on startup

## Phase 6: Validation
- [x] All 5 unit tests pass (ChessEngine, Economy, Complexity, Models, TrainingConfig)
- [x] README.md written with full setup instructions
- [x] Project packaged as zip
