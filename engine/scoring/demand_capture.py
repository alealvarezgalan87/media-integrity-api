"""Demand Capture Integrity Score — Weight: 0.25.

Question: Is the account capturing the demand available to it?

Inputs:
- avg_search_impression_share
- avg_budget_lost_impression_share
- avg_rank_lost_impression_share
- avg_outranking_share (from auction_density)
"""

from engine.scoring.base_score import BaseDomainScore, ScoreResult


class DemandCaptureIntegrityScore(BaseDomainScore):
    """Computes the Demand Capture Integrity domain score."""

    domain_name = "demand_capture_integrity"
    weight = 0.25

    def compute(self, data: dict) -> ScoreResult:
        """Compute Demand Capture Integrity Score.

        Sub-scores:
        1. Impression Share Health (40%)
        2. Budget Constraint Penalty (25%)
        3. Rank Competitiveness (20%)
        4. Competitive Position (15%)
        """
        findings = []

        # 1. Impression Share Health (40%)
        is_val = data.get("avg_search_impression_share", 0.5)
        is_score = is_val * 100
        if is_val < 0.30:
            findings.append(f"Search impression share critically low at {is_val:.0%}")
        elif is_val < 0.50:
            findings.append(f"Search impression share averaging {is_val:.0%} — significant demand uncaptured")

        # 2. Budget Constraint Penalty (25%)
        budget_lost = data.get("avg_budget_lost_impression_share", 0.0)
        budget_penalty = (1 - budget_lost) * 100
        if budget_lost > 0.20:
            findings.append(f"Budget-lost IS at {budget_lost:.0%} — budget constraint is primary limiter")

        # 3. Rank Competitiveness (20%)
        rank_lost = data.get("avg_rank_lost_impression_share", 0.0)
        rank_score = (1 - rank_lost) * 100
        if rank_lost > 0.30:
            findings.append(f"Rank-lost IS at {rank_lost:.0%} — quality/bid issues")

        # 4. Competitive Position (15%)
        outranking = data.get("avg_outranking_share")
        if outranking is not None:
            competitive_score = outranking * 100
            findings.append(f"Competitive outranking: {outranking:.0%}")
            completeness = 1.0
        else:
            competitive_score = 50  # Neutral default
            completeness = 0.85
            findings.append("Auction insights unavailable — competitive position estimated")

        score = (
            is_score * 0.40
            + budget_penalty * 0.25
            + rank_score * 0.20
            + competitive_score * 0.15
        )

        value = self.clamp(score)

        return ScoreResult(
            domain=self.domain_name,
            value=value,
            weight=self.weight,
            weighted_contribution=round(value * self.weight, 2),
            key_findings=findings,
            data_completeness=completeness,
            sub_scores={
                "impression_share_health": round(is_score, 1),
                "budget_constraint_penalty": round(budget_penalty, 1),
                "rank_competitiveness": round(rank_score, 1),
                "competitive_position": round(competitive_score, 1),
            },
        )
