"""RunAudit() — Main entry point for a complete audit run.

Single entry point: RunAudit(account_id, date_range)
-> triggers extraction -> normalization -> scoring -> report -> evidence pack -> log.
"""

import os
import uuid
from datetime import datetime, timezone

import structlog

from engine.orchestrator.pipeline import (
    extract_stage_fixture,
    extract_stage_real,
    extract_ga4_stage,
    normalize_stage,
    score_stage,
    report_stage,
)
from engine.orchestrator.run_manifest import create_run_manifest, save_run_manifest
from engine.fixtures.demo_data import get_demo_account, DEMO_ACCOUNTS

logger = structlog.get_logger(__name__)


def run_audit(
    account_id: str,
    start_date: str,
    end_date: str,
    output_dir: str = "./output",
    demo_key: str | None = None,
    credentials: dict | None = None,
    login_customer_id: str | None = None,
    ga4_property_id: str | None = None,
    bq_config: dict | None = None,
) -> dict:
    """Execute a complete media structural integrity audit.

    Pipeline:
    1. Extract raw data (real API or fixtures for demo)
    2. Normalize raw data into scoring metrics (real API path)
    3. Compute 5 domain scores + composite
    4. Detect red flags
    5. Generate PDF report
    6. Package evidence bundle (ZIP)
    7. Log run manifest

    Args:
        account_id: Google Ads account ID (e.g., "123-456-7890").
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).
        output_dir: Base output directory.
        demo_key: If provided, use this demo fixture instead of real APIs.
        credentials: Google Ads API credentials dict for real extraction.
        login_customer_id: MCC manager account ID (for real extraction).

    Returns:
        Run manifest dictionary with all metadata and output paths.
    """
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    errors = []
    is_live = credentials is not None and demo_key is None

    logger.info(
        "audit_started",
        run_id=run_id,
        account_id=account_id,
        mode="live" if is_live else "demo",
        date_range=f"{start_date}:{end_date}",
    )

    account_name = account_id
    date_range = {"start": start_date, "end": end_date}
    domain_data = None
    ga4_raw_data = {}

    if is_live:
        try:
            run_dir = os.path.join(output_dir, run_id)
            os.makedirs(run_dir, exist_ok=True)

            raw_data = extract_stage_real(
                credentials=credentials,
                customer_id=account_id,
                start_date=start_date,
                end_date=end_date,
                output_dir=run_dir,
                login_customer_id=login_customer_id,
            )

            # GA4 extraction (optional — only if property linked)
            ga4_raw_data = {}
            if ga4_property_id:
                try:
                    ga4_raw_data = extract_ga4_stage(
                        credentials=credentials,
                        property_id=ga4_property_id,
                        start_date=start_date,
                        end_date=end_date,
                        bq_config=bq_config,
                    )
                except Exception as ga4_err:
                    logger.warning("ga4_extraction_failed", error=str(ga4_err))

            # Resolve account name before normalization (needed for brand classifier)
            from engine.auth.mcc_manager import MCCManager
            try:
                mcc_id = login_customer_id or account_id
                mcc = MCCManager(credentials, mcc_id)
                info = mcc.get_account_info(account_id)
                if info:
                    account_name = info.get("name", account_id)
            except Exception:
                pass

            # Pass brand name to normalization for brand/nonbrand classification
            raw_data["_brand_name"] = account_name

            domain_data = normalize_stage(raw_data, ga4_raw_data=ga4_raw_data or None)

        except Exception as e:
            errors.append(f"Extraction/normalization failed: {e}")
            logger.error("extraction_failed", error=str(e))
    else:
        if demo_key:
            fixture = get_demo_account(demo_key)
        else:
            fixture = None
            for key, acct in DEMO_ACCOUNTS.items():
                if acct["account_id"] == account_id:
                    fixture = acct
                    break
            if fixture is None:
                fixture = get_demo_account("demo-moderate")

        account_name = fixture["account_name"]
        date_range = fixture.get("date_range", {"start": start_date, "end": end_date})

        try:
            domain_data = extract_stage_fixture(fixture)
        except Exception as e:
            errors.append(f"Extraction failed: {e}")
            logger.error("extraction_failed", error=str(e))

    scoring_results = None
    report_results = None

    if domain_data:
        try:
            scoring_results = score_stage(domain_data)
        except Exception as e:
            errors.append(f"Scoring failed: {e}")
            logger.error("scoring_failed", error=str(e))

    if scoring_results:
        try:
            report_results = report_stage(
                run_id=run_id,
                account_id=account_id,
                account_name=account_name,
                date_range=date_range,
                scoring_results=scoring_results,
                output_dir=output_dir,
            )
        except Exception as e:
            errors.append(f"Report generation failed: {e}")
            logger.error("report_failed", error=str(e))

    extraction_stats = {}
    if domain_data:
        extraction_stats = {
            s.get("table", "unknown"): s.get("status", "unknown")
            for s in domain_data.get("extraction_stats", [])
            if isinstance(s, dict)
        }
    if ga4_raw_data:
        extraction_stats["ga4_source"] = ga4_raw_data.get("source", "ga4_api")

    scoring_summary = {}
    if scoring_results:
        band = scoring_results["risk_band"]
        scoring_summary = {
            "composite_score": scoring_results["composite_score"],
            "risk_band": band.name,
            "risk_band_label": band.label,
            "confidence": scoring_results["confidence"],
            "capital_implication": scoring_results["capital_implication"],
            "red_flags_count": len(scoring_results["red_flags"]),
        }

    output_paths = {}
    if report_results:
        output_paths = report_results.get("output_paths", {})

    manifest = create_run_manifest(
        run_id=run_id,
        account_id=account_id,
        account_name=account_name,
        date_range=date_range,
        started_at=started_at,
        extraction_stats=extraction_stats,
        scoring_summary=scoring_summary,
        output_paths=output_paths,
        errors=errors if errors else None,
    )

    if output_paths.get("run_directory"):
        manifest_path = os.path.join(output_paths["run_directory"], "run_manifest.json")
        save_run_manifest(manifest, manifest_path)

    logger.info(
        "audit_completed",
        run_id=run_id,
        status=manifest["execution"]["status"],
        duration=manifest["execution"]["duration_seconds"],
    )

    manifest["_scorecard"] = report_results.get("scorecard") if report_results else None
    manifest["_scoring_results"] = scoring_results

    # Save raw extractor data for detailed Excel report sheets
    if is_live and raw_data:
        manifest["_raw_data"] = {
            k: v for k, v in raw_data.items()
            if k != "extraction_stats"
        }

    # Save GA4 raw data if available
    if is_live and ga4_raw_data:
        manifest["_ga4_raw_data"] = ga4_raw_data

    return manifest
