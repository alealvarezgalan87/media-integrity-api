"""Risk Band classification based on composite score."""

from dataclasses import dataclass


@dataclass
class RiskBand:
    """Risk band classification result."""

    name: str
    label: str
    color: str
    score_range: tuple[int, int]


RISK_BANDS = [
    RiskBand("Critical Structural Failure", "CRITICAL", "#EF4444", (0, 40)),
    RiskBand("High Structural Exposure", "HIGH", "#F97316", (41, 60)),
    RiskBand("Moderate Structural Exposure", "MODERATE", "#F59E0B", (61, 75)),
    RiskBand("Sound — Minor Adjustments Recommended", "SOUND", "#4ADE80", (76, 90)),
    RiskBand("Excellent Structural Integrity", "EXCELLENT", "#22C55E", (91, 100)),
]


def classify_risk_band(composite_score: int) -> RiskBand:
    """Classify a composite score into a risk band.

    Args:
        composite_score: The composite integrity score (0-100).

    Returns:
        RiskBand with name, label, color, and score range.
    """
    for band in RISK_BANDS:
        if band.score_range[0] <= composite_score <= band.score_range[1]:
            return band
    return RISK_BANDS[0]  # Default to critical if out of range
