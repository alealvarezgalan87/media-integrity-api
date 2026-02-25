"""Automation Exposure Score — Weight: 0.20.

Question: How dependent is the account on automated systems,
and is that dependency well-managed?

Inputs:
- pct_spend_automated
- pct_spend_pmax
- pmax_channel_concentration (HHI)
- bidding_strategy_diversity
"""

from engine.scoring.base_score import BaseDomainScore, ScoreResult


class AutomationExposureScore(BaseDomainScore):
    """Computes the Automation Exposure domain score."""

    domain_name = "automation_exposure"
    weight = 0.20

    def compute(self, data: dict) -> ScoreResult:
        """Compute Automation Exposure Score.

        Sub-scores:
        1. Automation Dependency (30%) — 40-70% is ideal
        2. PMax Concentration (25%) — >50% = high risk
        3. PMax Channel Diversity (25%) — HHI-based
        4. Strategy Diversity (20%) — unique bidding types
        """
        findings = []

        # 1. Automation Dependency (30%)
        auto_pct = data.get("pct_spend_automated", 0.5)
        if 0.40 <= auto_pct <= 0.70:
            auto_score = 100
        elif auto_pct < 0.40:
            auto_score = (auto_pct / 0.40) * 100
        else:
            auto_score = max(0, 100 - ((auto_pct - 0.70) / 0.30) * 60)
        findings.append(f"{auto_pct:.0%} spend on automated bidding")

        # 2. PMax Concentration (25%)
        pmax_pct = data.get("pct_spend_pmax", 0.0)
        if pmax_pct <= 0.30:
            pmax_score = 100
        elif pmax_pct <= 0.50:
            pmax_score = 100 - ((pmax_pct - 0.30) / 0.20) * 30
        else:
            pmax_score = max(0, 70 - ((pmax_pct - 0.50) / 0.50) * 70)
        if pmax_pct > 0.0:
            findings.append(f"PMax: {pmax_pct:.0%} of total budget")

        # 3. PMax Channel Diversity (25%)
        hhi = data.get("pmax_channel_concentration")
        if hhi is not None:
            channel_score = (1 - hhi) * 100
            findings.append(f"PMax channel HHI: {hhi:.2f}")
        else:
            channel_score = 50  # No PMax = neutral

        # 4. Strategy Diversity (20%)
        unique_strategies = data.get("bidding_strategy_diversity", 1)
        if unique_strategies >= 3:
            strategy_score = 100
        elif unique_strategies == 2:
            strategy_score = 70
        else:
            strategy_score = 40
        findings.append(f"{unique_strategies} bidding strategy types in use")

        score = (
            auto_score * 0.30
            + pmax_score * 0.25
            + channel_score * 0.25
            + strategy_score * 0.20
        )

        value = self.clamp(score)

        return ScoreResult(
            domain=self.domain_name,
            value=value,
            weight=self.weight,
            weighted_contribution=round(value * self.weight, 2),
            key_findings=findings,
            data_completeness=1.0,
            sub_scores={
                "automation_dependency": round(auto_score, 1),
                "pmax_concentration": round(pmax_score, 1),
                "pmax_channel_diversity": round(channel_score, 1),
                "strategy_diversity": round(strategy_score, 1),
            },
        )
