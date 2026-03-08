"""
ChessEcon Training — Configuration
All training parameters read from environment variables / .env file.
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).parent.parent / ".env")


@dataclass
class TrainingConfig:
    # ── Model ─────────────────────────────────────────────────────────────────
    player_model: str   = field(default_factory=lambda: os.getenv("PLAYER_MODEL", "Qwen/Qwen2.5-0.5B-Instruct"))
    hf_token: str       = field(default_factory=lambda: os.getenv("HF_TOKEN", ""))
    model_cache_dir: str = field(default_factory=lambda: os.getenv("MODEL_CACHE_DIR", "./training/models"))
    skip_download: bool = field(default_factory=lambda: os.getenv("SKIP_MODEL_DOWNLOAD", "false").lower() == "true")
    device: str         = field(default_factory=lambda: os.getenv("DEVICE", "cpu"))

    # ── RL Algorithm ──────────────────────────────────────────────────────────
    rl_method: str      = field(default_factory=lambda: os.getenv("RL_METHOD", "grpo"))
    learning_rate: float = field(default_factory=lambda: float(os.getenv("LEARNING_RATE", "1e-5")))
    batch_size: int     = field(default_factory=lambda: int(os.getenv("BATCH_SIZE", "4")))
    num_generations: int = field(default_factory=lambda: int(os.getenv("NUM_GENERATIONS", "4")))
    max_new_tokens: int = 128
    temperature: float  = 0.9
    kl_coef: float      = 0.1

    # ── Self-play ─────────────────────────────────────────────────────────────
    total_games: int    = field(default_factory=lambda: int(os.getenv("TOTAL_GAMES", "100")))
    train_every: int    = field(default_factory=lambda: int(os.getenv("TRAIN_EVERY", "5")))
    train_steps: int    = field(default_factory=lambda: int(os.getenv("TRAIN_STEPS", "200")))
    save_every: int     = field(default_factory=lambda: int(os.getenv("SAVE_EVERY", "10")))

    # ── Economy ───────────────────────────────────────────────────────────────
    entry_fee: float    = field(default_factory=lambda: float(os.getenv("ENTRY_FEE", "10.0")))
    prize_multiplier: float = field(default_factory=lambda: float(os.getenv("PRIZE_MULTIPLIER", "0.9")))
    initial_wallet: float = field(default_factory=lambda: float(os.getenv("INITIAL_WALLET", "100.0")))
    coaching_fee: float = field(default_factory=lambda: float(os.getenv("COACHING_FEE", "5.0")))

    # ── Reward weights ────────────────────────────────────────────────────────
    game_reward_weight: float = 0.4
    economic_reward_weight: float = 0.6

    # ── Backend connection ────────────────────────────────────────────────────
    backend_url: str    = field(default_factory=lambda: os.getenv("BACKEND_URL", "http://localhost:8000"))

    # ── Output paths ──────────────────────────────────────────────────────────
    checkpoint_dir: str = field(default_factory=lambda: os.getenv("CHECKPOINT_DIR", "./training/checkpoints"))
    data_dir: str       = field(default_factory=lambda: os.getenv("SELFPLAY_DATA_DIR", "./training/data"))

    def __post_init__(self):
        Path(self.checkpoint_dir).mkdir(parents=True, exist_ok=True)
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.model_cache_dir).mkdir(parents=True, exist_ok=True)

    def summary(self) -> dict:
        return {
            "player_model": self.player_model,
            "rl_method": self.rl_method,
            "device": self.device,
            "total_games": self.total_games,
            "train_every": self.train_every,
            "batch_size": self.batch_size,
            "learning_rate": self.learning_rate,
            "hf_token_set": bool(self.hf_token),
        }
