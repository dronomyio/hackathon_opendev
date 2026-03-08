"""
ChessEcon Training — Self-Play Loop
Runs games between the trainable agent and a heuristic opponent,
collects episodes, and triggers RL training every N games.
Emits training metrics to the backend WebSocket for live dashboard display.
"""
from __future__ import annotations
import asyncio
import json
import logging
import random
import uuid
import time
from pathlib import Path
from typing import List, Optional

import chess

from training.config import TrainingConfig
from training.reward import combined_reward, build_prompt, game_reward, economic_reward
from shared.models import Episode, GameOutcome, TrainingStep

logger = logging.getLogger(__name__)


class SelfPlayLoop:
    """
    Orchestrates self-play games between the trainable LLM agent
    and a heuristic opponent. Collects episodes for RL training.
    """

    def __init__(self, model, tokenizer, trainer, config: TrainingConfig):
        self.model = model
        self.tokenizer = tokenizer
        self.trainer = trainer
        self.config = config
        self.episode_buffer: List[Episode] = []
        self.game_count = 0
        self.training_steps = 0
        self.win_count = 0
        self.total_profit = 0.0
        self.coaching_calls = 0

    def run(self, total_games: Optional[int] = None) -> None:
        """Run the full self-play training loop."""
        total = total_games or self.config.total_games
        logger.info(f"Starting self-play: {total} games, training every {self.config.train_every}")
        logger.info(f"Model: {self.config.player_model} | Method: {self.config.rl_method}")

        for game_num in range(1, total + 1):
            episode = self._run_game(game_num)
            self.episode_buffer.append(episode)
            self.game_count += 1

            # Track stats
            if episode.outcome == GameOutcome.WHITE_WIN:
                self.win_count += 1
            self.total_profit += episode.net_profit
            self.coaching_calls += episode.coaching_calls

            logger.info(
                f"Game {game_num}/{total} | "
                f"Outcome: {episode.outcome.value} | "
                f"Reward: {episode.combined_reward:.3f} | "
                f"Net P&L: {episode.net_profit:.1f}"
            )

            # Save episode to disk
            self._save_episode(episode)

            # Train every N games
            if game_num % self.config.train_every == 0:
                self._train()

        logger.info(
            f"Self-play complete. "
            f"Win rate: {self.win_count/max(self.game_count,1):.1%} | "
            f"Avg profit: {self.total_profit/max(self.game_count,1):.2f} | "
            f"Total training steps: {self.training_steps}"
        )

    def _run_game(self, game_num: int) -> Episode:
        """Run a single game and return the collected episode."""
        board = chess.Board()
        agent_is_white = random.random() > 0.5
        agent_color = chess.WHITE if agent_is_white else chess.BLACK

        # Economy tracking
        wallet = self.config.initial_wallet - self.config.entry_fee
        coaching_calls = 0
        coaching_cost = 0.0

        prompts: List[str] = []
        responses: List[str] = []
        moves: List[str] = []

        max_moves = 150
        move_count = 0

        while not board.is_game_over() and move_count < max_moves:
            legal = [m.uci() for m in board.legal_moves]
            is_agent_turn = (board.turn == agent_color)

            if is_agent_turn:
                # Build prompt for the LLM agent
                can_coach = wallet >= self.config.coaching_fee + 5.0
                prompt = build_prompt(
                    fen=board.fen(),
                    legal_moves=legal,
                    wallet=wallet,
                    coaching_fee=self.config.coaching_fee,
                    move_number=board.fullmove_number,
                    can_afford_coaching=can_coach,
                )
                # Generate response from model
                response = self._generate_response(prompt, legal)
                move_uci = self._extract_move(response, legal)
                buy_coaching = "BUY_COACHING: yes" in response.upper() and can_coach

                if buy_coaching:
                    wallet -= self.config.coaching_fee
                    coaching_calls += 1
                    coaching_cost += self.config.coaching_fee
                    # Use a heuristic move as "coaching" recommendation
                    move_uci = self._heuristic_move(board)

                prompts.append(prompt)
                responses.append(response)
                moves.append(move_uci)
            else:
                # Heuristic opponent
                move_uci = self._heuristic_move(board)

            try:
                board.push(chess.Move.from_uci(move_uci))
            except Exception:
                move_uci = random.choice(legal)
                board.push(chess.Move.from_uci(move_uci))

            move_count += 1

        # Determine outcome
        outcome = self._board_outcome(board)

        # Economic settlement
        prize = 0.0
        if (outcome == GameOutcome.WHITE_WIN and agent_is_white) or \
           (outcome == GameOutcome.BLACK_WIN and not agent_is_white):
            prize = self.config.entry_fee * 2 * self.config.prize_multiplier
        elif outcome == GameOutcome.DRAW:
            prize = self.config.entry_fee * self.config.prize_multiplier

        net_profit = prize - self.config.entry_fee - coaching_cost
        gr = game_reward(outcome, agent_is_white)
        er = economic_reward(net_profit)
        cr = combined_reward(outcome, agent_is_white, net_profit)

        return Episode(
            episode_id=str(uuid.uuid4()),
            game_id=str(uuid.uuid4()),
            agent_id="trainable_agent",
            prompts=prompts,
            responses=responses,
            moves=moves,
            outcome=outcome,
            game_reward=gr,
            economic_reward=er,
            combined_reward=cr,
            coaching_calls=coaching_calls,
            coaching_cost=coaching_cost,
            net_profit=net_profit,
        )

    def _train(self) -> None:
        """Run one training step on buffered episodes."""
        if not self.episode_buffer:
            return

        logger.info(f"Training on {len(self.episode_buffer)} episodes...")
        metrics = self.trainer.train_step(self.episode_buffer)
        self.training_steps += 1

        # Augment metrics with game stats
        metrics["win_rate"] = self.win_count / max(self.game_count, 1)
        metrics["avg_profit"] = self.total_profit / max(self.game_count, 1)
        metrics["coaching_rate"] = self.coaching_calls / max(self.game_count, 1)

        # Save checkpoint
        if self.training_steps % self.config.save_every == 0:
            self.trainer.save_checkpoint(metrics)

        # Emit to backend WebSocket (fire-and-forget)
        self._emit_training_metrics(metrics)

        # Clear buffer
        self.episode_buffer.clear()

    def _generate_response(self, prompt: str, legal_moves: list) -> str:
        """Generate a response from the LLM model."""
        try:
            from training.model_loader import generate_move
            return generate_move(
                self.model, self.tokenizer, prompt,
                max_new_tokens=self.config.max_new_tokens,
                temperature=self.config.temperature,
                device=self.config.device,
            )
        except Exception as e:
            logger.debug(f"Model generation failed: {e} — using heuristic")
            return f"MOVE: {random.choice(legal_moves)}\nBUY_COACHING: no\nREASONING: heuristic"

    def _extract_move(self, response: str, legal_moves: list) -> str:
        """Extract UCI move from model response."""
        import re
        match = re.search(r"MOVE:\s*([a-h][1-8][a-h][1-8][qrbn]?)", response, re.IGNORECASE)
        if match:
            move = match.group(1).lower()
            if move in legal_moves:
                return move
        # Scan for any UCI move in the text
        for token in re.findall(r"\b([a-h][1-8][a-h][1-8][qrbn]?)\b", response):
            if token.lower() in legal_moves:
                return token.lower()
        return random.choice(legal_moves)

    def _heuristic_move(self, board: chess.Board) -> str:
        """Simple heuristic: prefer captures, then center moves."""
        legal = list(board.legal_moves)
        captures = [m for m in legal if board.is_capture(m)]
        if captures:
            return random.choice(captures).uci()
        center = [chess.Move.from_uci(m) for m in ["e2e4","d2d4","e7e5","d7d5","g1f3","b1c3"]
                  if chess.Move.from_uci(m) in legal]
        if center:
            return random.choice(center).uci()
        return random.choice(legal).uci()

    def _board_outcome(self, board: chess.Board) -> GameOutcome:
        if not board.is_game_over():
            return GameOutcome.DRAW
        result = board.result()
        if result == "1-0":
            return GameOutcome.WHITE_WIN
        elif result == "0-1":
            return GameOutcome.BLACK_WIN
        return GameOutcome.DRAW

    def _save_episode(self, episode: Episode) -> None:
        """Append episode to JSONL file for later analysis."""
        data_dir = Path(self.config.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        file_path = data_dir / f"episodes_{time.strftime('%Y%m%d')}.jsonl"
        with open(file_path, "a") as f:
            f.write(episode.model_dump_json() + "\n")

    def _emit_training_metrics(self, metrics: dict) -> None:
        """Send training metrics to backend WebSocket (best-effort)."""
        try:
            import requests
            backend_url = self.config.backend_url
            requests.post(
                f"{backend_url}/api/training/ingest",
                json={"step": self.training_steps, **metrics},
                timeout=2,
            )
        except Exception:
            pass  # Non-critical — dashboard will poll /api/training/metrics
