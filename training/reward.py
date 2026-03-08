"""
ChessEcon Training — Reward Function
Combines chess game outcome reward with economic performance reward.
The agent learns to win games AND manage money efficiently.
"""
from __future__ import annotations
from shared.models import GameOutcome


GAME_WEIGHT     = 0.4   # Weight for chess outcome
ECONOMIC_WEIGHT = 0.6   # Weight for economic performance


def game_reward(outcome: GameOutcome, agent_is_white: bool) -> float:
    """
    Binary reward for game outcome.
    +1.0 = win, 0.0 = draw, -1.0 = loss
    """
    if outcome == GameOutcome.DRAW:
        return 0.0
    if outcome == GameOutcome.WHITE_WIN:
        return 1.0 if agent_is_white else -1.0
    if outcome == GameOutcome.BLACK_WIN:
        return -1.0 if agent_is_white else 1.0
    return 0.0  # ONGOING — should not happen at episode end


def economic_reward(
    net_profit: float,
    initial_wallet: float = 100.0,
    max_profit: float = 20.0,
) -> float:
    """
    Normalized economic reward based on net profit per game.
    Scaled to [-1, +1] range.
    net_profit = prize_income - entry_fee - coaching_costs
    """
    # Normalize: max_profit is the best possible outcome (win without coaching)
    normalized = net_profit / max_profit
    return max(-1.0, min(1.0, normalized))


def combined_reward(
    outcome: GameOutcome,
    agent_is_white: bool,
    net_profit: float,
    initial_wallet: float = 100.0,
    max_profit: float = 20.0,
    game_weight: float = GAME_WEIGHT,
    economic_weight: float = ECONOMIC_WEIGHT,
) -> float:
    """
    Combined reward = game_weight * game_reward + economic_weight * economic_reward
    This is the signal used to train the RL policy.
    """
    gr = game_reward(outcome, agent_is_white)
    er = economic_reward(net_profit, initial_wallet, max_profit)
    return game_weight * gr + economic_weight * er


def build_prompt(
    fen: str,
    legal_moves: list,
    wallet: float,
    coaching_fee: float,
    move_number: int,
    can_afford_coaching: bool,
) -> str:
    """
    Build the LLM prompt for the trainable player agent.
    The model must output a valid UCI move and optionally request coaching.
    """
    legal_sample = legal_moves[:20]
    coaching_hint = (
        f"You can request coaching (costs {coaching_fee:.1f} units from your wallet)."
        if can_afford_coaching else
        "Coaching unavailable (insufficient funds)."
    )
    return f"""You are an autonomous chess player managing your own finances.

Current position (FEN): {fen}
Move number: {move_number}
Your wallet: {wallet:.1f} units
{coaching_hint}

Legal moves (UCI format): {', '.join(legal_sample)}{'...' if len(legal_moves) > 20 else ''}

Analyze the position and respond with:
MOVE: <uci_move>
BUY_COACHING: yes/no
REASONING: <brief explanation>

Your move must be from the legal moves list."""
