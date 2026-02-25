"""Composite Integrity Score — Weighted average of 5 domain scores."""

from engine.scoring.base_score import ScoreResult

DOMAIN_WEIGHTS = {
    "demand_capture_integrity": 0.25,
    "automation_exposure": 0.20,
    "measurement_integrity": 0.25,
    "capital_allocation_discipline": 0.20,
    "creative_velocity": 0.10,
}


def compute_composite_score(domain_scores: dict[str, ScoreResult]) -> int:
    """Compute the composite integrity score from domain scores.

    Args:
        domain_scores: Dict mapping domain name to ScoreResult.

    Returns:
        Composite score (0-100).
    """
    composite = sum(
        domain_scores[domain].value * weight
        for domain, weight in DOMAIN_WEIGHTS.items()
        if domain in domain_scores
    )
    return round(composite)
