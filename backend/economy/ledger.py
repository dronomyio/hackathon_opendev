"""
ChessEcon Backend — Economic Ledger
Manages agent wallets, tournament prize pools, and transaction history.
"""
from __future__ import annotations
import os
import uuid
import time
from typing import Dict, List, Optional
from shared.models import Transaction, WalletState, TournamentResult, GameOutcome


class EconomicConfig:
    entry_fee: float       = float(os.getenv("ENTRY_FEE", "10.0"))
    prize_multiplier: float = float(os.getenv("PRIZE_MULTIPLIER", "0.9"))
    initial_wallet: float  = float(os.getenv("INITIAL_WALLET", "100.0"))
    coaching_fee: float    = float(os.getenv("COACHING_FEE", "5.0"))
    min_wallet_for_coaching: float = float(os.getenv("MIN_WALLET_FOR_COACHING", "15.0"))


class Ledger:
    """
    Manages all economic activity in the ChessEcon system.
    Thread-safe for concurrent game sessions.
    """

    def __init__(self, config: Optional[EconomicConfig] = None):
        self.config = config or EconomicConfig()
        self._wallets: Dict[str, WalletState] = {}
        self._transactions: List[Transaction] = []
        self._open_games: Dict[str, dict] = {}  # game_id -> {white, black, pool}

    # ── Wallet management ─────────────────────────────────────────────────────

    def register_agent(self, agent_id: str) -> WalletState:
        if agent_id not in self._wallets:
            self._wallets[agent_id] = WalletState(
                agent_id=agent_id,
                balance=self.config.initial_wallet,
                total_earned=self.config.initial_wallet,
            )
        return self._wallets[agent_id]

    def get_wallet(self, agent_id: str) -> WalletState:
        if agent_id not in self._wallets:
            return self.register_agent(agent_id)
        return self._wallets[agent_id]

    def get_balance(self, agent_id: str) -> float:
        return self.get_wallet(agent_id).balance

    def _debit(self, agent_id: str, amount: float, description: str) -> Transaction:
        wallet = self.get_wallet(agent_id)
        wallet.balance -= amount
        wallet.total_spent += amount
        tx = Transaction(
            tx_id=str(uuid.uuid4()),
            agent_id=agent_id,
            amount=-amount,
            description=description,
        )
        self._transactions.append(tx)
        return tx

    def _credit(self, agent_id: str, amount: float, description: str) -> Transaction:
        wallet = self.get_wallet(agent_id)
        wallet.balance += amount
        wallet.total_earned += amount
        tx = Transaction(
            tx_id=str(uuid.uuid4()),
            agent_id=agent_id,
            amount=amount,
            description=description,
        )
        self._transactions.append(tx)
        return tx

    # ── Tournament management ─────────────────────────────────────────────────

    def open_game(self, game_id: str, white_id: str, black_id: str) -> float:
        """Collect entry fees and open a prize pool. Returns pool size."""
        fee = self.config.entry_fee
        self._debit(white_id, fee, f"Entry fee game {game_id}")
        self._debit(black_id, fee, f"Entry fee game {game_id}")
        pool = fee * 2 * self.config.prize_multiplier
        self._open_games[game_id] = {
            "white": white_id,
            "black": black_id,
            "pool": pool,
            "entry_fees": fee * 2,
        }
        # Update game counts
        self.get_wallet(white_id).games_played += 1
        self.get_wallet(black_id).games_played += 1
        return pool

    def settle_game(self, game_id: str, outcome: GameOutcome) -> TournamentResult:
        """Pay out prize pool based on game outcome. Returns settlement details."""
        if game_id not in self._open_games:
            raise KeyError(f"Game {game_id} not found in open games")

        game = self._open_games.pop(game_id)
        white_id = game["white"]
        black_id = game["black"]
        pool = game["pool"]
        entry_fees = game["entry_fees"]
        organizer_cut = entry_fees - pool

        winner: Optional[str] = None
        prize_paid = 0.0

        if outcome == GameOutcome.WHITE_WIN:
            winner = white_id
            prize_paid = pool
            self._credit(white_id, pool, f"Prize win game {game_id}")
            self.get_wallet(white_id).games_won += 1
        elif outcome == GameOutcome.BLACK_WIN:
            winner = black_id
            prize_paid = pool
            self._credit(black_id, pool, f"Prize win game {game_id}")
            self.get_wallet(black_id).games_won += 1
        elif outcome == GameOutcome.DRAW:
            # Split pool equally on draw
            half = pool / 2
            prize_paid = pool
            self._credit(white_id, half, f"Draw prize game {game_id}")
            self._credit(black_id, half, f"Draw prize game {game_id}")

        return TournamentResult(
            game_id=game_id,
            winner=winner,
            outcome=outcome,
            prize_paid=prize_paid,
            entry_fees_collected=entry_fees,
            organizer_cut=organizer_cut,
        )

    # ── Coaching payments ─────────────────────────────────────────────────────

    def charge_coaching(self, agent_id: str, game_id: str) -> float:
        """Deduct coaching fee. Returns fee charged, or 0 if insufficient funds."""
        wallet = self.get_wallet(agent_id)
        if wallet.balance < self.config.min_wallet_for_coaching:
            return 0.0
        fee = self.config.coaching_fee
        self._debit(agent_id, fee, f"Claude coaching game {game_id}")
        wallet.coaching_calls += 1
        return fee

    def can_afford_coaching(self, agent_id: str) -> bool:
        return self.get_balance(agent_id) >= self.config.min_wallet_for_coaching

    # ── Reporting ─────────────────────────────────────────────────────────────

    def get_all_wallets(self) -> Dict[str, WalletState]:
        return dict(self._wallets)

    def get_transactions(self, agent_id: Optional[str] = None) -> List[Transaction]:
        if agent_id:
            return [t for t in self._transactions if t.agent_id == agent_id]
        return list(self._transactions)

    def summary(self) -> dict:
        wallets = self._wallets
        return {
            "total_agents": len(wallets),
            "total_transactions": len(self._transactions),
            "open_games": len(self._open_games),
            "wallets": {aid: w.model_dump() for aid, w in wallets.items()},
        }


# Singleton instance
ledger = Ledger()
