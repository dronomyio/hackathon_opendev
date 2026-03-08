"""
ChessEcon Training — Base Trainer
Abstract base class for all RL training algorithms.
"""
from __future__ import annotations
import abc
import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from training.config import TrainingConfig

logger = logging.getLogger(__name__)


class BaseTrainer(abc.ABC):
    """Abstract base for GRPO, PPO, RLOO, and other RL trainers."""

    def __init__(self, model, tokenizer, config: TrainingConfig):
        self.model = model
        self.tokenizer = tokenizer
        self.config = config
        self.step = 0
        self.metrics_history: List[Dict[str, Any]] = []

    @abc.abstractmethod
    def train_step(self, episodes: list) -> Dict[str, float]:
        """
        Run one training step on a batch of episodes.
        Returns a dict of metrics: loss, reward, kl_div, etc.
        """
        ...

    def save_checkpoint(self, metrics: Dict[str, float]) -> None:
        """Save model checkpoint and metrics to disk."""
        checkpoint_path = Path(self.config.checkpoint_dir) / f"step_{self.step:04d}"
        checkpoint_path.mkdir(parents=True, exist_ok=True)

        # Save model
        self.model.save_pretrained(str(checkpoint_path))
        self.tokenizer.save_pretrained(str(checkpoint_path))

        # Save metrics
        metrics["step"] = self.step
        with open(checkpoint_path / "metrics.json", "w") as f:
            json.dump(metrics, f, indent=2)

        logger.info(f"Checkpoint saved: {checkpoint_path}")

    def log_metrics(self, metrics: Dict[str, float]) -> None:
        metrics["step"] = self.step
        self.metrics_history.append(metrics)
        logger.info(
            f"[Step {self.step}] "
            + " | ".join(f"{k}={v:.4f}" for k, v in metrics.items() if k != "step")
        )

    def _format_episodes_for_training(self, episodes: list) -> List[Dict]:
        """Convert Episode objects to training-ready format."""
        samples = []
        for ep in episodes:
            for prompt, response, move in zip(ep.prompts, ep.responses, ep.moves):
                samples.append({
                    "prompt": prompt,
                    "response": response,
                    "move": move,
                    "reward": ep.combined_reward,
                    "game_reward": ep.game_reward,
                    "economic_reward": ep.economic_reward,
                })
        return samples
