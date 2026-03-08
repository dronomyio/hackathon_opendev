"""
grpo_trainer.py
───────────────
Group Relative Policy Optimisation (GRPO) training loop for the chess agent.

Algorithm summary (per game batch):
  1. Collect a group of G candidate moves per position (sampled from the policy).
  2. Compute advantages: A_i = (r_i - mean(r)) / (std(r) + ε)
     where r_i is the terminal game reward for the trajectory that chose move i.
  3. Compute the GRPO policy loss:
       L = -E[ min(ratio * A, clip(ratio, 1-ε, 1+ε) * A) ]
     where ratio = exp(log_π_θ(a) - log_π_old(a))
  4. Add KL penalty: L_total = L + β * KL(π_θ || π_ref)
  5. Backprop and update the model weights.

In practice, for a single-agent chess game:
  - Each move in the game is a "step" with a delayed terminal reward.
  - The group is formed by sampling G moves at each position and running
    mini-rollouts (or approximating with the final game outcome).
  - For simplicity we use the full game outcome as the reward for every
    move in the game (REINFORCE-style with GRPO normalisation).

References:
  DeepSeek-R1 GRPO: https://arxiv.org/abs/2501.12599
"""

import os
import logging
import torch
import torch.nn.functional as F
from dataclasses import dataclass, field
from typing import Optional

from settings import settings

logger = logging.getLogger(__name__)


@dataclass
class Trajectory:
    """One complete game trajectory collected for training."""
    agent_color: str
    log_probs: list[float]          # log π_θ(a_t | s_t) for each move
    ref_log_probs: list[float]      # log π_ref(a_t | s_t) for KL
    reward: float                   # terminal reward (+1 win, -1 loss, 0 draw)
    move_count: int = 0


@dataclass
class TrainingMetrics:
    step: int = 0
    loss: float = 0.0
    policy_reward: float = 0.0
    kl_div: float = 0.0
    win_rate: float = 0.0
    avg_profit: float = 0.0
    coaching_rate: float = 0.0
    # Running stats
    wins: int = 0
    games: int = 0
    total_profit: float = 0.0
    total_coaching_calls: int = 0
    total_moves: int = 0


class GRPOTrainer:
    """
    Manages the GRPO training loop for the Qwen chess agent.

    Usage:
        trainer = GRPOTrainer(model, tokenizer)
        trainer.record_move(log_prob, ref_log_prob)
        ...
        metrics = trainer.end_game(reward, profit, coaching_calls)
        # metrics is None until grpo_update_every_n_games games have been collected
    """

    def __init__(self, model, tokenizer):
        self.model = model
        self.tokenizer = tokenizer
        self._step = 0
        self._pending: list[Trajectory] = []
        self._current: Optional[Trajectory] = None
        self._metrics = TrainingMetrics()

        # Optimizer — only update LoRA params if present, else all params
        trainable = [p for p in model.parameters() if p.requires_grad]
        if not trainable:
            logger.warning("No trainable parameters found — GRPO updates will be no-ops.")
        self._optimizer = torch.optim.AdamW(trainable, lr=settings.grpo_lr) if trainable else None

    # ── Game lifecycle ────────────────────────────────────────────────────

    def start_game(self, agent_color: str):
        """Call at the start of each game."""
        self._current = Trajectory(agent_color=agent_color, log_probs=[], ref_log_probs=[], reward=0.0)

    def record_move(self, log_prob: float, ref_log_prob: float):
        """Call after each move with the policy and reference log-probs."""
        if self._current is None:
            return
        self._current.log_probs.append(log_prob)
        self._current.ref_log_probs.append(ref_log_prob)
        self._current.move_count += 1

    def end_game(
        self,
        reward: float,
        profit: float = 0.0,
        coaching_calls: int = 0,
    ) -> Optional[TrainingMetrics]:
        """
        Call at game end with the terminal reward.
        Returns updated TrainingMetrics if a gradient update was performed,
        else None (still accumulating games).
        """
        if self._current is None:
            return None

        self._current.reward = reward
        self._pending.append(self._current)
        self._current = None

        # Update running stats
        m = self._metrics
        m.games += 1
        if reward > 0:
            m.wins += 1
        m.total_profit += profit
        m.total_coaching_calls += coaching_calls
        m.total_moves += self._pending[-1].move_count

        # Trigger update every N games
        if m.games % settings.grpo_update_every_n_games == 0:
            return self._update()

        return None

    # ── GRPO update ───────────────────────────────────────────────────────

    def _update(self) -> TrainingMetrics:
        """Perform one GRPO gradient update over the pending trajectories."""
        if self._optimizer is None or not self._pending:
            return self._build_metrics()

        trajectories = self._pending
        self._pending = []

        # Collect rewards and compute advantages (GRPO normalisation)
        rewards = torch.tensor([t.reward for t in trajectories], dtype=torch.float32)
        mean_r = rewards.mean()
        std_r = rewards.std(unbiased=False) + 1e-8  # unbiased=False avoids nan for N=1
        if std_r < 1e-6:
            advantages = rewards - mean_r
        else:
            advantages = (rewards - mean_r) / std_r  # shape: (N,)

        total_loss = torch.tensor(0.0, requires_grad=True)
        total_kl = 0.0
        n_tokens = 0

        for traj, adv in zip(trajectories, advantages):
            if not traj.log_probs:
                continue

            lp = torch.tensor(traj.log_probs, dtype=torch.float32)       # (T,)
            ref_lp = torch.tensor(traj.ref_log_probs, dtype=torch.float32)  # (T,)

            # Ratio: π_θ / π_old  (here π_old == π_ref since we update every game)
            ratio = torch.exp(lp - ref_lp)

            # Clipped surrogate loss (PPO-style clip)
            eps = 0.2
            clipped = torch.clamp(ratio, 1 - eps, 1 + eps)
            surrogate = torch.min(ratio * adv, clipped * adv)
            policy_loss = -surrogate.mean()

            # KL penalty: KL(π_θ || π_ref) ≈ exp(lp - ref_lp) - (lp - ref_lp) - 1
            diff = torch.clamp(lp - ref_lp, -10, 10)  # prevent KL explosion
            kl = (torch.exp(diff) - diff - 1).mean()
            total_kl += kl.item()

            step_loss = policy_loss + settings.grpo_kl_coeff * kl
            total_loss = total_loss + step_loss
            n_tokens += len(traj.log_probs)

        if n_tokens > 0:
            total_loss = total_loss / len(trajectories)
            self._optimizer.zero_grad()
            total_loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            self._optimizer.step()

        self._step += 1

        # Save checkpoint periodically
        if self._step % settings.save_every_n_steps == 0:
            self._save_checkpoint()

        # Update metrics
        m = self._metrics
        m.step = self._step
        m.loss = total_loss.item() if n_tokens > 0 else 0.0
        m.policy_reward = float(rewards.mean())
        m.kl_div = total_kl / max(len(trajectories), 1)
        m.win_rate = m.wins / max(m.games, 1)
        m.avg_profit = m.total_profit / max(m.games, 1)
        m.coaching_rate = m.total_coaching_calls / max(m.total_moves, 1)

        logger.info(
            "GRPO step %d | loss=%.4f reward=%.3f kl=%.4f win_rate=%.2f",
            m.step, m.loss, m.policy_reward, m.kl_div, m.win_rate,
        )
        return self._build_metrics()

    def _build_metrics(self) -> TrainingMetrics:
        import copy
        return copy.copy(self._metrics)

    # ── Checkpoint ────────────────────────────────────────────────────────

    def _save_checkpoint(self):
        os.makedirs(settings.checkpoint_dir, exist_ok=True)
        path = os.path.join(settings.checkpoint_dir, f"step_{self._step:06d}")
        try:
            self.model.save_pretrained(path)
            self.tokenizer.save_pretrained(path)
            logger.info("Checkpoint saved: %s", path)
        except Exception as exc:
            logger.error("Checkpoint save failed: %s", exc)

    def load_checkpoint(self, path: str):
        """Load a previously saved LoRA checkpoint."""
        try:
            from peft import PeftModel  # type: ignore
            self.model = PeftModel.from_pretrained(self.model, path)
            logger.info("Checkpoint loaded: %s", path)
        except Exception as exc:
            logger.error("Checkpoint load failed: %s", exc)

