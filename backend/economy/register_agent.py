"""
ChessEcon — Nevermined Agent Registration Script
=================================================
Run this ONCE to register the ChessEcon chess analysis service in the
Nevermined marketplace. It creates:
  1. A payment plan (credits-based, free for hackathon demo)
  2. An agent entry pointing to the /api/chess/analyze endpoint

After running, copy the printed NVM_PLAN_ID and NVM_AGENT_ID into your .env.

Usage:
    cd chessecon-v2
    python -m backend.economy.register_agent

Environment variables required:
    NVM_API_KEY        — Your Nevermined API key (sandbox:xxx...)
    CHESSECON_API_URL  — Public URL of your ChessEcon backend
                         e.g. https://your-server.com or https://ngrok-url.ngrok.io
"""
from __future__ import annotations

import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname )s: %(message)s")
logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
NVM_API_KEY = os.getenv("NVM_API_KEY", "")
NVM_ENVIRONMENT = os.getenv("NVM_ENVIRONMENT", "sandbox")
CHESSECON_API_URL = os.getenv("CHESSECON_API_URL", "https://chessecon.example.com" )

# Service description
SERVICE_NAME = "ChessEcon Chess Analysis"
SERVICE_DESCRIPTION = (
    "Premium chess position analysis powered by Claude Opus 4.5. "
    "Provides best-move recommendations, tactical threat assessment, "
    "and strategic coaching for AI chess agents. "
    "Part of the ChessEcon multi-agent chess economy — "
    "agents earn money playing chess and spend it on coaching."
)
SERVICE_TAGS = ["chess", "ai", "coaching", "analysis", "game", "rl", "hackathon"]

# Plan: free credits for hackathon demo
# 1000 credits, 1 credit per request — free to subscribe
PLAN_NAME = "ChessEcon Coaching Plan (Hackathon)"
PLAN_DESCRIPTION = (
    "1000 free credits for chess position analysis. "
    "Each analysis request costs 1 credit. "
    "Subscribe to access the ChessEcon coaching endpoint."
)
CREDITS_GRANTED = 1000
CREDITS_PER_REQUEST = 1


def register():
    """Register ChessEcon as a paid agent service in Nevermined."""
    if not NVM_API_KEY:
        logger.error(
            "NVM_API_KEY is not set. "
            "Get your key at https://nevermined.app and set it in .env"
         )
        sys.exit(1)

    logger.info(f"Initializing Nevermined SDK (environment={NVM_ENVIRONMENT})")

    try:
        from payments_py import Payments, PaymentOptions
        from payments_py.common.types import AgentMetadata, AgentAPIAttributes, PlanMetadata, Endpoint
        from payments_py.plans import get_free_price_config, get_fixed_credits_config
    except ImportError:
        logger.error("payments-py not installed. Run: pip install payments-py")
        sys.exit(1)

    payments = Payments.get_instance(
        PaymentOptions(
            nvm_api_key=NVM_API_KEY,
            environment=NVM_ENVIRONMENT,
        )
    )

    analyze_endpoint = f"{CHESSECON_API_URL}/api/chess/analyze"
    openapi_url = f"{CHESSECON_API_URL}/openapi.json"

    logger.info(f"Registering agent at: {analyze_endpoint}")
    logger.info(f"OpenAPI spec: {openapi_url}")

    try:
        result = payments.agents.register_agent_and_plan(
            agent_metadata=AgentMetadata(
                name=SERVICE_NAME,
                description=SERVICE_DESCRIPTION,
                tags=SERVICE_TAGS,
            ),
            agent_api=AgentAPIAttributes(
                endpoints=[Endpoint(verb="POST", url=analyze_endpoint)],
                open_endpoints=[f"{CHESSECON_API_URL}/health"],
                agent_definition_url=openapi_url,
            ),
            plan_metadata=PlanMetadata(
                name=PLAN_NAME,
                description=PLAN_DESCRIPTION,
            ),
            price_config=get_free_price_config(),
            credits_config=get_fixed_credits_config(
                credits_granted=CREDITS_GRANTED,
                credits_per_request=CREDITS_PER_REQUEST,
            ),
            access_limit="credits",
        )

        agent_id = result.get("agentId", "")
        plan_id = result.get("planId", "")

        print("\n" + "=" * 60)
        print("✅  ChessEcon registered on Nevermined!")
        print("=" * 60)
        print(f"  NVM_AGENT_ID = {agent_id}")
        print(f"  NVM_PLAN_ID  = {plan_id}")
        print("=" * 60)
        print("\nAdd these to your .env file:")
        print(f"  NVM_AGENT_ID={agent_id}")
        print(f"  NVM_PLAN_ID={plan_id}")
        print("\nMarketplace URL:")
        print(f"  https://nevermined.app/en/subscription/{plan_id}" )
        print("=" * 60 + "\n")

        return agent_id, plan_id

    except Exception as exc:
        logger.error(f"Registration failed: {exc}")
        raise


if __name__ == "__main__":
    register()

