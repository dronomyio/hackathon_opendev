"""
ChessEcon — NVM-Aware Player Agent
====================================
Extends the chess player agent with Nevermined payment capabilities.
This agent can:
  1. Discover external coaching services via Nevermined marketplace
  2. Purchase coaching plans from other teams' agents
  3. Generate x402 access tokens for paid service calls
  4. Make HTTP requests to external coaching endpoints with payment headers
  5. Fall back to internal Claude coaching if external service fails

This demonstrates the core hackathon requirement: autonomous agents
making real economic decisions — buy, pay, switch, stop.

Economic decision logic:
  - If position complexity > threshold AND wallet balance > min_balance:
      → Try external NVM coaching first (cross-team transaction)
      → Fall back to internal Claude coaching
      → Fall back to heuristic
  - Track spending vs. performance to decide when to stop coaching
"""
from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
# External coaching service (another team's endpoint)
# Set EXTERNAL_COACHING_URL to use cross-team agent payments
EXTERNAL_COACHING_URL = os.getenv("EXTERNAL_COACHING_URL", "")
EXTERNAL_NVM_PLAN_ID = os.getenv("EXTERNAL_NVM_PLAN_ID", "")
EXTERNAL_NVM_AGENT_ID = os.getenv("EXTERNAL_NVM_AGENT_ID", "")

# Internal NVM credentials (for purchasing external services)
NVM_API_KEY = os.getenv("NVM_API_KEY", "")
NVM_ENVIRONMENT = os.getenv("NVM_ENVIRONMENT", "sandbox")

# Economic thresholds
EXTERNAL_COACHING_BUDGET = float(os.getenv("EXTERNAL_COACHING_BUDGET", "50.0"))
MIN_WALLET_FOR_EXTERNAL = float(os.getenv("MIN_WALLET_FOR_EXTERNAL", "20.0"))


class NvmPlayerAgent:
    """
    A chess player agent that makes autonomous economic decisions
    using Nevermined for cross-team agent-to-agent payments.
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self._payments = None
        self._nvm_available = False
        self._external_token: Optional[str] = None
        self._external_plan_ordered = False
        self._total_external_spend = 0.0
        self._external_calls = 0
        self._external_successes = 0
        self._init_nvm()

    def _init_nvm(self):
        """Initialize Nevermined SDK for purchasing external services."""
        if not NVM_API_KEY:
            logger.debug(f"Agent {self.agent_id}: NVM_API_KEY not set, external payments disabled")
            return
        try:
            from payments_py import Payments, PaymentOptions
            self._payments = Payments.get_instance(
                PaymentOptions(
                    nvm_api_key=NVM_API_KEY,
                    environment=NVM_ENVIRONMENT,
                )
            )
            self._nvm_available = True
            logger.info(f"Agent {self.agent_id}: NVM SDK initialized")
        except Exception as exc:
            logger.warning(f"Agent {self.agent_id}: NVM init failed: {exc}")

    # ── External coaching via NVM ──────────────────────────────────────────────
    def can_use_external_coaching(self, wallet_balance: float) -> bool:
        """
        Decide whether to use external coaching based on:
          - NVM availability
          - External service configured
          - Wallet balance above threshold
          - Budget not exhausted
        """
        return (
            self._nvm_available
            and bool(EXTERNAL_COACHING_URL)
            and bool(EXTERNAL_NVM_PLAN_ID)
            and wallet_balance >= MIN_WALLET_FOR_EXTERNAL
            and self._total_external_spend < EXTERNAL_COACHING_BUDGET
        )

    def _ensure_plan_ordered(self) -> bool:
        """
        Order the external coaching plan if not already done.
        This is the 'buy' decision — agent autonomously purchases a service.
        """
        if self._external_plan_ordered:
            return True
        if not self._nvm_available or not EXTERNAL_NVM_PLAN_ID:
            return False

        try:
            logger.info(
                f"Agent {self.agent_id}: Ordering external coaching plan {EXTERNAL_NVM_PLAN_ID}"
            )
            result = self._payments.plans.order_plan(EXTERNAL_NVM_PLAN_ID)
            self._external_plan_ordered = True
            logger.info(f"Agent {self.agent_id}: Plan ordered successfully: {result}")
            return True
        except Exception as exc:
            logger.warning(f"Agent {self.agent_id}: Failed to order plan: {exc}")
            return False

    def _get_access_token(self) -> Optional[str]:
        """
        Get or refresh the x402 access token for the external coaching service.
        """
        if not self._nvm_available or not EXTERNAL_NVM_PLAN_ID:
            return None

        try:
            result = self._payments.x402.get_x402_access_token(
                plan_id=EXTERNAL_NVM_PLAN_ID,
                agent_id=EXTERNAL_NVM_AGENT_ID or None,
            )
            token = result.get("accessToken") or result.get("access_token")
            self._external_token = token
            return token
        except Exception as exc:
            logger.warning(f"Agent {self.agent_id}: Failed to get access token: {exc}")
            return None

    def request_external_coaching(
        self,
        fen: str,
        legal_moves: List[str],
        game_id: str,
        wallet_balance: float,
    ) -> Optional[Dict]:
        """
        Request chess analysis from an external agent service via Nevermined.

        This is the core cross-team agent-to-agent payment flow:
          1. Order plan (if not already done)
          2. Get x402 access token
          3. Call external endpoint with payment-signature header
          4. Track spending

        Returns:
            Analysis dict with 'recommended_move' and 'analysis', or None on failure.
        """
        if not self.can_use_external_coaching(wallet_balance):
            return None

        # Step 1: Ensure plan is ordered (buy decision)
        if not self._ensure_plan_ordered():
            logger.warning(f"Agent {self.agent_id}: Could not order external plan")
            return None

        # Step 2: Get access token (pay decision)
        token = self._get_access_token()
        if not token:
            logger.warning(f"Agent {self.agent_id}: Could not get access token")
            return None

        # Step 3: Call external coaching endpoint
        try:
            self._external_calls += 1
            response = httpx.post(
                f"{EXTERNAL_COACHING_URL}/api/chess/analyze",
                headers={
                    "Content-Type": "application/json",
                    "payment-signature": token,
                },
                json={
                    "fen": fen,
                    "legal_moves": legal_moves[:30],  # Limit for API efficiency
                    "game_id": game_id,
                    "agent_id": self.agent_id,
                },
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                self._external_successes += 1
                self._total_external_spend += 1.0  # 1 credit per call
                logger.info(
                    f"Agent {self.agent_id}: External coaching success "
                    f"move={data.get('recommended_move')} "
                    f"model={data.get('model_used')} "
                    f"total_spend={self._total_external_spend}"
                )
                return data

            elif response.status_code == 402:
                logger.warning(
                    f"Agent {self.agent_id}: External coaching returned 402 — "
                    "insufficient credits or invalid token"
                )
                # Reset token so it gets refreshed next time
                self._external_token = None
                return None

            else:
                logger.warning(
                    f"Agent {self.agent_id}: External coaching returned {response.status_code}"
                )
                return None

        except httpx.TimeoutException:
            logger.warning(f"Agent {self.agent_id}: External coaching request timed out")
            return None
        except Exception as exc:
            logger.error(f"Agent {self.agent_id}: External coaching request failed: {exc}")
            return None

    # ── Economic decision: switch / stop ───────────────────────────────────────
    def should_stop_external_coaching(self) -> bool:
        """
        Autonomous 'stop' decision: stop buying external coaching if
        the ROI is poor (low success rate) or budget is exhausted.
        """
        if self._total_external_spend >= EXTERNAL_COACHING_BUDGET:
            logger.info(
                f"Agent {self.agent_id}: External coaching budget exhausted "
                f"(spent={self._total_external_spend:.1f})"
            )
            return True

        if self._external_calls >= 10:
            success_rate = self._external_successes / self._external_calls
            if success_rate < 0.5:
                logger.info(
                    f"Agent {self.agent_id}: Stopping external coaching due to low success rate "
                    f"({success_rate:.0%})"
                )
                return True

        return False

    def get_stats(self) -> Dict:
        """Return agent economic stats for dashboard display."""
        return {
            "agent_id": self.agent_id,
            "nvm_available": self._nvm_available,
            "external_coaching_url": EXTERNAL_COACHING_URL or None,
            "external_plan_id": EXTERNAL_NVM_PLAN_ID or None,
            "plan_ordered": self._external_plan_ordered,
            "external_calls": self._external_calls,
            "external_successes": self._external_successes,
            "total_external_spend": self._total_external_spend,
            "success_rate": (
                self._external_successes / self._external_calls
                if self._external_calls > 0 else 0.0
            ),
        }
