"""Capital Implication Logic — REDUCE / REWEIGHT / TEST / HOLD.

Decision tree based on composite score, red flags, and domain scores.
"""

from engine.scoring.base_score import ScoreResult
from engine.scoring.red_flags import RedFlag


def compute_capital_implication(
    composite_score: int,
    red_flags: list[RedFlag],
    domain_scores: dict[str, ScoreResult],
) -> str:
    """Determine capital implication from audit results.

    Only 4 allowed outputs:
    - REDUCE: Decrease spend until structural issues resolved
    - REWEIGHT: Total spend OK but allocation is wrong
    - TEST: Mostly sound, validate hypotheses before scaling
    - HOLD: Healthy structure, maintain trajectory

    Args:
        composite_score: The composite integrity score (0-100).
        red_flags: List of triggered red flags.
        domain_scores: Dict mapping domain name to ScoreResult.

    Returns:
        One of: "REDUCE", "REWEIGHT", "TEST", "HOLD".
    """
    critical_flags = [f for f in red_flags if f.severity == "critical"]

    # REDUCE: Critical structural failure OR critical measurement issues
    if composite_score <= 40:
        return "REDUCE"
    if len(critical_flags) >= 3:
        return "REDUCE"
    if (
        "measurement_integrity" in domain_scores
        and domain_scores["measurement_integrity"].value <= 30
    ):
        return "REDUCE"

    # REWEIGHT: Moderate-to-high exposure with clear reallocation opportunity
    if 41 <= composite_score <= 60:
        return "REWEIGHT"
    if (
        "capital_allocation_discipline" in domain_scores
        and domain_scores["capital_allocation_discipline"].value <= 40
    ):
        return "REWEIGHT"
    if (
        "demand_capture_integrity" in domain_scores
        and "capital_allocation_discipline" in domain_scores
        and domain_scores["demand_capture_integrity"].value <= 40
        and domain_scores["capital_allocation_discipline"].value >= 60
    ):
        return "REWEIGHT"

    # TEST: Moderate exposure, no critical failures
    if 61 <= composite_score <= 75:
        return "TEST"
    if len(critical_flags) >= 1:
        return "TEST"

    # HOLD: Sound or excellent
    return "HOLD"
