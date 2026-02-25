"""Creative Velocity Score — Weight: 0.10.

Question: Is the creative portfolio healthy and being actively managed?

Inputs:
- total_asset_count
- pct_best_performing, pct_good_performing
- pct_low_performing
- pct_disapproved
- format_diversity
- asset_groups_count
"""

from engine.scoring.base_score import BaseDomainScore, ScoreResult


class CreativeVelocityScore(BaseDomainScore):
    """Computes the Creative Velocity domain score."""

    domain_name = "creative_velocity"
    weight = 0.10

    def compute(self, data: dict) -> ScoreResult:
        """Compute Creative Velocity Score.

        Sub-scores:
        1. Asset Volume (20%) — 15+ per group recommended
        2. Performance Distribution (30%) — BEST + GOOD ratio
        3. Low Performer Penalty (20%)
        4. Disapproval Penalty (15%)
        5. Format Diversity (15%)
        """
        findings = []

        # 1. Asset Volume (20%)
        total_assets = data.get("total_asset_count", 0)
        groups = data.get("asset_groups_count", 1)
        avg_assets = total_assets / max(groups, 1)
        if avg_assets >= 15:
            volume_score = 100
        elif avg_assets >= 10:
            volume_score = 70
        elif avg_assets >= 5:
            volume_score = 40
        else:
            volume_score = 10
        findings.append(f"{total_assets} assets across {groups} asset groups")

        # 2. Performance Distribution (30%)
        good_pct = data.get("pct_best_performing", 0) + data.get("pct_good_performing", 0)
        if good_pct >= 0.60:
            perf_score = 100
        elif good_pct >= 0.40:
            perf_score = 70
        elif good_pct >= 0.20:
            perf_score = 40
        else:
            perf_score = 10

        # 3. Low Performer Penalty (20%)
        low_pct = data.get("pct_low_performing", 0)
        if low_pct <= 0.10:
            low_score = 100
        elif low_pct <= 0.25:
            low_score = 70
        elif low_pct <= 0.50:
            low_score = 40
        else:
            low_score = 10
        if low_pct > 0.25:
            findings.append(f"{low_pct:.0%} rated LOW performance")

        # 4. Disapproval Penalty (15%)
        dis_pct = data.get("pct_disapproved", 0)
        if dis_pct == 0:
            dis_score = 100
        elif dis_pct <= 0.05:
            dis_score = 70
        elif dis_pct <= 0.15:
            dis_score = 30
        else:
            dis_score = 0
        findings.append(f"{dis_pct:.0%} disapproved")

        # 5. Format Diversity (15%)
        formats = data.get("format_diversity", 1)
        if formats >= 6:
            format_score = 100
        elif formats >= 4:
            format_score = 70
        elif formats >= 2:
            format_score = 40
        else:
            format_score = 10
        findings.append(f"{formats} format types")

        score = (
            volume_score * 0.20
            + perf_score * 0.30
            + low_score * 0.20
            + dis_score * 0.15
            + format_score * 0.15
        )

        value = self.clamp(score)

        return ScoreResult(
            domain=self.domain_name,
            value=value,
            weight=self.weight,
            weighted_contribution=round(value * self.weight, 2),
            key_findings=findings,
            data_completeness=data.get("data_completeness", 0.90),
            sub_scores={
                "asset_volume": round(volume_score, 1),
                "performance_distribution": round(perf_score, 1),
                "low_performer_penalty": round(low_score, 1),
                "disapproval_penalty": round(dis_score, 1),
                "format_diversity": round(format_score, 1),
            },
        )
