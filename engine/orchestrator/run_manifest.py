"""Run manifest — Complete audit run log with metadata.

Tracks: start time, end time, account, date range, extraction stats,
scores, output paths, errors.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


def create_run_manifest(
    run_id: str,
    account_id: str,
    account_name: str,
    date_range: dict[str, str],
    started_at: datetime,
    extraction_stats: dict,
    scoring_summary: dict,
    output_paths: dict,
    errors: list[str] | None = None,
) -> dict:
    """Create a complete run manifest.

    Args:
        run_id: Unique run identifier.
        account_id: Google Ads account ID.
        account_name: Client name.
        date_range: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}.
        started_at: When the audit started.
        extraction_stats: Per-table extraction statistics.
        scoring_summary: Composite score, risk band, etc.
        output_paths: Paths to all generated outputs.
        errors: List of error messages (if any).

    Returns:
        Run manifest dictionary.
    """
    completed_at = datetime.now(timezone.utc)

    manifest = {
        "run_id": run_id,
        "account_id": account_id,
        "account_name": account_name,
        "date_range": date_range,
        "engine_version": "1.0.0",
        "api_versions": {
            "google_ads": "v23",
            "ga4_data_api": "v1beta",
            "bigquery": "v2",
        },
        "execution": {
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_seconds": (completed_at - started_at).total_seconds(),
            "status": "FAILED" if errors else "SUCCESS",
        },
        "extraction_stats": extraction_stats,
        "scoring": scoring_summary,
        "outputs": output_paths,
        "errors": errors or [],
    }

    return manifest


def save_run_manifest(manifest: dict, output_path: str) -> str:
    """Save run manifest to JSON file.

    Args:
        manifest: Run manifest dictionary.
        output_path: Path to save the JSON file.

    Returns:
        Path to the saved file.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)

    logger.info("run_manifest_saved", path=str(path))
    return str(path)
