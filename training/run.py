"""
ChessEcon Training — Entry Point
Run RL training from the command line.

Usage:
    python -m training.run --method grpo --games 100
    python -m training.run --method ppo --model Qwen/Qwen2.5-1.5B-Instruct
    python -m training.run --demo   # 3-game demo without model download
"""
from __future__ import annotations
import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from training.config import TrainingConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def get_trainer(method: str, model, tokenizer, config: TrainingConfig):
    method = method.lower()
    if method == "grpo":
        from training.trainers.grpo import GRPOTrainer
        return GRPOTrainer(model, tokenizer, config)
    elif method == "ppo":
        from training.trainers.ppo import PPOTrainer
        return PPOTrainer(model, tokenizer, config)
    elif method == "rloo":
        from training.trainers.rloo import RLOOTrainer
        return RLOOTrainer(model, tokenizer, config)
    else:
        raise ValueError(f"Unknown RL method: {method}. Choose: grpo, ppo, rloo")


def run_demo(config: TrainingConfig) -> None:
    """Run a 3-game demo with heuristic agents (no LLM download required)."""
    import chess
    import random
    from shared.models import GameOutcome
    from training.reward import combined_reward, game_reward, economic_reward

    logger.info("=== ChessEcon Demo (3 games, heuristic agents) ===")
    for game_num in range(1, 4):
        board = chess.Board()
        moves = 0
        while not board.is_game_over() and moves < 80:
            legal = list(board.legal_moves)
            captures = [m for m in legal if board.is_capture(m)]
            move = random.choice(captures if captures else legal)
            board.push(move)
            moves += 1

        result = board.result()
        outcome = (GameOutcome.WHITE_WIN if result == "1-0" else
                   GameOutcome.BLACK_WIN if result == "0-1" else GameOutcome.DRAW)
        net_profit = (config.entry_fee * 2 * config.prize_multiplier - config.entry_fee
                      if outcome == GameOutcome.WHITE_WIN else
                      -config.entry_fee if outcome == GameOutcome.BLACK_WIN else 0.0)
        reward = combined_reward(outcome, True, net_profit)

        logger.info(
            f"Game {game_num}: {outcome.value} in {moves} moves | "
            f"Net P&L: {net_profit:+.1f} | Reward: {reward:.3f}"
        )
    logger.info("Demo complete.")


def main():
    parser = argparse.ArgumentParser(description="ChessEcon RL Training")
    parser.add_argument("--method", default="grpo", choices=["grpo", "ppo", "rloo"],
                        help="RL training algorithm")
    parser.add_argument("--model", default=None,
                        help="HuggingFace model ID (overrides PLAYER_MODEL env var)")
    parser.add_argument("--games", type=int, default=None,
                        help="Number of self-play games (overrides TOTAL_GAMES env var)")
    parser.add_argument("--device", default=None,
                        help="Device: cpu | cuda | mps")
    parser.add_argument("--demo", action="store_true",
                        help="Run 3-game demo without downloading a model")
    args = parser.parse_args()

    config = TrainingConfig()
    if args.model:
        config.player_model = args.model
    if args.games:
        config.total_games = args.games
    if args.device:
        config.device = args.device
    config.rl_method = args.method

    logger.info("=== ChessEcon Training Configuration ===")
    for k, v in config.summary().items():
        logger.info(f"  {k}: {v}")

    if args.demo:
        run_demo(config)
        return

    # Download and load model
    logger.info(f"Loading model: {config.player_model}")
    if not config.skip_download:
        from training.model_loader import download_model
        download_model(config.player_model, config.model_cache_dir, config.hf_token or None)

    from training.model_loader import load_model_and_tokenizer
    model, tokenizer = load_model_and_tokenizer(
        config.player_model,
        config.model_cache_dir,
        config.device,
        config.hf_token or None,
    )

    # Initialize trainer
    trainer = get_trainer(config.rl_method, model, tokenizer, config)
    logger.info(f"Trainer: {type(trainer).__name__}")

    # Run self-play loop
    from training.self_play import SelfPlayLoop
    loop = SelfPlayLoop(model, tokenizer, trainer, config)
    loop.run()


if __name__ == "__main__":
    main()
