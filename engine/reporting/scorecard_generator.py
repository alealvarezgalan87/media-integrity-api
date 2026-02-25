"""Generates scorecard.json — the primary output of the scoring engine.

Contains: composite score, domain scores, red flags, confidence report, metadata.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

from engine.scoring.base_score import ScoreResult
from engine.scoring.red_flags import RedFlag

logger = structlog.get_logger(__name__)


def generate_scorecard(
    run_id: str,
    account_id: str,
    account_name: str,
    date_range: dict[str, str],
    composite_score: int,
    risk_band: str,
    confidence: str,
    capital_implication: str,
    domain_scores: dict[str, ScoreResult],
    red_flags: list[RedFlag],
    confidence_report: dict[str, Any],
) -> dict:
    """Generate the scorecard.json output.

    Args:
        run_id: Unique run identifier.
        account_id: Google Ads account ID.
        account_name: Client name.
        date_range: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}.
        composite_score: Composite integrity score (0-100).
        risk_band: Risk band name.
        confidence: "High", "Medium", or "Low".
        capital_implication: "REDUCE", "REWEIGHT", "TEST", or "HOLD".
        domain_scores: Dict of domain ScoreResults.
        red_flags: List of triggered RedFlags.
        confidence_report: Data completeness details.

    Returns:
        Scorecard dictionary ready for JSON serialization.
    """
    scorecard = {
        "run_id": run_id,
        "account_id": account_id,
        "account_name": account_name,
        "date_range": date_range,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine_version": "1.0.0",
        "composite_score": {
            "value": composite_score,
            "risk_band": risk_band,
            "confidence": confidence,
            "capital_implication": capital_implication,
        },
        "domain_scores": {
            name: {
                "value": result.value,
                "weight": result.weight,
                "weighted_contribution": result.weighted_contribution,
                "key_findings": result.key_findings,
                "data_completeness": result.data_completeness,
            }
            for name, result in domain_scores.items()
        },
        "red_flags": [
            {
                "id": flag.id,
                "severity": flag.severity,
                "domain": flag.domain,
                "title": flag.title,
                "description": flag.description,
                "evidence": flag.evidence,
                "recommendation": flag.recommendation,
            }
            for flag in red_flags
        ],
        "confidence_report": confidence_report,
    }

    return scorecard


def save_scorecard(scorecard: dict, output_path: str) -> str:
    """Save scorecard to JSON file.

    Args:
        scorecard: Scorecard dictionary.
        output_path: Path to save the JSON file.

    Returns:
        Path to the saved file.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        json.dump(scorecard, f, indent=2)

    logger.info("scorecard_saved", path=str(path))
    return str(path)
