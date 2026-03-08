---
title: ChessEcon
emoji: ♟️
colorFrom: indigo
colorTo: purple
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
license: apache-2.0
---

# ♟️ ChessEcon — OpenEnv 0.1 Compliant Chess Economy Environment

> **Self-hosted environment** — the live API runs on AdaBoost AI infrastructure.
> Update this URL if the domain changes.

**Live API base URL:** `https://chessecon.adaboost.io`
**env_info:** `https://chessecon.adaboost.io/env/env_info`
**Dashboard:** `https://chessecon-ui.adaboost.io`
**Swagger docs:** `https://chessecon.adaboost.io/docs`

---

**Two competing LLM agents play chess for economic stakes.**
White = `Qwen/Qwen2.5-0.5B-Instruct` (trainable) | Black = `meta-llama/Llama-3.2-1B-Instruct` (fixed)

Both agents pay an entry fee each game. The winner earns a prize pool.
The White agent is trained live with **GRPO** (Group Relative Policy Optimisation).

---

## OpenEnv 0.1 API

This environment is fully compliant with the [OpenEnv 0.1 spec](https://github.com/huggingface/openenv).

| Endpoint | Method | Description |
|---|---|---|
| `/env/reset` | `POST` | Start a new episode, deduct entry fees, return initial observation |
| `/env/step` | `POST` | Apply one move (UCI or SAN), return reward + next observation |
| `/env/state` | `GET` | Inspect current board state — read-only, no side effects |
| `/env/env_info` | `GET` | Environment metadata for HF Hub discoverability |
| `/ws` | `WS` | Real-time event stream for the live dashboard |
| `/health` | `GET` | Health check + model load status |
| `/docs` | `GET` | Interactive Swagger UI |

---

## Quick Start

```python
import httpx

BASE = "https://chessecon.adaboost.io"

# 1. Start a new episode
reset = httpx.post(f"{BASE}/env/reset").json()
print(reset["observation"]["fen"])             # starting FEN
print(reset["observation"]["legal_moves_uci"]) # all legal moves

# 2. Play moves
step = httpx.post(f"{BASE}/env/step", json={"action": "e2e4"}).json()
print(step["observation"]["fen"])   # board after move
print(step["reward"])               # per-step reward signal
print(step["terminated"])           # True if game is over
print(step["truncated"])            # True if move limit hit

# 3. Inspect state (non-destructive)
state = httpx.get(f"{BASE}/env/state").json()
print(state["step_count"])          # moves played so far
print(state["status"])              # "active" | "terminated" | "idle"

# 4. Environment metadata
info = httpx.get(f"{BASE}/env/env_info").json()
print(info["openenv_version"])      # "0.1"
print(info["agents"])               # white/black model IDs
```

### Drop-in Client for TRL / verl / SkyRL

```python
import httpx

class ChessEconClient:
    """OpenEnv 0.1 client — compatible with TRL, verl, SkyRL."""

    def __init__(self, base_url: str = "https://chessecon.adaboost.io"):
        self.base = base_url.rstrip("/")
        self.client = httpx.Client(timeout=30)

    def reset(self, seed=None):
        payload = {"seed": seed} if seed is not None else {}
        r = self.client.post(f"{self.base}/env/reset", json=payload)
        r.raise_for_status()
        data = r.json()
        return data["observation"], data["info"]

    def step(self, action: str):
        r = self.client.post(f"{self.base}/env/step", json={"action": action})
        r.raise_for_status()
        data = r.json()
        return (
            data["observation"],
            data["reward"],
            data["terminated"],
            data["truncated"],
            data["info"],
        )

    def state(self):
        return self.client.get(f"{self.base}/env/state").json()

    def env_info(self):
        return self.client.get(f"{self.base}/env/env_info").json()


# Usage
env = ChessEconClient()
obs, info = env.reset()

while True:
    action = obs["legal_moves_uci"][0]          # replace with your policy
    obs, reward, terminated, truncated, info = env.step(action)
    if terminated or truncated:
        break
```

---

## Observation Schema

Every response wraps a `ChessObservation` object:

```json
{
  "observation": {
    "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
    "turn": "black",
    "move_number": 1,
    "last_move_uci": "e2e4",
    "last_move_san": "e4",
    "legal_moves_uci": ["e7e5", "d7d5", "g8f6"],
    "is_check": false,
    "wallet_white": 90.0,
    "wallet_black": 90.0,
    "white_model": "Qwen/Qwen2.5-0.5B-Instruct",
    "black_model": "meta-llama/Llama-3.2-1B-Instruct",
    "info": {}
  }
}
```

### Step Response

```json
{
  "observation": { "...": "see above" },
  "reward": 0.01,
  "terminated": false,
  "truncated": false,
  "info": { "san": "e4", "uci": "e2e4", "move_number": 1 }
}
```

### State Response

```json
{
  "observation": { "...": "see above" },
  "episode_id": "ep-42",
  "step_count": 1,
  "status": "active",
  "info": {}
}
```

---

## Reward Structure

| Event | Reward | Notes |
|---|---|---|
| Legal move | `+0.01` | Every valid move |
| Move gives check | `+0.05` | Additional bonus |
| Capture | `+0.10` | Additional bonus |
| Win (checkmate) | `+1.00` | Terminal |
| Loss | `-1.00` | Terminal |
| Draw | `0.00` | Terminal |
| Illegal move | `-0.10` | Episode continues |

Combined reward: `0.4 × game_reward + 0.6 × economic_reward`

---

## Economy Model

| Parameter | Value |
|---|---|
| Starting wallet | 100 units |
| Entry fee | 10 units per agent per game |
| Prize pool | 18 units (90% of 2 × entry fee) |
| Draw refund | 5 units each |

---

## Architecture

```
External RL Trainers (TRL / verl / SkyRL)
          │  HTTP
          ▼
┌─────────────────────────────────────────────┐
│         OpenEnv 0.1 HTTP API                │
│  POST /env/reset  POST /env/step            │
│  GET  /env/state  GET  /env/env_info        │
│         asyncio.Lock — thread safe          │
└──────────────┬──────────────────────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
┌─────────────┐  ┌──────────────┐
│ Chess Engine│  │Economy Engine│
│ python-chess│  │Wallets · Fees│
│ FEN · UCI   │  │Prize Pool    │
└──────┬──────┘  └──────────────┘
       │
  ┌────┴─────┐
  ▼          ▼
♔ Qwen     ♚ Llama
0.5B       1B
GRPO↑      Fixed
```

---

## Hardware

Self-hosted on AdaBoost AI infrastructure:
- 4× NVIDIA RTX 3070 (lambda-quad)
- Models loaded in 4-bit quantization

Built by [AdaBoost AI](https://adaboost.io) · Hackathon 2026
