"""
ChessEcon Backend — Position Complexity Analyzer
Decides when a position is complex enough to warrant calling Claude.
Claude is only called when ALL three gates pass:
  1. Position complexity >= threshold
  2. Agent wallet >= minimum
  3. Agent's own policy requests coaching
"""
from __future__ import annotations
import os
from shared.models import ComplexityAnalysis, PositionComplexity


THRESHOLD_COMPLEX  = float(os.getenv("COMPLEXITY_THRESHOLD_COMPLEX", "0.45"))
THRESHOLD_CRITICAL = float(os.getenv("COMPLEXITY_THRESHOLD_CRITICAL", "0.70"))


class ComplexityAnalyzer:

    def analyze(self, features: dict) -> ComplexityAnalysis:
        """
        Compute a 0–1 complexity score from raw board features.
        Higher = more complex = more likely Claude is useful.
        """
        score = 0.0
        factors: dict = {}

        # Factor 1: Number of legal moves (high = complex position)
        num_moves = features.get("num_legal_moves", 20)
        move_score = min(num_moves / 60.0, 1.0)
        factors["mobility"] = round(move_score, 3)
        score += move_score * 0.30

        # Factor 2: Check pressure
        check_score = 0.8 if features.get("is_check") else 0.0
        factors["check_pressure"] = check_score
        score += check_score * 0.20

        # Factor 3: Tactical captures available
        capture_score = 0.6 if features.get("has_captures") else 0.0
        factors["captures_available"] = capture_score
        score += capture_score * 0.15

        # Factor 4: Endgame (few pieces = precise calculation needed)
        num_pieces = features.get("num_pieces", 32)
        endgame_score = max(0.0, (16 - num_pieces) / 16.0)
        factors["endgame_pressure"] = round(endgame_score, 3)
        score += endgame_score * 0.20

        # Factor 5: Material imbalance (unbalanced = harder to evaluate)
        material = abs(features.get("material_balance", 0.0))
        imbalance_score = min(material / 9.0, 1.0)  # queen = 9
        factors["material_imbalance"] = round(imbalance_score, 3)
        score += imbalance_score * 0.15

        score = round(min(score, 1.0), 4)

        if score >= THRESHOLD_CRITICAL:
            level = PositionComplexity.CRITICAL
        elif score >= THRESHOLD_COMPLEX:
            level = PositionComplexity.COMPLEX
        elif score >= 0.25:
            level = PositionComplexity.MODERATE
        else:
            level = PositionComplexity.SIMPLE

        recommend = level in (PositionComplexity.COMPLEX, PositionComplexity.CRITICAL)

        return ComplexityAnalysis(
            fen=features.get("fen", ""),
            score=score,
            level=level,
            factors=factors,
            recommend_coaching=recommend,
        )


# Singleton
complexity_analyzer = ComplexityAnalyzer()
