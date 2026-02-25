"""Pipeline stages — Extract → Normalize → Score → Report.

Each stage is independently testable and logged.
"""

import json
import os
import time
from pathlib import Path

import structlog

from engine.scoring.demand_capture import DemandCaptureIntegrityScore
from engine.scoring.automation_exposure import AutomationExposureScore
from engine.scoring.measurement_integrity import MeasurementIntegrityScore
from engine.scoring.capital_allocation import CapitalAllocationDisciplineScore
from engine.scoring.creative_velocity import CreativeVelocityScore
from engine.scoring.composite import compute_composite_score
from engine.scoring.risk_band import classify_risk_band
from engine.scoring.capital_implication import compute_capital_implication
from engine.scoring.confidence import compute_confidence
from engine.scoring.red_flags import evaluate_rules
from engine.reporting.scorecard_generator import generate_scorecard, save_scorecard
from engine.reporting.html_renderer import render_report_html, save_html
from engine.reporting.pdf_generator import html_to_pdf
from engine.reporting.evidence_pack import create_evidence_pack

logger = structlog.get_logger(__name__)


def extract_stage_fixture(fixture_data: dict) -> dict:
    """Stage 1: Use fixture data instead of real API extraction.

    Returns:
        Dictionary of domain metric data.
    """
    logger.info("extract_stage", mode="fixture")
    return {
        "demand_capture": fixture_data["demand_capture"],
        "automation_exposure": fixture_data["automation_exposure"],
        "measurement_integrity": fixture_data["measurement_integrity"],
        "capital_allocation": fixture_data["capital_allocation"],
        "creative_velocity": fixture_data["creative_velocity"],
        "extraction_stats": fixture_data["extraction_stats"],
    }


def extract_stage_real(
    credentials: dict,
    customer_id: str,
    start_date: str,
    end_date: str,
    output_dir: str,
    login_customer_id: str | None = None,
) -> dict:
    """Stage 1: Extract real data from Google Ads API.

    Runs all 9 extractors, saves raw JSON, returns raw data dict.
    """
    from engine.connectors.google_ads.campaign_performance import CampaignPerformanceExtractor
    from engine.connectors.google_ads.budget_allocation import BudgetAllocationExtractor
    from engine.connectors.google_ads.impression_share import ImpressionShareExtractor
    from engine.connectors.google_ads.conversion_actions import ConversionActionsExtractor
    from engine.connectors.google_ads.bidding_strategies import BiddingStrategiesExtractor
    from engine.connectors.google_ads.pmax_breakdown import PMaxBreakdownExtractor
    from engine.connectors.google_ads.asset_performance import AssetPerformanceExtractor
    from engine.connectors.google_ads.auction_insights import AuctionInsightsExtractor
    from engine.connectors.google_ads.change_history import ChangeHistoryExtractor

    logger.info("extract_stage", mode="real", customer_id=customer_id)

    extractor_configs = [
        ("campaign_performance", CampaignPerformanceExtractor),
        ("budget_allocation", BudgetAllocationExtractor),
        ("impression_share", ImpressionShareExtractor),
        ("conversion_actions", ConversionActionsExtractor),
        ("bidding_strategies", BiddingStrategiesExtractor),
        ("pmax_breakdown", PMaxBreakdownExtractor),
        ("asset_performance", AssetPerformanceExtractor),
        ("auction_insights", AuctionInsightsExtractor),
        ("change_history", ChangeHistoryExtractor),
    ]

    raw_data = {}
    extraction_stats = []

    for name, ExtractorClass in extractor_configs:
        t0 = time.time()
        try:
            extractor = ExtractorClass(
                credentials=credentials,
                customer_id=customer_id,
                login_customer_id=login_customer_id,
                output_dir=output_dir,
            )
            data = extractor.extract(start_date, end_date)
            raw_data[name] = data
            duration = time.time() - t0
            extraction_stats.append({
                "table": name,
                "status": "complete" if len(data) > 0 else "empty",
                "rows": len(data),
                "duration_seconds": round(duration, 2),
            })
            logger.info(
                "extractor_complete",
                extractor=name,
                rows=len(data),
                duration=round(duration, 2),
            )
        except Exception as e:
            duration = time.time() - t0
            raw_data[name] = []
            extraction_stats.append({
                "table": name,
                "status": "failed",
                "rows": 0,
                "duration_seconds": round(duration, 2),
                "error": str(e),
            })
            logger.warning(
                "extractor_failed",
                extractor=name,
                error=str(e),
                duration=round(duration, 2),
            )

    raw_data["extraction_stats"] = extraction_stats
    return raw_data


def normalize_stage(raw_data: dict) -> dict:
    """Stage 2: Normalize raw API data into scoring metrics.

    Takes raw extractor output and produces the same metric dictionaries
    that the fixture data provides.
    """
    from engine.normalization.campaigns_daily import build_campaigns_daily, compute_campaigns_metrics
    from engine.normalization.conversions_snapshot import build_conversions_snapshot, compute_measurement_metrics
    from engine.normalization.pmax_breakdown import build_pmax_breakdown, compute_automation_metrics
    from engine.normalization.auction_density import build_auction_density, compute_auction_metrics
    from engine.normalization.creative_velocity import build_creative_velocity, compute_creative_metrics

    logger.info("normalize_stage_start")

    campaigns_df = build_campaigns_daily(
        campaign_data=raw_data.get("campaign_performance", []),
        budget_data=raw_data.get("budget_allocation", []),
        impression_share_data=raw_data.get("impression_share", []),
    )
    campaigns_metrics = compute_campaigns_metrics(campaigns_df)

    conversions_df = build_conversions_snapshot(
        conversion_actions_data=raw_data.get("conversion_actions", []),
    )
    measurement_metrics = compute_measurement_metrics(conversions_df)

    pmax_df = build_pmax_breakdown(
        pmax_data=raw_data.get("pmax_breakdown", []),
    )
    automation_metrics = compute_automation_metrics(pmax_df, campaigns_df)

    auction_df = build_auction_density(
        auction_data=raw_data.get("auction_insights", []),
    )
    auction_metrics = compute_auction_metrics(auction_df)

    creative_df = build_creative_velocity(
        asset_data=raw_data.get("asset_performance", []),
    )
    creative_metrics = compute_creative_metrics(creative_df)

    demand_capture = {
        "avg_search_impression_share": campaigns_metrics.get("avg_search_impression_share", 0),
        "avg_budget_lost_impression_share": campaigns_metrics.get("avg_budget_lost_impression_share", 0),
        "avg_rank_lost_impression_share": campaigns_metrics.get("avg_rank_lost_impression_share", 0),
        "avg_outranking_share": auction_metrics.get("avg_outranking_share", 0),
    }

    automation_exposure = {
        "pct_spend_automated": automation_metrics.get("pct_spend_automated", 0),
        "pct_spend_pmax": automation_metrics.get("pct_spend_pmax", 0),
        "pmax_channel_concentration": automation_metrics.get("pmax_channel_concentration", 0),
        "bidding_strategy_diversity": automation_metrics.get("bidding_strategy_diversity", 1),
    }

    measurement_integrity = {
        "attribution_model_count": measurement_metrics.get("attribution_model_count", 1),
        "dda_adoption_rate": measurement_metrics.get("dda_adoption_rate", 0),
        "lookback_window_consistency": measurement_metrics.get("lookback_window_consistency", True),
        "conversion_action_count": measurement_metrics.get("conversion_action_count", 0),
        "ga4_ads_revenue_discrepancy": measurement_metrics.get("ga4_ads_revenue_discrepancy", None),
    }

    capital_allocation = {
        "avg_budget_utilization": campaigns_metrics.get("avg_budget_utilization", 0),
        "spend_concentration_hhi": campaigns_metrics.get("spend_concentration_hhi", 0),
        "roas_variance_coefficient": campaigns_metrics.get("roas_variance_coefficient", 0),
        "zero_conversion_spend_pct": campaigns_metrics.get("zero_conversion_spend_pct", 0),
        "campaign_count": campaigns_metrics.get("campaign_count", 0),
    }

    creative_velocity = {
        "total_asset_count": creative_metrics.get("total_asset_count", 0),
        "asset_groups_count": creative_metrics.get("asset_groups_count", 0),
        "pct_best_performing": creative_metrics.get("pct_best_performing", 0),
        "pct_good_performing": creative_metrics.get("pct_good_performing", 0),
        "pct_low_performing": creative_metrics.get("pct_low_performing", 0),
        "pct_disapproved": creative_metrics.get("pct_disapproved", 0),
        "format_diversity": creative_metrics.get("format_diversity", 0),
        "data_completeness": creative_metrics.get("data_completeness", 0),
    }

    extraction_stats = raw_data.get("extraction_stats", [])

    logger.info("normalize_stage_complete")

    return {
        "demand_capture": demand_capture,
        "automation_exposure": automation_exposure,
        "measurement_integrity": measurement_integrity,
        "capital_allocation": capital_allocation,
        "creative_velocity": creative_velocity,
        "extraction_stats": extraction_stats,
    }


def score_stage(domain_data: dict) -> dict:
    """Stage 3: Compute all scores from domain data.

    Returns:
        Dictionary with domain_scores, composite_score, red_flags, etc.
    """
    logger.info("score_stage_start")

    scorers = [
        (DemandCaptureIntegrityScore(), domain_data["demand_capture"]),
        (AutomationExposureScore(), domain_data["automation_exposure"]),
        (MeasurementIntegrityScore(), domain_data["measurement_integrity"]),
        (CapitalAllocationDisciplineScore(), domain_data["capital_allocation"]),
        (CreativeVelocityScore(), domain_data["creative_velocity"]),
    ]

    domain_scores = {}
    for scorer, data in scorers:
        result = scorer.compute(data)
        domain_scores[result.domain] = result
        logger.info(
            "domain_score_computed",
            domain=result.domain,
            value=result.value,
        )

    composite = compute_composite_score(domain_scores)
    band = classify_risk_band(composite)

    flat_metrics = {}
    for data in domain_data.values():
        if isinstance(data, dict):
            flat_metrics.update(data)
    cv_data = domain_data.get("creative_velocity", {})
    groups = cv_data.get("asset_groups_count", 1)
    assets = cv_data.get("total_asset_count", 0)
    flat_metrics["avg_assets_per_group"] = assets / max(groups, 1)
    ae_data = domain_data.get("automation_exposure", {})
    flat_metrics["pmax_channel_hhi"] = ae_data.get("pmax_channel_concentration", 0)

    red_flags = evaluate_rules(flat_metrics)
    confidence = compute_confidence(domain_data.get("extraction_stats", []))
    implication = compute_capital_implication(composite, red_flags, domain_scores)

    logger.info(
        "score_stage_complete",
        composite=composite,
        risk_band=band.label,
        red_flags=len(red_flags),
        capital_implication=implication,
    )

    return {
        "domain_scores": domain_scores,
        "composite_score": composite,
        "risk_band": band,
        "red_flags": red_flags,
        "confidence": confidence,
        "capital_implication": implication,
        "extraction_stats": domain_data.get("extraction_stats", []),
    }


def report_stage(
    run_id: str,
    account_id: str,
    account_name: str,
    date_range: dict,
    scoring_results: dict,
    output_dir: str,
) -> dict:
    """Stage 4: Generate report, evidence pack, and run manifest.

    Returns:
        Dictionary of output file paths.
    """
    logger.info("report_stage_start", run_id=run_id)

    run_dir = os.path.join(output_dir, run_id)
    os.makedirs(run_dir, exist_ok=True)

    band = scoring_results["risk_band"]
    confidence_report = {
        "level": scoring_results["confidence"],
        "tables": [
            {"table": s.get("table", "unknown"), "status": s.get("status", "unknown")}
            for s in scoring_results.get("extraction_stats", [])
        ],
    }

    scorecard = generate_scorecard(
        run_id=run_id,
        account_id=account_id,
        account_name=account_name,
        date_range=date_range,
        composite_score=scoring_results["composite_score"],
        risk_band=band.name,
        confidence=scoring_results["confidence"],
        capital_implication=scoring_results["capital_implication"],
        domain_scores=scoring_results["domain_scores"],
        red_flags=scoring_results["red_flags"],
        confidence_report=confidence_report,
    )

    scorecard_path = save_scorecard(scorecard, os.path.join(run_dir, "scorecard.json"))

    html = render_report_html(scorecard)
    html_path = save_html(html, os.path.join(run_dir, "report.html"))

    pdf_path = os.path.join(run_dir, "report.pdf")
    try:
        html_to_pdf(html_path, pdf_path)
    except Exception as e:
        logger.warning("pdf_generation_failed", error=str(e))
        pdf_path = None

    zip_path = os.path.join(run_dir, "evidence_pack.zip")
    try:
        create_evidence_pack(run_dir, zip_path)
    except Exception as e:
        logger.warning("evidence_pack_failed", error=str(e))
        zip_path = None

    output_paths = {
        "scorecard": scorecard_path,
        "html_report": html_path,
        "pdf_report": pdf_path,
        "evidence_pack": zip_path,
        "run_directory": run_dir,
    }

    logger.info("report_stage_complete", outputs=list(output_paths.keys()))

    return {
        "scorecard": scorecard,
        "output_paths": output_paths,
    }
