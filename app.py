"""
app.py
──────
HuggingFace Spaces entry point.

For Docker-based Spaces (sdk: docker), HF looks for this file but does not
run it — the actual server is started by the Dockerfile CMD.

This file serves as a discoverable Python client that users can copy/paste
to interact with the environment from their own code.

Usage:
    from app import ChessEconClient
    env = ChessEconClient()
    obs, info = env.reset()
    obs, reward, done, truncated, info = env.step("e2e4")
"""

import httpx
from typing import Any

SPACE_URL = "https://adaboostai-chessecon.hf.space"


class ChessEconClient:
    """
    OpenEnv 0.1 client for the ChessEcon environment.

    Compatible with any RL trainer that expects:
        reset()  → (observation, info)
        step()   → (observation, reward, terminated, truncated, info)
        state()  → StateResponse dict
    """

    def __init__(self, base_url: str = SPACE_URL, timeout: float = 30.0):
        self.base = base_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout)

    def reset(self, seed: int | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
        """Start a new episode. Returns (observation, info)."""
        payload: dict[str, Any] = {}
        if seed is not None:
            payload["seed"] = seed
        r = self._client.post(f"{self.base}/env/reset", json=payload)
        r.raise_for_status()
        data = r.json()
        return data["observation"], data.get("info", {})

    def step(self, action: str) -> tuple[dict[str, Any], float, bool, bool, dict[str, Any]]:
        """
        Apply a chess move (UCI e.g. 'e2e4' or SAN e.g. 'e4').
        Returns (observation, reward, terminated, truncated, info).
        """
        r = self._client.post(f"{self.base}/env/step", json={"action": action})
        r.raise_for_status()
        data = r.json()
        return (
            data["observation"],
            data["reward"],
            data["terminated"],
            data["truncated"],
            data.get("info", {}),
        )

    def state(self) -> dict[str, Any]:
        """Return current episode state (read-only)."""
        r = self._client.get(f"{self.base}/env/state")
        r.raise_for_status()
        return r.json()

    def env_info(self) -> dict[str, Any]:
        """Return environment metadata."""
        r = self._client.get(f"{self.base}/env/env_info")
        r.raise_for_status()
        return r.json()

    def health(self) -> dict[str, Any]:
        r = self._client.get(f"{self.base}/health")
        r.raise_for_status()
        return r.json()

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# ── Quick demo ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json

    with ChessEconClient() as env:
        print("Environment info:")
        print(json.dumps(env.env_info(), indent=2))

        print("\nResetting …")
        obs, info = env.reset()
        print(f"  FEN:   {obs['fen']}")
        print(f"  Turn:  {obs['turn']}")
        print(f"  Wallet W={obs['wallet_white']}  B={obs['wallet_black']}")

        print("\nPlaying e2e4 …")
        obs, reward, done, truncated, info = env.step("e2e4")
        print(f"  Reward: {reward}")
        print(f"  Done:   {done}")
        print(f"  FEN:    {obs['fen']}")
