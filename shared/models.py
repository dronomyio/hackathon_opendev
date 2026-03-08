"""
ChessEcon — Shared Data Models
Pydantic models used by both the backend API and the training pipeline.
"""
from __future__ import annotations
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import time


# ── Enums ──────────────────────────────────────────────────────────────────────

class GameStatus(str, Enum):
    WAITING   = "waiting"
    ACTIVE    = "active"
    FINISHED  = "finished"

class GameOutcome(str, Enum):
    WHITE_WIN = "white_win"
    BLACK_WIN = "black_win"
    DRAW      = "draw"
    ONGOING   = "ongoing"

class EventType(str, Enum):
    GAME_START      = "game_start"
    MOVE            = "move"
    COACHING_REQUEST = "coaching_request"
    COACHING_RESULT  = "coaching_result"
    GAME_END        = "game_end"
    TRAINING_STEP   = "training_step"
    ECONOMY_UPDATE  = "economy_update"
    ERROR           = "error"

class PositionComplexity(str, Enum):
    SIMPLE   = "simple"
    MODERATE = "moderate"
    COMPLEX  = "complex"
    CRITICAL = "critical"

class RLMethod(str, Enum):
    GRPO      = "grpo"
    PPO       = "ppo"
    RLOO      = "rloo"
    REINFORCE = "reinforce"
    DPO       = "dpo"


# ── Chess Models ───────────────────────────────────────────────────────────────

class MoveRequest(BaseModel):
    game_id: str
    player: str  # "white" | "black"
    move_uci: str

class MoveResponse(BaseModel):
    game_id: str
    move_uci: str
    fen: str
    legal_moves: List[str]
    outcome: GameOutcome
    move_number: int
    is_check: bool
    is_checkmate: bool
    is_stalemate: bool

class GameState(BaseModel):
    game_id: str
    fen: str
    legal_moves: List[str]
    outcome: GameOutcome
    move_number: int
    move_history: List[str] = Field(default_factory=list)
    status: GameStatus = GameStatus.ACTIVE
    white_player: str = "white"
    black_player: str = "black"
    created_at: float = Field(default_factory=time.time)

class NewGameResponse(BaseModel):
    game_id: str
    fen: str
    legal_moves: List[str]
    status: GameStatus


# ── Economy Models ─────────────────────────────────────────────────────────────

class Transaction(BaseModel):
    tx_id: str
    agent_id: str
    amount: float          # positive = credit, negative = debit
    description: str
    timestamp: float = Field(default_factory=time.time)

class WalletState(BaseModel):
    agent_id: str
    balance: float
    total_earned: float = 0.0
    total_spent: float = 0.0
    coaching_calls: int = 0
    games_played: int = 0
    games_won: int = 0

class TournamentResult(BaseModel):
    game_id: str
    winner: Optional[str]   # agent_id or None for draw
    outcome: GameOutcome
    prize_paid: float
    entry_fees_collected: float
    organizer_cut: float


# ── Agent Models ───────────────────────────────────────────────────────────────

class ComplexityAnalysis(BaseModel):
    fen: str
    score: float                      # 0.0 – 1.0
    level: PositionComplexity
    factors: Dict[str, float] = Field(default_factory=dict)
    recommend_coaching: bool = False

class CoachingRequest(BaseModel):
    game_id: str
    agent_id: str
    fen: str
    legal_moves: List[str]
    wallet_balance: float
    complexity: ComplexityAnalysis

class CoachingResponse(BaseModel):
    game_id: str
    agent_id: str
    recommended_move: str
    analysis: str
    cost: float
    model_used: str
    tokens_used: int = 0


# ── Training Models ────────────────────────────────────────────────────────────

class Episode(BaseModel):
    """A single completed game episode used for RL training."""
    episode_id: str
    game_id: str
    agent_id: str
    prompts: List[str]           # LLM prompts at each move
    responses: List[str]         # LLM responses at each move
    moves: List[str]             # UCI moves played
    outcome: GameOutcome
    game_reward: float           # +1 win, 0 draw, -1 loss
    economic_reward: float       # normalized net profit
    combined_reward: float       # weighted combination
    coaching_calls: int = 0
    coaching_cost: float = 0.0
    net_profit: float = 0.0
    created_at: float = Field(default_factory=time.time)

class TrainingStep(BaseModel):
    step: int
    method: RLMethod
    loss: float
    policy_reward: float
    kl_divergence: float
    win_rate: float
    avg_profit: float
    coaching_rate: float
    episodes_used: int
    timestamp: float = Field(default_factory=time.time)

class TrainingConfig(BaseModel):
    model_name: str = "Qwen/Qwen2.5-0.5B-Instruct"
    method: RLMethod = RLMethod.GRPO
    learning_rate: float = 1e-5
    batch_size: int = 4
    num_generations: int = 4
    max_new_tokens: int = 128
    temperature: float = 0.9
    kl_coef: float = 0.1
    train_every: int = 5
    total_games: int = 100
    save_every: int = 10
    device: str = "cpu"
    checkpoint_dir: str = "training/checkpoints"
    data_dir: str = "training/data"


# ── WebSocket Event Models ─────────────────────────────────────────────────────

class WSEvent(BaseModel):
    """Generic WebSocket event envelope."""
    type: EventType
    timestamp: float = Field(default_factory=time.time)
    data: Dict[str, Any] = Field(default_factory=dict)

class GameStartEvent(BaseModel):
    game_id: str
    white_agent: str
    black_agent: str
    white_wallet: float
    black_wallet: float
    entry_fee: float

class MoveEvent(BaseModel):
    game_id: str
    player: str
    move_uci: str
    fen: str
    move_number: int
    wallet_white: float
    wallet_black: float
    used_coaching: bool = False

class GameEndEvent(BaseModel):
    game_id: str
    outcome: GameOutcome
    winner: Optional[str]
    white_wallet_final: float
    black_wallet_final: float
    prize_paid: float
    total_moves: int

class TrainingStepEvent(BaseModel):
    step: int
    loss: float
    reward: float
    kl_div: float
    win_rate: float
    avg_profit: float
    coaching_rate: float

class EconomyUpdateEvent(BaseModel):
    game_number: int
    white_wallet: float
    black_wallet: float
    prize_income: float
    coaching_cost: float
    entry_fee: float
    net_pnl: float
    cumulative_pnl: float
