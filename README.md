---
title: ChessEcon
emoji: ♟️
colorFrom: indigo
colorTo: yellow
sdk: docker
app_port: 8000
tags:
  - openenv
  - reinforcement-learning
  - chess
  - multi-agent
  - grpo
  - rl-environment
  - economy
  - two-player
  - game
  - textarena
  - llm-training
license: apache-2.0
---

**Dashboard:** https://chessecon.adaboost.ai

<div align="center">

# ♟️ ChessEcon

### Multi-Agent Chess Economy · OpenEnv 0.1 · GRPO Live Training

[![OpenEnv](https://img.shields.io/badge/OpenEnv-0.1-blueviolet?style=flat-square)](https://github.com/huggingface/openenv)
[![TextArena](https://img.shields.io/badge/TextArena-compatible-orange?style=flat-square)](https://github.com/textarena)
[![License](https://img.shields.io/badge/license-Apache--2.0-green?style=flat-square)](LICENSE)
[![Hackathon](https://img.shields.io/badge/Hackathon-2026-gold?style=flat-square)](https://adaboost.io)

**Live API:** `https://chessecon.adaboost.io`
**Dashboard:** `https://chessecon-ui.adaboost.io`
**Swagger:** `https://chessecon.adaboost.io/docs`
**env_info:** `https://chessecon.adaboost.io/env/env_info`

</div>

---

## Overview

ChessEcon is a **two-player LLM chess environment** where agents compete for economic stakes, fully compliant with the [OpenEnv 0.1](https://github.com/huggingface/openenv) specification.

Two language models play chess head-to-head. Each game costs an entry fee. The winner earns a prize pool. The White agent trains **live** using **GRPO** (Group Relative Policy Optimisation) — every game updates the policy weights in real-time. A Bloomberg-style dashboard streams all activity via WebSocket.

| Agent | Model | Role |
|---|---|---|
| ♔ White | `Qwen/Qwen2.5-0.5B-Instruct` | **Trainable** — GRPO updates every game |
| ♚ Black | `meta-llama/Llama-3.2-1B-Instruct` | **Fixed opponent** — frozen weights |

---

## OpenEnv 0.1 API

All endpoints are compatible with TRL, verl, SkyRL, and any OpenEnv 0.1 trainer.

| Endpoint | Method | Description |
|---|---|---|
| `/env/reset` | `POST` | Start new episode · deduct entry fees · return initial observation |
| `/env/step` | `POST` | Apply one move (UCI or SAN) · return reward + next observation |
| `/env/state` | `GET` | Read current board state — non-destructive |
| `/env/env_info` | `GET` | Environment metadata for HF Hub discoverability |
| `/ws` | `WebSocket` | Real-time event stream (moves, rewards, GRPO metrics) |
| `/health` | `GET` | Health check + model load status |
| `/docs` | `GET` | Interactive Swagger UI |

---

## Quick Start

```python
import httpx

BASE = "https://chessecon.adaboost.io"

# 1. Start a new episode
reset = httpx.post(f"{BASE}/env/reset").json()
print(reset["observation"]["fen"])              # starting position
print(reset["observation"]["legal_moves_uci"])  # all legal moves in UCI

# 2. Play a move (UCI or SAN accepted)
step = httpx.post(f"{BASE}/env/step", json={"action": "e2e4"}).json()
print(step["observation"]["fen"])   # updated board
print(step["reward"])               # per-step reward signal
print(step["terminated"])           # True when game ends
print(step["truncated"])            # True if move limit reached

# 3. Inspect current state (read-only)
state = httpx.get(f"{BASE}/env/state").json()
print(state["step_count"])          # moves played so far
print(state["status"])              # "active" | "terminated" | "idle"

# 4. Environment metadata
info = httpx.get(f"{BASE}/env/env_info").json()
print(info["openenv_version"])      # "0.1"
print(info["agents"])               # model IDs for white/black
```

---

## Drop-in Client (TRL / verl / SkyRL)

```python
import httpx

class ChessEconEnv:
    """
    OpenEnv 0.1 client for ChessEcon.
    Compatible with TRL, verl, SkyRL, and any gym-style RL trainer.
    """

    def __init__(self, base_url: str = "https://chessecon.adaboost.io"):
        self.base = base_url.rstrip("/")
        self.http = httpx.Client(timeout=30)

    def reset(self, seed: int | None = None) -> tuple[dict, dict]:
        payload = {"seed": seed} if seed is not None else {}
        r = self.http.post(f"{self.base}/env/reset", json=payload)
        r.raise_for_status()
        d = r.json()
        return d["observation"], d["info"]

    def step(self, action: str) -> tuple[dict, float, bool, bool, dict]:
        """
        Args:
            action: Move in UCI (e.g. "e2e4") or SAN (e.g. "e4")
        Returns:
            (observation, reward, terminated, truncated, info)
        """
        r = self.http.post(f"{self.base}/env/step", json={"action": action})
        r.raise_for_status()
        d = r.json()
        return (d["observation"], d["reward"], d["terminated"], d["truncated"], d["info"])

    def state(self) -> dict:
        return self.http.get(f"{self.base}/env/state").json()

    def env_info(self) -> dict:
        return self.http.get(f"{self.base}/env/env_info").json()

    def close(self):
        self.http.close()


# Example: random rollout
import random

env = ChessEconEnv()
obs, info = env.reset()
total_reward = 0.0

while True:
    action = random.choice(obs["legal_moves_uci"])  # replace with your policy
    obs, reward, terminated, truncated, info = env.step(action)
    total_reward += reward
    if terminated or truncated:
        print(f"Game over | result={info.get('result')} | total_reward={total_reward:.3f}")
        break

env.close()
```

---

## Observation Schema

Every response from `/env/reset`, `/env/step`, and `/env/state` contains a `ChessObservation`:

```json
{
  "observation": {
    "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
    "turn": "black",
    "move_number": 1,
    "last_move_uci": "e2e4",
    "last_move_san": "e4",
    "legal_moves_uci": ["e7e5", "d7d5", "g8f6", "..."],
    "is_check": false,
    "wallet_white": 90.0,
    "wallet_black": 90.0,
    "white_model": "Qwen/Qwen2.5-0.5B-Instruct",
    "black_model": "meta-llama/Llama-3.2-1B-Instruct",
    "info": {}
  }
}
```

### `/env/step` Response

```json
{
  "observation": { "...": "ChessObservation — see above" },
  "reward": 0.01,
  "terminated": false,
  "truncated": false,
  "info": { "san": "e4", "uci": "e2e4", "move_number": 1 }
}
```

### `/env/state` Response

```json
{
  "observation": { "...": "ChessObservation — see above" },
  "episode_id": "ep-42",
  "step_count": 1,
  "status": "active",
  "info": {}
}
```

### `/env/env_info` Response

```json
{
  "openenv_version": "0.1",
  "environment_id": "chessecon-v1",
  "name": "ChessEcon",
  "description": "Multi-agent chess economy with live GRPO training",
  "action_space": "text",
  "observation_space": "text",
  "reward_range": [-1.0, 1.0],
  "max_steps": 40,
  "agents": {
    "white": "Qwen/Qwen2.5-0.5B-Instruct",
    "black": "meta-llama/Llama-3.2-1B-Instruct"
  },
  "tags": ["chess", "multi-agent", "economy", "grpo", "openenv"]
}
```

---

## Reward Structure

Per-step rewards are issued after every move. Terminal rewards are issued at game end.

| Event | Reward | Type |
|---|---|---|
| Legal move played | `+0.01` | Per-step |
| Move delivers check | `+0.05` | Per-step bonus |
| Capture | `+0.10` | Per-step bonus |
| Win (checkmate / material adj.) | `+1.00` | Terminal |
| Loss | `-1.00` | Terminal |
| Draw | `0.00` | Terminal |
| Illegal move attempted | `-0.10` | Per-step penalty |

> **Combined reward formula:**
> `R = 0.4 × game_reward + 0.6 × economic_reward`
>
> `economic_reward = (prize_income − entry_fee) / entry_fee`

### Material Adjudication

Games reaching the move limit are adjudicated by material count (Q=9, R=5, B=3, N=3, P=1). The side with superior material wins — ensuring every game produces a decisive `+1` / `-1` signal for GRPO training.

---

## Economy Model

Both agents pay into a shared prize pool each game, creating zero-sum economic incentives aligned with game outcome.

| Parameter | Value |
|---|---|
| Starting wallet | 100 units |
| Entry fee | 10 units per agent per game |
| Prize pool | 18 units (90% of 2 × entry fee) |
| Win payout | +18 units → net **+8** |
| Draw payout | +9 units each → net **−1** |
| Loss payout | +0 units → net **−10** |

---

## GRPO Training

The White agent (`Qwen2.5-0.5B`) trains live using Group Relative Policy Optimisation:

```
Per-game update:
  1. White generates moves: sample log π_θ(a | s) at each position
  2. Reference log-probs log π_ref(a | s) computed from frozen snapshot
  3. Terminal reward R ∈ {+1, 0, −1} from material adjudication
  4. Advantage: A = (R − mean_R) / (std_R + ε)
  5. Clipped surrogate: L = −min(ratio·A, clip(ratio, 0.8, 1.2)·A)
  6. KL penalty: KL(π_θ ∥ π_ref), diff clamped to [−10, 10]
  7. Total: L_total = L + β·KL,  β = 0.04
  8. AdamW update, grad-norm clip max_norm=1.0
```

| Hyperparameter | Value |
|---|---|
| LoRA rank | 8 |
| LoRA target modules | `q_proj`, `v_proj` |
| Learning rate | `1e-5` |
| KL coefficient β | `0.04` |
| Update frequency | Every 1 game |
| Checkpoint frequency | Every 100 steps |
| Optimizer | AdamW |
| Gradient clip | `max_norm=1.0` |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│               External RL Trainers                           │
│         TRL · verl · SkyRL · custom OpenEnv clients         │
└──────────────────────┬───────────────────────────────────────┘
                       │ HTTP  POST /env/reset  /env/step
                       │       GET  /env/state  /env/env_info
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                  FastAPI WebSocket Server                    │
│  ┌──────────────────────┐   ┌───────────────────────────┐   │
│  │  OpenEnv 0.1 Router  │   │  WebSocket  /ws           │   │
│  │  asyncio.Lock        │   │  broadcast() → dashboard  │   │
│  └──────────┬───────────┘   └───────────────────────────┘   │
│             │                                               │
│  ┌──────────▼───────────┐   ┌───────────────────────────┐   │
│  │   Chess Engine        │   │   Economy Engine          │   │
│  │   python-chess        │   │   Wallets · Entry fees    │   │
│  │   FEN · UCI · SAN     │   │   Prize pool · P&L        │   │
│  └──────────┬───────────┘   └───────────────────────────┘   │
│             │                                               │
│  ┌──────────▼───────────┐   ┌───────────────────────────┐   │
│  │  ♔ White Agent        │   │  ♚ Black Agent (fixed)    │   │
│  │  Qwen2.5-0.5B         │   │  Llama-3.2-1B             │   │
│  │  LoRA r=8             │   │  Frozen weights           │   │
│  └──────────┬───────────┘   └───────────────────────────┘   │
│             │                                               │
│  ┌──────────▼───────────┐                                   │
│  │  GRPO Trainer         │──▶  /checkpoints/step_N         │
│  │  PPO-clip + KL        │                                   │
│  │  AdamW  LR=1e-5       │                                   │
│  └──────────────────────┘                                   │
└──────────────────────┬───────────────────────────────────────┘
                       │ WebSocket broadcast()
                       ▼
┌──────────────────────────────────────────────────────────────┐
│              React Dashboard (nginx)                         │
│  Live Board · Wallet History · GRPO Metrics · P&L Chart     │
│  Architecture View · Live Event Feed                        │
└──────────────────────────────────────────────────────────────┘
```

---

## WebSocket Event Stream

Connect to `wss://chessecon.adaboost.io/ws` for real-time events:

```python
import asyncio, json, websockets

async def watch():
    async with websockets.connect("wss://chessecon.adaboost.io/ws") as ws:
        async for raw in ws:
            msg = json.loads(raw)
            match msg["type"]:
                case "move":
                    print(f"{msg['data']['player']} plays {msg['data']['move']}")
                case "game_end":
                    d = msg["data"]
                    print(f"Game over: {d['result']} | reward={d['reward']}")
                case "training_step":
                    d = msg["data"]
                    print(f"GRPO step {d['step']} | loss={d['loss']:.4f} kl={d['kl_div']:.4f}")
                case "status":
                    print(f"Snapshot: game #{msg['data']['game_id']}")

asyncio.run(watch())
```

### Event Types

| Type | Key Fields |
|---|---|
| `status` | `game_id`, `wallet_white`, `wallet_black`, `grpo_step` |
| `game_start` | `game_id`, `wallet_white`, `wallet_black`, `prize_pool` |
| `move` | `player`, `move`, `uci`, `fen`, `move_number` |
| `game_end` | `result`, `reward`, `wallet_white`, `wallet_black`, `net_pnl_white` |
| `training_step` | `step`, `loss`, `reward`, `kl_div`, `win_rate` |

---

## Models

ChessEcon uses two publicly available HuggingFace models:

| Agent | Model Card | Size | Local Path |
|---|---|---|---|
| ♔ White (trainable) | [Qwen/Qwen2.5-0.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct) | 943 MB | `training/models/Qwen_Qwen2.5-0.5B-Instruct/` |
| ♚ Black (fixed) | [meta-llama/Llama-3.2-1B-Instruct](https://huggingface.co/meta-llama/Llama-3.2-1B-Instruct) | 2.4 GB | `training/models/meta-llama_Llama-3.2-1B-Instruct/` |

> **Note:** `Llama-3.2-1B-Instruct` requires a HuggingFace account with Meta's license accepted at [meta-llama/Llama-3.2-1B-Instruct](https://huggingface.co/meta-llama/Llama-3.2-1B-Instruct). Generate a token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).

### Download Commands

**Option A — Python (recommended):**

```python
from huggingface_hub import snapshot_download

# White agent — Qwen2.5-0.5B-Instruct (no token required)
snapshot_download(
    repo_id="Qwen/Qwen2.5-0.5B-Instruct",
    local_dir="training/models/Qwen_Qwen2.5-0.5B-Instruct",
    local_dir_use_symlinks=False,
)

# Black agent — Llama-3.2-1B-Instruct (requires HF token + Meta license)
snapshot_download(
    repo_id="meta-llama/Llama-3.2-1B-Instruct",
    local_dir="training/models/meta-llama_Llama-3.2-1B-Instruct",
    local_dir_use_symlinks=False,
    token="hf_YOUR_TOKEN_HERE",
)
```

**Option B — huggingface-cli:**

```bash
# Install CLI if needed
pip install huggingface_hub

# White agent (no token)
huggingface-cli download Qwen/Qwen2.5-0.5B-Instruct \
  --local-dir training/models/Qwen_Qwen2.5-0.5B-Instruct

# Black agent (token required)
huggingface-cli login   # paste your HF token when prompted
huggingface-cli download meta-llama/Llama-3.2-1B-Instruct \
  --local-dir training/models/meta-llama_Llama-3.2-1B-Instruct
```

**Option C — git lfs:**

```bash
git lfs install

# White agent
git clone https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct \
  training/models/Qwen_Qwen2.5-0.5B-Instruct

# Black agent (must be logged in: huggingface-cli login)
git clone https://huggingface.co/meta-llama/Llama-3.2-1B-Instruct \
  training/models/meta-llama_Llama-3.2-1B-Instruct
```

### Verify Downloads

```bash
# Expected files after download:
ls training/models/Qwen_Qwen2.5-0.5B-Instruct/
# config.json  generation_config.json  model.safetensors  tokenizer*.json  ...

ls training/models/meta-llama_Llama-3.2-1B-Instruct/
# config.json  generation_config.json  model.safetensors  tokenizer*.json  ...

# Check sizes
du -sh training/models/Qwen_Qwen2.5-0.5B-Instruct/model.safetensors
# → 943M

du -sh training/models/meta-llama_Llama-3.2-1B-Instruct/model.safetensors
# → 2.4G
```

---

## Running Locally

```bash
git clone https://huggingface.co/spaces/adaboost-ai/chessecon
cd chessecon

# 1. Download models (see Models section above)

# 2. Start backend + dashboard
docker-compose up -d

# API:       http://localhost:8008
# Dashboard: http://localhost:3006
# Docs:      http://localhost:8008/docs
```

### Key Environment Variables

| Variable | Default | Description |
|---|---|---|
| `WHITE_MODEL` | `/models/Qwen_...` | Path to White model |
| `BLACK_MODEL` | `/models/meta-llama_...` | Path to Black model |
| `DEVICE` | `cuda` | `cuda` or `cpu` |
| `MAX_MOVES` | `15` | Moves before material adjudication |
| `MOVE_DELAY` | `0.05` | Seconds between moves |
| `ENTRY_FEE` | `10` | Units per agent per game |
| `PRIZE_POOL_FRACTION` | `0.9` | Fraction of 2×entry returned as prize |
| `GRPO_LR` | `1e-5` | AdamW learning rate |
| `GRPO_KL_COEFF` | `0.04` | KL divergence penalty β |
| `LORA_RANK` | `8` | LoRA adapter rank |

---

## Hardware Requirements

| Config | Minimum |
|---|---|
| CPU-only | 8 GB RAM · `DEVICE=cpu` |
| GPU (recommended) | 8 GB VRAM · CUDA 11.8+ |
| Dev server | 4× NVIDIA RTX 3070 (lambda-quad) |

---

## Citation

```bibtex
@software{chessecon2026,
  title   = {ChessEcon: Multi-Agent Chess Economy with Live GRPO Training},
  author  = {AdaBoost AI},
  year    = {2026},
  url     = {https://huggingface.co/spaces/adaboost-ai/chessecon},
  note    = {OpenEnv 0.1 · TextArena + Meta OpenEnv · Hackathon 2026}
}
```

---

## Links

- **Live Dashboard:** [chessecon-ui.adaboost.io](https://chessecon-ui.adaboost.io)
- **API + Swagger:** [chessecon.adaboost.io/docs](https://chessecon.adaboost.io/docs)
- **AdaBoost AI:** [adaboost.io](https://adaboost.io)
- **OpenEnv Spec:** [github.com/huggingface/openenv](https://github.com/huggingface/openenv)
- **GRPO Paper:** [DeepSeek-R1 (arXiv 2501.12599)](https://arxiv.org/abs/2501.12599)

---

<div align="center">
Built by <a href="https://adaboost.io">AdaBoost AI</a> · TextArena + Meta OpenEnv + GRPO · Hackathon 2026
</div>
