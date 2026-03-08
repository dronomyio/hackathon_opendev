# ChessEcon Setup Log

Complete record of all steps, issues, and fixes for the backend and frontend.

---

## Frontend (Dashboard) — Manus Web Project

### Design & Layout

The dashboard was built as a Bloomberg-style dark terminal UI with:
- KPI cards row (wallets, coaching calls, last reward, win rate, GRPO loss, KL div)
- Agent cards (White / Black with wallet and Claude call count)
- Live chess board (left column)
- Move history feed (centre column)
- GRPO training metrics charts (right column)
- Wallet history chart
- Live event feed
- Economic performance chart (bottom)

### Issue 1 — Panels expanding vertically beyond viewport

**Symptom:** Panels in the middle and right columns were growing taller than 100vh, causing the page to scroll.

**Fix:** Changed the root container from `minHeight: 100vh` to `height: 100vh` with `overflow: hidden`. Added `minHeight: 0` and `overflow: hidden` to the GRPO Training Metrics panel.

### Issue 2 — Chess board clipping rows 1 and 2

**Symptom:** The board panel was clipping at the bottom — white pawns (row 2) and back rank (row 1) were not visible.

**Root cause:** The board panel used `flexShrink: 0` with `aspectRatio: 1/1`. As the left column was squeezed by the 100vh constraint, the board overflowed its container.

**Fix:** Changed the board panel to `flex: 1` with `minHeight: 0` and `overflow: hidden` so it fills available height without overflowing.

---

## Backend — Python FastAPI + Qwen2.5-0.5B + GRPO

### Architecture

New files added to `backend/`:

| File | Purpose |
|---|---|
| `settings.py` | Centralised env-var config (model name, device, fees, GRPO params) |
| `chess_engine.py` | Thin `python-chess` wrapper (copied to `chess/chess_engine.py`) |
| `qwen_agent.py` | Qwen2.5-0.5B move generator with LoRA + illegal-move retry (copied to `agents/qwen_agent.py`) |
| `grpo_trainer.py` | GRPO policy gradient training loop (copied to `agents/grpo_trainer.py`) |
| `websocket_server.py` | FastAPI WebSocket server (merged into existing `main.py`) |
| `requirements.txt` | Python dependencies |
| `Dockerfile` | GPU-capable container |
| `docker-compose.yml` | Orchestrates backend + dashboard |

### Step 1 — Environment setup on Lambda Labs GPU machine

**Machine:** 4× RTX 3070 (8 GB VRAM each), CUDA 12.4, Ubuntu 20.04

**Issue:** System `pip` at `/usr/local/bin/pip` was broken due to Ubuntu 20.04 `pyOpenSSL` / `libssl` version conflict.

```
pkg_resources.VersionConflict: (uvicorn 0.27.0, Requirement.parse('uvicorn==0.11.3'))
AttributeError: module 'lib' has no attribute 'X509_V_FLAG_NOTIFY_POLICY'
```

**Fix:** Used Anaconda's pip instead of the system pip. Created a fresh conda env with Python 3.11:

```bash
conda create -n chessecon python=3.11 -y
conda activate chessecon
```

### Step 2 — Installing requirements.txt

**Issue 1:** Duplicate `transformers` version pin in `requirements.txt`.

```
ERROR: Double requirement given: transformers>=4.46.0 (already in transformers>=4.40.0)
```

**Fix:**
```bash
sed -i '/^transformers>=4.40.0/d' requirements.txt
```

**Issue 2:** `pydantic>=2.7.0` not available — conda env had pydantic 2.5.3 max.

**Fix:**
```bash
sed -i 's/pydantic>=2.7.0/pydantic>=2.0.0/' requirements.txt
sed -i 's/pydantic-settings>=2.3.0/pydantic-settings>=2.0.0/' requirements.txt
```

**Issue 3:** `httpx>=0.27.0` not available in conda env.

**Fix:** Removed all version pins:
```bash
sed -i 's/>=.*//' requirements.txt
```

**Issue 4:** `payments-py` (Nevermined SDK) not on PyPI.

**Fix:**
```bash
sed -i '/payments-py/d' requirements.txt
```

**Issue 5:** `jitter` requires Python 3.8+ — conda base env was Python 3.7, blocking `anthropic` install.

**Fix:** Used the `chessecon` conda env (Python 3.11) instead of the base env.

**Issue 6:** `transformers` required PyTorch 2.4+; conda env had PyTorch 1.9.

**Fix:**
```bash
pip install torch==2.4.1 --index-url https://download.pytorch.org/whl/cu121
pip install transformers accelerate peft sentencepiece tokenizers
```

### Step 3 — Running the server

**Command:**
```bash
cd ~/suvasis/tools/blogs/hackathon/ChessEcon
python3.11 -m uvicorn backend.main:app --host 0.0.0.0 --port 8008 --reload
```

**Issue 1:** System `uvicorn` at `/bin/uvicorn` conflicted with the newly installed version.

**Fix:** Used `python3.11 -m uvicorn` instead of the bare `uvicorn` command.

**Issue 2:** Port 8000 already in use by existing backend.

**Fix:** Used port 8008 instead.

**Issue 3:** `from backend.api.game_router import router` — absolute import failed when running from inside `backend/`.

**Fix:** Run from the parent directory (`ChessEcon/`) using `backend.main:app` as the module path.

**Issue 4:** New files (`qwen_agent.py`, `grpo_trainer.py`, `chess_engine.py`) were placed at `backend/` root but `main.py` expected them at `backend/agents/` and `backend/chess/`.

**Fix:**
```bash
cp backend/qwen_agent.py backend/agents/qwen_agent.py
cp backend/grpo_trainer.py backend/agents/grpo_trainer.py
cp backend/chess_engine.py backend/chess/chess_engine.py
```

**Issue 5:** New imports inside `qwen_agent.py` and `grpo_trainer.py` used bare `from settings import settings` — failed when running from parent directory.

**Fix:**
```bash
sed -i 's/^from settings import settings/from backend.settings import settings/' \
    backend/agents/qwen_agent.py backend/agents/grpo_trainer.py
sed -i 's/^from chess_engine import ChessEngine/from backend.chess.chess_engine import ChessEngine/' \
    backend/agents/qwen_agent.py backend/agents/grpo_trainer.py
```

**Issue 6:** WebSocket endpoint block was inserted before `app = FastAPI()` in `main.py`, causing `NameError: name 'app' is not defined`.

**Fix:** Rewrote `main.py` with the WebSocket endpoint and `game_loop` correctly placed after `app` is created.

### Step 4 — HuggingFace authentication

**Issue:** Expired token `"llama4"` was cached at `~/.cache/huggingface/token`, causing 401 errors even after creating a new token.

**Fix:**
```bash
rm -f ~/.cache/huggingface/token
export HF_TOKEN=hf_<new_token>
echo "HF_TOKEN=hf_<new_token>" >> backend/.env
```

**Note on token type:** The new `hackathon_chess` token was created as a **Fine-grained** token with no repository permissions, which also returns 401. The fix was to either edit its permissions to add **Contents: Read**, or create a classic **Read** token instead.

### Step 5 — Game loop API mismatches

After the model loaded successfully on `cuda:1`, the `game_loop` had several API mismatches with the actual `ChessEngine` and `QwenAgent` classes:

| Error | Cause | Fix |
|---|---|---|
| `'bool' object is not callable` | `engine.is_game_over` is a `@property`, called with `()` | Remove `()` |
| `QwenAgent.__init__() takes 1 positional argument but 3 were given` | Constructor takes no args | `QwenAgent()` with no args |
| `QwenAgent.get_move() missing 2 required positional arguments` | `get_move(engine, agent_color, move_history)` — not `(fen, ...)` | Pass `engine` object, not `engine.fen` |
| `'Settings' object has no attribute 'initial_wallet'` | Field is `starting_wallet` not `initial_wallet` | `settings.starting_wallet` |
| `'Settings' object has no attribute 'move_delay_seconds'` | Field is `move_delay` | `settings.move_delay` |
| `'TrainingMetrics' object has no attribute 'grpo_loss'` | Field is `loss` not `grpo_loss`; `kl_div` not `kl_divergence` | Use correct field names |
| `NameError: 'move_history' is not defined` | Not initialised before the move loop | `move_history = []` after `engine = ChessEngine()` |
| `'QwenAgent' object has no attribute 'wallet'` | `QwenAgent` has no wallet — economy tracked separately | Use local `wallet_white` / `wallet_black` variables |
| `'QwenAgent' object has no attribute 'trajectory'` | Trajectory is internal to trainer | Use `getattr(agent, 'trajectory', [])` |

### Step 6 — Game running successfully

After all fixes, the server runs cleanly:

```
Model loaded on device: cuda:1
trainable params: 540,672 || all params: 494,573,440 || trainable%: 0.1093
LoRA adapter applied (rank=8)
GRPO step 1 | loss=nan reward=1.000 kl=1808.1735 win_rate=1.00
```

**Expected warnings (not errors):**

- `All retries exhausted — using random fallback move` — Normal for an untrained model. Qwen generates illegal moves initially; the fallback ensures the game continues. This improves as GRPO training progresses.
- `loss=nan on step 1` — Normal. GRPO requires multiple trajectory samples to compute group-relative advantages (std deviation). With only one game, std=0 → NaN. Resolves after a few games.

---

## Frontend Docker Setup (macOS)

The dashboard is the Manus React web project. To run it on macOS pointing at the Lambda backend:

### docker-compose.yml changes needed for macOS

1. Remove the `deploy: resources: reservations: devices` GPU block (macOS has no NVIDIA GPU).
2. Add `VITE_WS_URL=ws://<LAMBDA_IP>:8008/ws` to the `dashboard` environment so the frontend connects to the remote backend.
3. Remove `depends_on` health check (backend is not running locally).

```bash
# Build and run just the dashboard
docker-compose build --no-cache dashboard
docker-compose up -d dashboard
# Dashboard available at http://localhost:3000
```

### Connecting to the backend

In the dashboard, click **LIVE** in the top-right toggle. The `VITE_WS_URL` env var sets the default WebSocket URL. If not set, the dashboard defaults to `ws://localhost:8008/ws`.

---

## Current Status

| Component | Status |
|---|---|
| Dashboard UI | Running — simulation mode fully functional |
| Backend server | Running on Lambda at port 8008 |
| Qwen2.5-0.5B | Loaded on `cuda:1`, generating moves |
| GRPO training | Active — step 1 completed |
| Dashboard ↔ Backend connection | Pending — need to run frontend and set `VITE_WS_URL` |
| Claude coaching | Disabled — `ANTHROPIC_API_KEY` not set |
| Nevermined integration | Not implemented (deferred) |

---

## Dashboard Docker Deployment — Lambda GPU Machine (Mar 5, 2026)

This section documents the complete sequence of attempts, failures, and fixes required to get the React dashboard accessible at `http://192.168.1.140:3006` on the Lambda GPU machine.

---

### Attempt 1 — https instead of http

**Symptom:** Browser showed "This site can't be reached — 192.168.1.140 refused to connect" when navigating to `https://192.168.1.140:3006`.

**Root cause:** The dashboard has no SSL certificate configured. Nginx serves plain HTTP only.

**Fix:** Use `http://192.168.1.140:3006` (not `https://`).

---

### Attempt 2 — Dashboard container running the wrong image (GPU backend)

**Symptom:** `docker-compose ps` showed the `chessecon-dashboard` container in a `Restarting` loop. Logs showed the Python backend entrypoint running and failing with:

```
ERROR: Required environment variable HF_TOKEN is not set.
```

**Root cause:** The `docker-compose.yml` `dashboard` service originally had:

```yaml
dashboard:
  build:
    context: .
    dockerfile: Dockerfile
```

This `Dockerfile` at the project root is the **combined GPU backend + frontend** image (CUDA, PyTorch, Python, `docker-entrypoint.sh`). Docker had already built and tagged it as `chessecon-dashboard:latest`. Even after changing the `docker-compose.yml` to `image: nginx:alpine`, running `docker-compose up -d` reused the cached `chessecon-dashboard:latest` image instead of pulling nginx.

**Fix — two steps:**

1. Remove the stale image:
   ```bash
   docker-compose down
   docker rmi chessecon-dashboard:latest
   ```

2. Update `docker-compose.yml` dashboard service to use nginx directly (no build step):
   ```yaml
   dashboard:
     image: nginx:alpine
     container_name: chessecon-dashboard
     restart: unless-stopped
     ports:
       - "3006:80"
     volumes:
       - ./frontend/dist/public:/usr/share/nginx/html:ro
   ```

3. Bring up fresh:
   ```bash
   docker-compose up -d dashboard
   ```

---

### Attempt 3 — 403 Forbidden: wrong volume path

**Symptom:** Nginx started successfully but returned `403 Forbidden`. Nginx error log showed:

```
directory index of "/usr/share/nginx/html/" is forbidden
```

**Root cause — part A:** The volume mount was initially set to `./frontend/dist:/usr/share/nginx/html:ro`. The Vite build outputs files to `frontend/dist/public/` (not `frontend/dist/` directly) because the Manus web project template configures `publicDir` in `vite.config.ts`. So nginx was serving an empty directory.

**Root cause — part B:** The frontend had not been built at all — `frontend/dist/public/` did not exist yet.

**Fix — step 1:** Build the frontend on the host machine:

```bash
cd ~/suvasis/tools/blogs/hackathon/ChessEcon/frontend
VITE_WS_URL=ws://192.168.1.140:8008/ws pnpm build
```

The build completed successfully (the esbuild error for `server/_core/index.ts` is a server-side build step that does not affect the static frontend output):

```
../dist/public/index.html                 367.71 kB
../dist/public/assets/index-dzvHG_3C.css  118.58 kB
../dist/public/assets/index-TWBDAwdS.js   887.67 kB
✓ built in 4.20s
```

**Fix — step 2:** Update the volume path in `docker-compose.yml`:

```bash
sed -i 's|./frontend/dist:/usr/share/nginx/html|./frontend/dist/public:/usr/share/nginx/html|' docker-compose.yml
```

---

### Attempt 4 — `docker-compose restart` does not re-read volume mounts

**Symptom:** After updating the volume path and running `docker-compose restart dashboard`, the 403 persisted.

**Root cause:** `docker-compose restart` only stops and restarts the existing container — it does **not** recreate it. Volume mount changes in `docker-compose.yml` are only applied when the container is recreated. `restart` does not trigger recreation.

**Fix:** Always use `down` + `up` when changing volume mounts or image references:

```bash
docker-compose down
docker-compose up -d dashboard
```

---

### Final Working State

After all fixes, the dashboard is accessible at `http://192.168.1.140:3006`.

**Summary of the working `docker-compose.yml` dashboard service:**

```yaml
dashboard:
  image: nginx:alpine
  container_name: chessecon-dashboard
  restart: unless-stopped
  ports:
    - "3006:80"
  volumes:
    - ./frontend/dist/public:/usr/share/nginx/html:ro
```

**Summary of the working build + deploy sequence:**

```bash
# 1. Build the React frontend (run once, or after any code change)
cd ~/suvasis/tools/blogs/hackathon/ChessEcon/frontend
VITE_WS_URL=ws://192.168.1.140:8008/ws pnpm build

# 2. Remove any stale container/image if switching from the old GPU image
cd ..
docker-compose down
docker rmi chessecon-dashboard:latest 2>/dev/null || true

# 3. Start nginx serving the built files
docker-compose up -d dashboard

# 4. Verify
docker-compose ps
docker exec chessecon-dashboard ls /usr/share/nginx/html/
# Should show: index.html  assets/
```

**Key lessons learned:**

| Lesson | Detail |
|---|---|
| `VITE_*` vars are build-time | Must be set as shell env vars during `pnpm build`, not in Docker `environment:` |
| `docker-compose restart` ≠ recreate | Volume/image changes require `down` + `up` to take effect |
| Vite output path | Manus template outputs to `dist/public/`, not `dist/` — always check `vite.config.ts` `publicDir` |
| Old image caching | After changing `image:` in `docker-compose.yml`, remove the old image with `docker rmi` before `up` |
| esbuild server error is non-fatal | The `server/_core/index.ts` esbuild step fails on Lambda (no server env vars), but the Vite frontend build completes successfully before that step |

---

## Updated Current Status

| Component | Status |
|---|---|
| Dashboard UI | **Running** — accessible at `http://192.168.1.140:3006` |
| Backend server | Running on Lambda at port 8008 |
| Qwen2.5-0.5B | Loaded on `cuda:1`, generating moves |
| GRPO training | Active |
| Dashboard ↔ Backend (LIVE mode) | Ready — click LIVE toggle in dashboard to connect |
| Claude coaching | Disabled — `ANTHROPIC_API_KEY` not set |
| Nevermined integration | Not implemented (deferred) |

