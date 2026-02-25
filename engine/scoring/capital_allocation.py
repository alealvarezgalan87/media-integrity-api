"""Capital Allocation Discipline Score — Weight: 0.20.

Question: Is money being deployed efficiently and intentionally?

Inputs:
- avg_budget_utilization
- spend_concentration_hhi
- roas_variance_coefficient
- zero_conversion_spend_pct
- campaign_count
"""

from engine.scoring.base_score import BaseDomainScore, ScoreResult


class CapitalAllocationDisciplineScore(BaseDomainScore):
    """Computes the Capital Allocation Discipline domain score."""

    domain_name = "capital_allocation_discipline"
    weight = 0.20

    def compute(self, data: dict) -> ScoreResult:
        """Compute Capital Allocation Discipline Score.

        Sub-scores:
        1. Budget Utilization (25%) — 80-95% ideal
        2. Spend Concentration (25%) — HHI-based
        3. ROAS Variance (25%) — coefficient of variation
        4. Wasted Spend (25%) — zero-conversion campaigns
        """
        findings = []

        # 1. Budget Utilization (25%)
        util = data.get("avg_budget_utilization", 0.85)
        if 0.80 <= util <= 0.95:
            util_score = 100
        elif 0.60 <= util < 0.80:
            util_score = 60 + ((util - 0.60) / 0.20) * 40
        elif util > 0.95:
            util_score = max(50, 100 - ((util - 0.95) / 0.05) * 50)
        else:
            util_score = max(0, (util / 0.60) * 60)
        findings.append(f"Budget utilization: {util:.0%}")

        # 2. Spend Concentration (25%)
        hhi = data.get("spend_concentration_hhi", 0.2)
        n = data.get("campaign_count", 5)
        ideal_hhi = 1.0 / max(n, 1)
        if n <= 3:
            conc_score = 80
        elif hhi <= ideal_hhi * 3:
            conc_score = 100
        elif hhi <= 0.5:
            conc_score = 70
        else:
            conc_score = max(20, 100 - (hhi * 100))

        # 3. ROAS Variance (25%)
        cv = data.get("roas_variance_coefficient", 0.5)
        if cv <= 0.3:
            roas_score = 100
        elif cv <= 0.6:
            roas_score = 100 - ((cv - 0.3) / 0.3) * 40
        elif cv <= 1.0:
            roas_score = 60 - ((cv - 0.6) / 0.4) * 30
        else:
            roas_score = max(0, 30 - ((cv - 1.0) * 20))
        findings.append(f"ROAS variance CV: {cv:.2f}")

        # 4. Wasted Spend (25%)
        waste = data.get("zero_conversion_spend_pct", 0.0)
        if waste <= 0.05:
            waste_score = 100
        elif waste <= 0.15:
            waste_score = 100 - ((waste - 0.05) / 0.10) * 40
        elif waste <= 0.30:
            waste_score = 60 - ((waste - 0.15) / 0.15) * 40
        else:
            waste_score = max(0, 20 - ((waste - 0.30) / 0.20) * 20)
        findings.append(f"Zero-conversion spend: {waste:.0%}")

        score = (
            util_score * 0.25
            + conc_score * 0.25
            + roas_score * 0.25
            + waste_score * 0.25
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
                "budget_utilization": round(util_score, 1),
                "spend_concentration": round(conc_score, 1),
                "roas_variance": round(roas_score, 1),
                "wasted_spend": round(waste_score, 1),
            },
        )
