"""
ChessEcon — Chess Analysis API Router (Nevermined-Protected)
=============================================================
Exposes POST /api/chess/analyze as a paid service endpoint using the
x402 payment protocol. Other teams' agents can:

  1. Discover this endpoint via the Nevermined marketplace
  2. Subscribe to the ChessEcon Coaching Plan (NVM_PLAN_ID)
  3. Generate an x402 access token
  4. Call this endpoint with the token in the `payment-signature` header
  5. Receive chess position analysis powered by Claude Opus 4.5

Payment flow:
  - No token → HTTP 402 with `payment-required` header (base64-encoded spec)
  - Invalid token → HTTP 402 with error reason
  - Valid token → Analysis delivered, 1 credit settled automatically

The endpoint also works WITHOUT Nevermined (NVM_API_KEY not set) for
local development and testing — payment verification is skipped.
"""
from __future__ import annotations

import base64
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.agents.claude_coach import claude_coach
from backend.agents.complexity import ComplexityAnalyzer
from backend.economy.nvm_payments import nvm_manager, NVM_PLAN_ID, NVM_AGENT_ID
from shared.models import CoachingRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chess", tags=["chess-analysis"])

# ── Request / Response models ──────────────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    """Chess position analysis request."""
    fen: str
    legal_moves: List[str]
    game_id: Optional[str] = "external"
    agent_id: Optional[str] = "external_agent"
    context: Optional[str] = None  # Optional game context for richer analysis


class AnalyzeResponse(BaseModel):
    """Chess position analysis response."""
    recommended_move: str
    analysis: str
    complexity_score: float
    complexity_level: str
    model_used: str
    credits_used: int = 1
    nvm_plan_id: Optional[str] = None
    nvm_agent_id: Optional[str] = None


# ── Payment helper ─────────────────────────────────────────────────────────────
def _make_402_response(endpoint: str, http_verb: str = "POST") -> JSONResponse:
    """
    Return an HTTP 402 response with the x402 payment-required header.
    The header contains a base64-encoded PaymentRequired specification
    that tells clients exactly how to pay for this service.
    """
    payment_required = nvm_manager.build_payment_required(endpoint, http_verb)

    if payment_required is None:
        # NVM not configured — return plain 402
        return JSONResponse(
            status_code=402,
            content={
                "error": "Payment Required",
                "message": (
                    "This endpoint requires a Nevermined payment token. "
                    f"Subscribe to plan {NVM_PLAN_ID} and include "
                    "the x402 access token in the 'payment-signature' header."
                ),
                "nvm_plan_id": NVM_PLAN_ID or None,
                "nvm_agent_id": NVM_AGENT_ID or None,
                "docs": "https://nevermined.ai/docs/integrate/quickstart/5-minute-setup",
            },
        )

    # Encode the payment spec per x402 spec
    pr_json = payment_required.model_dump_json(by_alias=True)
    pr_base64 = base64.b64encode(pr_json.encode()).decode()

    return JSONResponse(
        status_code=402,
        content={
            "error": "Payment Required",
            "message": (
                "Include your x402 access token in the 'payment-signature' header. "
                f"Subscribe to plan: {NVM_PLAN_ID}"
            ),
            "nvm_plan_id": NVM_PLAN_ID or None,
            "nvm_agent_id": NVM_AGENT_ID or None,
            "docs": "https://nevermined.ai/docs/integrate/quickstart/5-minute-setup",
        },
        headers={"payment-required": pr_base64},
    )


# ── Main endpoint ──────────────────────────────────────────────────────────────
@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_position(request: Request, body: AnalyzeRequest):
    """
    **Paid chess position analysis endpoint.**

    Analyzes a chess position and returns the best move recommendation
    with strategic reasoning, powered by Claude Opus 4.5.

    **Payment:**
    - Requires a Nevermined x402 access token in the `payment-signature` header
    - Each call costs 1 credit from your subscribed plan
    - Subscribe at: https://nevermined.app/en/subscription/{NVM_PLAN_ID}

    **Without payment (NVM not configured):**
    - Falls back to heuristic analysis (no Claude)

    **Request body:**
    ```json
    {
      "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
      "legal_moves": ["e7e5", "d7d5", "g8f6", ...],
      "game_id": "game_001",
      "agent_id": "my_agent"
    }
    ```

    **Headers:**
    - `payment-signature`: x402 access token (required when NVM is active)

    **Response:**
    ```json
    {
      "recommended_move": "e7e5",
      "analysis": "The move e7e5 controls the center...",
      "complexity_score": 0.42,
      "complexity_level": "moderate",
      "model_used": "claude-opus-4-5",
      "credits_used": 1
    }
    ```
    """
    endpoint_url = str(request.url)
    http_verb = request.method

    # ── x402 Payment Verification ──────────────────────────────────────────────
    x402_token = request.headers.get("payment-signature")

    if nvm_manager.available:
        if not x402_token:
            logger.info(
                f"No payment-signature header for /api/chess/analyze "
                f"from {request.client.host if request.client else 'unknown'}"
            )
            return _make_402_response(endpoint_url, http_verb)

        is_valid, reason = nvm_manager.verify_token(
            x402_token=x402_token,
            endpoint=endpoint_url,
            http_verb=http_verb,
            max_credits="1",
        )

        if not is_valid:
            logger.warning(f"Payment verification failed: {reason}")
            return JSONResponse(
                status_code=402,
                content={
                    "error": "Payment Verification Failed",
                    "reason": reason,
                    "nvm_plan_id": NVM_PLAN_ID or None,
                },
            )

    # ── Chess Analysis ─────────────────────────────────────────────────────────
    # Assess position complexity
    analyzer = ComplexityAnalyzer()
    complexity = analyzer.analyze(body.fen, body.legal_moves)

    # Build coaching request
    coaching_req = CoachingRequest(
        game_id=body.game_id or "external",
        agent_id=body.agent_id or "external_agent",
        fen=body.fen,
        legal_moves=body.legal_moves,
        wallet_balance=0.0,  # External agents don't use internal wallet
        complexity=complexity,
    )

    # Get analysis from Claude (or fallback)
    coaching_resp = claude_coach.analyze(coaching_req)

    # ── Settle Credits ─────────────────────────────────────────────────────────
    if nvm_manager.available and x402_token:
        nvm_manager.settle_token(
            x402_token=x402_token,
            endpoint=endpoint_url,
            http_verb=http_verb,
            max_credits="1",
        )

    response_data = AnalyzeResponse(
        recommended_move=coaching_resp.recommended_move,
        analysis=coaching_resp.analysis,
        complexity_score=complexity.score,
        complexity_level=complexity.level.value,
        model_used=coaching_resp.model_used,
        credits_used=1,
        nvm_plan_id=NVM_PLAN_ID or None,
        nvm_agent_id=NVM_AGENT_ID or None,
    )

    logger.info(
        f"Chess analysis served: game={body.game_id} "
        f"agent={body.agent_id} move={coaching_resp.recommended_move} "
        f"model={coaching_resp.model_used} "
        f"nvm={'settled' if (nvm_manager.available and x402_token) else 'skipped'}"
    )

    return response_data


# ── Service info endpoint (public, no payment required) ────────────────────────
@router.get("/service-info")
async def service_info():
    """
    Public endpoint returning ChessEcon service information.
    Other agents can call this to discover how to subscribe and pay.
    """
    return {
        "service": "ChessEcon Chess Analysis",
        "description": (
            "Premium chess position analysis powered by Claude Opus 4.5. "
            "Subscribe to get best-move recommendations and strategic coaching."
        ),
        "endpoint": "/api/chess/analyze",
        "method": "POST",
        "payment": {
            "protocol": "x402",
            "nvm_plan_id": NVM_PLAN_ID or "not configured",
            "nvm_agent_id": NVM_AGENT_ID or "not configured",
            "credits_per_request": 1,
            "marketplace_url": (
                f"https://nevermined.app/en/subscription/{NVM_PLAN_ID}"
                if NVM_PLAN_ID else "not configured"
            ),
            "how_to_subscribe": [
                "1. Get NVM API key at https://nevermined.app",
                "2. Call payments.plans.order_plan(NVM_PLAN_ID)",
                "3. Call payments.x402.get_x402_access_token(NVM_PLAN_ID, NVM_AGENT_ID)",
                "4. Include token in 'payment-signature' header",
            ],
        },
        "nvm_available": nvm_manager.available,
        "claude_available": claude_coach.available,
        "docs": "https://nevermined.ai/docs/integrate/quickstart/5-minute-setup",
    }


# ── NVM transaction history (for dashboard) ────────────────────────────────────
@router.get("/nvm-transactions")
async def get_nvm_transactions(limit: int = 50):
    """Return recent Nevermined payment transactions for dashboard display."""
    return {
        "transactions": nvm_manager.get_transactions(limit=limit),
        "nvm_status": nvm_manager.get_status(),
    }
