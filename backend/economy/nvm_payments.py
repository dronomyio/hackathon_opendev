"""
ChessEcon — Nevermined Payment Manager
=======================================
Wraps the payments-py SDK to provide a clean interface for:
  - Initializing the Nevermined Payments client
  - Verifying x402 payment tokens on incoming requests
  - Settling credits after successful service delivery
  - Ordering plans and generating access tokens (subscriber side)
  - Tracking NVM transactions for the dashboard

This replaces the internal ledger for cross-team agent-to-agent payments.
The internal ledger (economy/ledger.py) is still used for intra-team
tournament accounting (entry fees, prize pools).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Environment ────────────────────────────────────────────────────────────────
NVM_API_KEY = os.getenv("NVM_API_KEY", "")
NVM_ENVIRONMENT = os.getenv("NVM_ENVIRONMENT", "sandbox")
NVM_PLAN_ID = os.getenv("NVM_PLAN_ID", "")
NVM_AGENT_ID = os.getenv("NVM_AGENT_ID", "")

# ── Transaction record ─────────────────────────────────────────────────────────
@dataclass
class NvmTransaction:
    """A recorded Nevermined payment transaction."""
    tx_id: str
    tx_type: str          # "verify" | "settle" | "order" | "token"
    agent_id: str
    plan_id: str
    credits: int
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None


# ── Nevermined Payment Manager ─────────────────────────────────────────────────
class NeverminedPaymentManager:
    """
    Singleton manager for all Nevermined payment operations.

    Usage (server side — verify + settle):
        nvm = NeverminedPaymentManager()
        if nvm.available:
            ok, reason = nvm.verify_token(token, request_url, "POST")
            if ok:
                # ... handle request ...
                nvm.settle_token(token, request_url, "POST")

    Usage (client/agent side — order + get token):
        nvm = NeverminedPaymentManager()
        if nvm.available:
            nvm.order_plan(plan_id)
            token = nvm.get_access_token(plan_id, agent_id)
    """

    def __init__(self):
        self._payments = None
        self._available = False
        self._transactions: List[NvmTransaction] = []
        self._init_sdk()

    def _init_sdk(self):
        """Initialize the payments-py SDK if NVM_API_KEY is configured."""
        if not NVM_API_KEY:
            logger.warning(
                "NVM_API_KEY not set — Nevermined payments disabled. "
                "Set NVM_API_KEY in .env to enable cross-team agent payments."
            )
            return
        try:
            from payments_py import Payments, PaymentOptions
            self._payments = Payments.get_instance(
                PaymentOptions(
                    nvm_api_key=NVM_API_KEY,
                    environment=NVM_ENVIRONMENT,
                )
            )
            self._available = True
            logger.info(
                f"Nevermined Payments SDK initialized "
                f"(environment={NVM_ENVIRONMENT}, "
                f"plan_id={NVM_PLAN_ID or 'not set'}, "
                f"agent_id={NVM_AGENT_ID or 'not set'})"
            )
        except Exception as exc:
            logger.error(f"Failed to initialize Nevermined SDK: {exc}")
            self._available = False

    # ── Properties ─────────────────────────────────────────────────────────────
    @property
    def available(self) -> bool:
        return self._available and self._payments is not None

    @property
    def payments(self):
        return self._payments

    # ── Server-side: verify + settle ───────────────────────────────────────────
    def build_payment_required(
        self,
        endpoint: str,
        http_verb: str = "POST",
        plan_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ):
        """Build a PaymentRequired spec for a protected endpoint."""
        if not self.available:
            return None
        try:
            from payments_py.x402.helpers import build_payment_required
            return build_payment_required(
                plan_id=plan_id or NVM_PLAN_ID,
                endpoint=endpoint,
                agent_id=agent_id or NVM_AGENT_ID,
                http_verb=http_verb,
            )
        except Exception as exc:
            logger.error(f"build_payment_required failed: {exc}")
            return None

    def verify_token(
        self,
        x402_token: str,
        endpoint: str,
        http_verb: str = "POST",
        max_credits: str = "1",
        plan_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Verify an x402 access token WITHOUT burning credits.

        Returns:
            (is_valid, error_reason)
        """
        if not self.available:
            # Graceful degradation: allow requests when NVM not configured
            logger.debug("NVM not available — skipping payment verification")
            return True, None

        payment_required = self.build_payment_required(endpoint, http_verb, plan_id, agent_id)
        if payment_required is None:
            return False, "Could not build payment_required spec"

        try:
            verification = self._payments.facilitator.verify_permissions(
                payment_required=payment_required,
                x402_access_token=x402_token,
                max_amount=max_credits,
            )
            is_valid = verification.is_valid
            reason = None if is_valid else (verification.invalid_reason or "Verification failed")

            self._record_transaction(
                tx_type="verify",
                agent_id=agent_id or NVM_AGENT_ID,
                plan_id=plan_id or NVM_PLAN_ID,
                credits=int(max_credits),
                success=is_valid,
                error=reason,
                details={"endpoint": endpoint, "verb": http_verb},
            )
            return is_valid, reason
        except Exception as exc:
            logger.error(f"verify_permissions failed: {exc}")
            return False, str(exc)

    def settle_token(
        self,
        x402_token: str,
        endpoint: str,
        http_verb: str = "POST",
        max_credits: str = "1",
        plan_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> bool:
        """
        Settle (burn) credits after successful service delivery.

        Returns:
            True if settlement succeeded, False otherwise.
        """
        if not self.available:
            return True  # No-op when NVM not configured

        payment_required = self.build_payment_required(endpoint, http_verb, plan_id, agent_id)
        if payment_required is None:
            return False

        try:
            settlement = self._payments.facilitator.settle_permissions(
                payment_required=payment_required,
                x402_access_token=x402_token,
                max_amount=max_credits,
            )
            credits_burned = getattr(settlement, "credits_redeemed", int(max_credits))
            self._record_transaction(
                tx_type="settle",
                agent_id=agent_id or NVM_AGENT_ID,
                plan_id=plan_id or NVM_PLAN_ID,
                credits=credits_burned,
                success=True,
                details={"endpoint": endpoint, "verb": http_verb},
            )
            logger.info(f"NVM credits settled: {credits_burned} credits for {endpoint}")
            return True
        except Exception as exc:
            logger.error(f"settle_permissions failed: {exc}")
            self._record_transaction(
                tx_type="settle",
                agent_id=agent_id or NVM_AGENT_ID,
                plan_id=plan_id or NVM_PLAN_ID,
                credits=0,
                success=False,
                error=str(exc),
                details={"endpoint": endpoint},
            )
            return False

    # ── Client/agent side: order + token ──────────────────────────────────────
    def order_plan(self, plan_id: str) -> bool:
        """
        Subscribe to a payment plan (purchase credits).

        Returns:
            True if order succeeded.
        """
        if not self.available:
            return False
        try:
            result = self._payments.plans.order_plan(plan_id)
            self._record_transaction(
                tx_type="order",
                agent_id="self",
                plan_id=plan_id,
                credits=0,
                success=True,
                details=result,
            )
            logger.info(f"NVM plan ordered: {plan_id}")
            return True
        except Exception as exc:
            logger.error(f"order_plan failed: {exc}")
            return False

    def get_access_token(
        self,
        plan_id: str,
        agent_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Generate an x402 access token for a purchased plan.

        Returns:
            The access token string, or None on failure.
        """
        if not self.available:
            return None
        try:
            result = self._payments.x402.get_x402_access_token(
                plan_id=plan_id,
                agent_id=agent_id or NVM_AGENT_ID,
            )
            token = result.get("accessToken") or result.get("access_token")
            self._record_transaction(
                tx_type="token",
                agent_id=agent_id or NVM_AGENT_ID,
                plan_id=plan_id,
                credits=0,
                success=bool(token),
            )
            return token
        except Exception as exc:
            logger.error(f"get_x402_access_token failed: {exc}")
            return None

    def get_plan_balance(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Return the current credit balance for a plan."""
        if not self.available:
            return None
        try:
            return self._payments.plans.get_plan_balance(plan_id)
        except Exception as exc:
            logger.error(f"get_plan_balance failed: {exc}")
            return None

    # ── Transaction history ────────────────────────────────────────────────────
    def _record_transaction(self, **kwargs):
        import uuid
        tx = NvmTransaction(
            tx_id=str(uuid.uuid4()),
            **kwargs,
        )
        self._transactions.append(tx)
        # Keep last 500 transactions in memory
        if len(self._transactions) > 500:
            self._transactions = self._transactions[-500:]

    def get_transactions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent NVM transactions for dashboard display."""
        txs = self._transactions[-limit:]
        return [
            {
                "tx_id": t.tx_id,
                "type": t.tx_type,
                "agent_id": t.agent_id,
                "plan_id": t.plan_id,
                "credits": t.credits,
                "timestamp": t.timestamp,
                "success": t.success,
                "error": t.error,
                "details": t.details,
            }
            for t in reversed(txs)
        ]

    def get_status(self) -> Dict[str, Any]:
        """Return NVM integration status for health checks."""
        return {
            "available": self.available,
            "environment": NVM_ENVIRONMENT,
            "plan_id": NVM_PLAN_ID or None,
            "agent_id": NVM_AGENT_ID or None,
            "api_key_set": bool(NVM_API_KEY),
            "transaction_count": len(self._transactions),
        }


# ── Singleton ──────────────────────────────────────────────────────────────────
nvm_manager = NeverminedPaymentManager()
