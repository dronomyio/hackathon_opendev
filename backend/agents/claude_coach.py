"""
ChessEcon Backend — Claude Coach Agent
Calls Anthropic claude-opus-4-5 ONLY when position complexity warrants it.
This is a fee-charging service that agents must decide to use.
"""
from __future__ import annotations
import os
import re
import logging
from typing import Optional
from shared.models import CoachingRequest, CoachingResponse

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL      = os.getenv("CLAUDE_MODEL", "claude-opus-4-5")
CLAUDE_MAX_TOKENS = int(os.getenv("CLAUDE_MAX_TOKENS", "1024"))
COACHING_FEE      = float(os.getenv("COACHING_FEE", "5.0"))


class ClaudeCoachAgent:
    """
    Premium coaching service backed by Claude claude-opus-4-5.
    Called only for COMPLEX or CRITICAL positions where the agent
    has explicitly requested coaching AND can afford the fee.
    """

    def __init__(self):
        self._client = None
        self._available = bool(ANTHROPIC_API_KEY)
        if self._available:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
                logger.info(f"Claude Coach initialized with model {CLAUDE_MODEL}")
            except ImportError:
                logger.warning("anthropic package not installed — Claude Coach disabled")
                self._available = False
        else:
            logger.warning("ANTHROPIC_API_KEY not set — Claude Coach disabled")

    @property
    def available(self) -> bool:
        return self._available and self._client is not None

    def analyze(self, request: CoachingRequest) -> CoachingResponse:
        """
        Request chess analysis from Claude. Returns best move recommendation
        and strategic reasoning. Falls back to heuristic if unavailable.
        """
        if not self.available:
            return self._fallback(request)

        prompt = self._build_prompt(request)
        try:
            response = self._client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=CLAUDE_MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text
            tokens_used = response.usage.input_tokens + response.usage.output_tokens
            recommended_move = self._extract_move(content, request.legal_moves)

            logger.info(
                f"Claude coaching: game={request.game_id} "
                f"agent={request.agent_id} move={recommended_move} "
                f"tokens={tokens_used}"
            )
            return CoachingResponse(
                game_id=request.game_id,
                agent_id=request.agent_id,
                recommended_move=recommended_move,
                analysis=content,
                cost=COACHING_FEE,
                model_used=CLAUDE_MODEL,
                tokens_used=tokens_used,
            )
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return self._fallback(request)

    def _build_prompt(self, request: CoachingRequest) -> str:
        legal_sample = request.legal_moves[:20]
        return f"""You are an expert chess coach. Analyze this position and recommend the best move.

Position (FEN): {request.fen}
Legal moves (UCI format): {', '.join(legal_sample)}{'...' if len(request.legal_moves) > 20 else ''}
Position complexity: {request.complexity.level.value} (score: {request.complexity.score:.2f})
Your wallet: {request.wallet_balance:.1f} units (you paid {COACHING_FEE} for this analysis)

Provide:
1. The single best move in UCI format (e.g., e2e4)
2. Brief strategic reasoning (2-3 sentences)
3. Key tactical threats to watch

Start your response with: BEST MOVE: <uci_move>"""

    def _extract_move(self, text: str, legal_moves: list) -> str:
        """Extract the recommended UCI move from Claude's response."""
        # Try explicit BEST MOVE: pattern first
        match = re.search(r"BEST MOVE:\s*([a-h][1-8][a-h][1-8][qrbn]?)", text, re.IGNORECASE)
        if match:
            move = match.group(1).lower()
            if move in legal_moves:
                return move

        # Scan for any UCI move mentioned in the text
        for token in re.findall(r"\b([a-h][1-8][a-h][1-8][qrbn]?)\b", text):
            if token.lower() in legal_moves:
                return token.lower()

        # Fallback: return first legal move
        return legal_moves[0] if legal_moves else "e2e4"

    def _fallback(self, request: CoachingRequest) -> CoachingResponse:
        """Return a basic heuristic move when Claude is unavailable."""
        move = request.legal_moves[0] if request.legal_moves else "e2e4"
        return CoachingResponse(
            game_id=request.game_id,
            agent_id=request.agent_id,
            recommended_move=move,
            analysis="Claude unavailable — using heuristic fallback.",
            cost=0.0,
            model_used="heuristic",
            tokens_used=0,
        )


# Singleton
claude_coach = ClaudeCoachAgent()
