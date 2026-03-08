"""
settings.py
───────────
Single source of truth for all environment-variable-driven configuration.
All values have safe defaults so the server starts without any .env file.

New in v2 (OpenEnv):
  - white_model / black_model replace the single player_model
"""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    # ── Models (dual-agent) ───────────────────────────────────────────────
    white_model: str = field(
        default_factory=lambda: os.getenv(
            "WHITE_MODEL",
            os.getenv("PLAYER_MODEL", "Qwen/Qwen2.5-0.5B-Instruct"),
        )
    )
    black_model: str = field(
        default_factory=lambda: os.getenv(
            "BLACK_MODEL",
            "meta-llama/Llama-3.2-1B-Instruct",
        )
    )
    # Legacy alias
    @property
    def player_model(self) -> str:
        return self.white_model

    hf_token: str = field(default_factory=lambda: os.getenv("HF_TOKEN", ""))
    device: str = field(default_factory=lambda: os.getenv("DEVICE", "auto"))
    torch_dtype: str = field(default_factory=lambda: os.getenv("TORCH_DTYPE", "bfloat16"))

    # ── Move generation ───────────────────────────────────────────────────
    max_new_tokens: int = field(default_factory=lambda: int(os.getenv("MAX_NEW_TOKENS", "32")))
    temperature: float = field(default_factory=lambda: float(os.getenv("TEMPERATURE", "0.7")))
    max_move_retries: int = field(default_factory=lambda: int(os.getenv("MAX_MOVE_RETRIES", "5")))

    # ── GRPO training ─────────────────────────────────────────────────────
    grpo_update_every_n_games: int = field(default_factory=lambda: int(os.getenv("GRPO_UPDATE_EVERY_N_GAMES", "1")))
    grpo_group_size: int = field(default_factory=lambda: int(os.getenv("GRPO_GROUP_SIZE", "4")))
    grpo_kl_coeff: float = field(default_factory=lambda: float(os.getenv("GRPO_KL_COEFF", "0.04")))
    grpo_lr: float = field(default_factory=lambda: float(os.getenv("GRPO_LR", "1e-5")))
    lora_rank: int = field(default_factory=lambda: int(os.getenv("LORA_RANK", "8")))
    checkpoint_dir: str = field(default_factory=lambda: os.getenv("CHECKPOINT_DIR", "./checkpoints"))
    save_every_n_steps: int = field(default_factory=lambda: int(os.getenv("SAVE_EVERY_N_STEPS", "10")))

    # ── Economy ───────────────────────────────────────────────────────────
    starting_wallet: float = field(default_factory=lambda: float(os.getenv("STARTING_WALLET", "100.0")))
    entry_fee: float = field(default_factory=lambda: float(os.getenv("ENTRY_FEE", "10.0")))
    prize_pool_fraction: float = field(default_factory=lambda: float(os.getenv("PRIZE_POOL_FRACTION", "0.9")))
    max_moves: int = field(default_factory=lambda: int(os.getenv("MAX_MOVES", "150")))

    # ── Server ────────────────────────────────────────────────────────────
    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    move_delay: float = field(default_factory=lambda: float(os.getenv("MOVE_DELAY", "0.5")))


settings = Settings()
