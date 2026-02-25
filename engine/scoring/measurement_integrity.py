"""Measurement Integrity Score — Weight: 0.25.

Question: Can the account's measurement system be trusted?

Inputs:
- attribution_model_count
- dda_adoption_rate
- lookback_window_consistency
- conversion_action_count
- ga4_ads_revenue_discrepancy (Phase 2)
"""

from engine.scoring.base_score import BaseDomainScore, ScoreResult


class MeasurementIntegrityScore(BaseDomainScore):
    """Computes the Measurement Integrity domain score."""

    domain_name = "measurement_integrity"
    weight = 0.25

    def compute(self, data: dict) -> ScoreResult:
        """Compute Measurement Integrity Score.

        Sub-scores:
        1. Attribution Model Consistency (30%)
        2. DDA Adoption (20%)
        3. Lookback Window Consistency (15%)
        4. Conversion Action Hygiene (15%)
        5. Cross-Platform Discrepancy (20%) — Phase 2
        """
        findings = []

        # 1. Attribution Model Consistency (30%)
        attr_count = data.get("attribution_model_count", 1)
        if attr_count == 1:
            attr_score = 100
        elif attr_count == 2:
            attr_score = 60
        else:
            attr_score = max(0, 100 - (attr_count * 20))
        if attr_count > 1:
            findings.append(f"{attr_count} attribution models across conversion actions")

        # 2. DDA Adoption (20%)
        dda_rate = data.get("dda_adoption_rate", 0.0)
        dda_score = dda_rate * 100
        findings.append(f"DDA adoption: {dda_rate:.0%}")

        # 3. Lookback Window Consistency (15%)
        lookback_consistent = data.get("lookback_window_consistency", True)
        lookback_score = 100 if lookback_consistent else 50
        if not lookback_consistent:
            findings.append("Inconsistent lookback windows across conversion actions")

        # 4. Conversion Action Hygiene (15%)
        action_count = data.get("conversion_action_count", 1)
        if 1 <= action_count <= 5:
            hygiene_score = 100
        elif action_count <= 10:
            hygiene_score = 70
        else:
            hygiene_score = max(0, 100 - (action_count - 10) * 5)
        if action_count > 10:
            findings.append(f"{action_count} active conversion actions (high noise)")

        # 5. Cross-Platform Discrepancy (20%) — Phase 2
        disc = data.get("ga4_ads_revenue_discrepancy")
        if disc is not None:
            if disc <= 5:
                cross_score = 100
            elif disc <= 15:
                cross_score = 100 - ((disc - 5) / 10) * 40
            elif disc <= 30:
                cross_score = 60 - ((disc - 15) / 15) * 40
            else:
                cross_score = max(0, 20 - ((disc - 30) / 20) * 20)
            findings.append(f"GA4 vs Ads revenue discrepancy: {disc:.0f}%")
            completeness = 1.0
        else:
            cross_score = 50  # No GA4 data = neutral
            completeness = 0.70

        score = (
            attr_score * 0.30
            + dda_score * 0.20
            + lookback_score * 0.15
            + hygiene_score * 0.15
            + cross_score * 0.20
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
                "attribution_model_consistency": round(attr_score, 1),
                "dda_adoption": round(dda_score, 1),
                "lookback_window_consistency": round(lookback_score, 1),
                "conversion_action_hygiene": round(hygiene_score, 1),
                "cross_platform_discrepancy": round(cross_score, 1),
            },
        )
