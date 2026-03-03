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
    from engine.connectors.google_ads.keyword_quality_score import KeywordQualityScoreExtractor
    from engine.connectors.google_ads.negative_keywords import NegativeKeywordsExtractor
    from engine.connectors.google_ads.shopping_structure import ShoppingStructureExtractor
    from engine.connectors.google_ads.pmax_audience_signals import PMaxAudienceSignalsExtractor
    from engine.connectors.google_ads.customer_lists import CustomerListsExtractor
    from engine.connectors.google_ads.nca_settings import NCASettingsExtractor

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
        ("keyword_quality_score", KeywordQualityScoreExtractor),
        ("negative_keywords", NegativeKeywordsExtractor),
        ("shopping_structure", ShoppingStructureExtractor),
        ("pmax_audience_signals", PMaxAudienceSignalsExtractor),
        ("customer_lists", CustomerListsExtractor),
        ("nca_settings", NCASettingsExtractor),
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


def extract_ga4_stage(
    credentials: dict,
    property_id: str,
    start_date: str,
    end_date: str,
    bq_config: dict | None = None,
) -> dict:
    """Extract GA4 data from BigQuery (preferred) or GA4 Data API v1 (fallback).

    If bq_config is provided with a bq_project_id, tries BigQuery first for
    unsampled data. Falls back to GA4 Data API if BQ fails.

    Args:
        credentials: OAuth2 credentials dict (client_id, client_secret, refresh_token).
        property_id: GA4 property ID (e.g. "345678901").
        start_date: YYYY-MM-DD.
        end_date: YYYY-MM-DD.
        bq_config: Optional dict with bq_project_id and bq_dataset_id.

    Returns:
        Dict with keys: attribution, channel_revenue, traffic_acquisition, paid_vs_organic.
        Empty dict if property_id is None.
    """
    if not property_id:
        return {}

    # ── Try BigQuery first (unsampled data) ───────────────────────
    if bq_config and bq_config.get("bq_project_id"):
        try:
            from engine.connectors.bigquery.ga4_raw_query import BigQueryGA4Connector

            connector = BigQueryGA4Connector(
                credentials=credentials,
                bq_project_id=bq_config["bq_project_id"],
                property_id=property_id,
            )
            bq_data = connector.extract(start_date, end_date)
            logger.info("bq_extract_success", property_id=property_id, source="bigquery")
            return bq_data
        except Exception as e:
            logger.warning(
                "bq_extract_failed_fallback_ga4",
                property_id=property_id,
                error=str(e),
            )
            # Fall through to GA4 Data API

    # ── Fallback: GA4 Data API ────────────────────────────────────
    from engine.connectors.ga4.attribution import GA4AttributionExtractor
    from engine.connectors.ga4.channel_revenue import GA4ChannelRevenueExtractor
    from engine.connectors.ga4.traffic_acquisition import GA4TrafficAcquisitionExtractor
    from engine.connectors.ga4.paid_vs_organic import GA4PaidVsOrganicExtractor
    from engine.connectors.ga4.events_list import GA4EventsListExtractor

    logger.info("extract_ga4_stage_start", property_id=property_id, source="ga4_api")

    ga4_extractors = [
        ("attribution", GA4AttributionExtractor),
        ("channel_revenue", GA4ChannelRevenueExtractor),
        ("traffic_acquisition", GA4TrafficAcquisitionExtractor),
        ("paid_vs_organic", GA4PaidVsOrganicExtractor),
        ("events_list", GA4EventsListExtractor),
    ]

    ga4_data = {"source": "ga4_api"}
    for name, ExtractorClass in ga4_extractors:
        t0 = time.time()
        try:
            extractor = ExtractorClass(
                credentials=credentials,
                property_id=property_id,
            )
            data = extractor.extract(start_date, end_date)
            ga4_data[name] = data
            duration = time.time() - t0
            logger.info("ga4_extractor_complete", extractor=name, rows=len(data), duration=round(duration, 2))
        except Exception as e:
            ga4_data[name] = []
            duration = time.time() - t0
            logger.warning("ga4_extractor_failed", extractor=name, error=str(e), duration=round(duration, 2))

    logger.info("extract_ga4_stage_complete", extractors_ok=sum(1 for k, v in ga4_data.items() if k != "source" and v))
    return ga4_data


def normalize_stage(raw_data: dict, ga4_raw_data: dict | None = None) -> dict:
    """Stage 2: Normalize raw API data into scoring metrics.

    Takes raw extractor output and produces the same metric dictionaries
    that the fixture data provides.
    """
    from engine.normalization.campaigns_daily import build_campaigns_daily, compute_campaigns_metrics
    from engine.normalization.conversions_snapshot import build_conversions_snapshot, compute_measurement_metrics
    from engine.normalization.pmax_breakdown import build_pmax_breakdown, compute_automation_metrics
    from engine.normalization.auction_density import build_auction_density, compute_auction_metrics
    from engine.normalization.creative_velocity import build_creative_velocity, compute_creative_metrics
    from engine.normalization.keyword_quality import compute_quality_score_metrics
    from engine.normalization.negative_keywords import compute_negative_keyword_metrics
    from engine.normalization.shopping_structure import compute_shopping_structure_metrics
    from engine.normalization.pmax_audiences import compute_pmax_audience_metrics
    from engine.normalization.customer_lists import compute_customer_list_metrics
    from engine.normalization.nca_settings import compute_nca_metrics

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

    # Phase 3A: Quality Score brand vs non-brand
    qs_metrics = compute_quality_score_metrics(
        qs_data=raw_data.get("keyword_quality_score", []),
        brand_name=raw_data.get("_brand_name", ""),
    )

    # Phase 3B: Negative keywords overlap and Shopping coverage
    nk_metrics = compute_negative_keyword_metrics(
        nk_data=raw_data.get("negative_keywords", []),
    )

    # Phase 3C: Shopping structure (product overlap + RLSA)
    shopping_metrics = compute_shopping_structure_metrics(
        ss_data=raw_data.get("shopping_structure", []),
    )

    # Phase 3D: PMax audience signals (prospecting vs retargeting)
    pmax_aud_metrics = compute_pmax_audience_metrics(
        pmax_aud_data=raw_data.get("pmax_audience_signals", []),
    )

    # Phase 3E: Customer lists health
    cl_metrics = compute_customer_list_metrics(
        cl_data=raw_data.get("customer_lists", []),
        change_data=raw_data.get("change_history", []),
    )

    # Phase 3F: NCA bid settings
    nca_metrics = compute_nca_metrics(
        nca_data=raw_data.get("nca_settings", []),
    )

    demand_capture = {
        "avg_search_impression_share": campaigns_metrics.get("avg_search_impression_share", 0),
        "avg_budget_lost_impression_share": campaigns_metrics.get("avg_budget_lost_impression_share", 0),
        "avg_rank_lost_impression_share": campaigns_metrics.get("avg_rank_lost_impression_share", 0),
        "avg_outranking_share": auction_metrics.get("avg_outranking_share", 0),
        # Phase 2: brand/nonbrand metrics
        "brand_spend_pct": campaigns_metrics.get("brand_spend_pct", 0),
        "nonbrand_search_impression_share": campaigns_metrics.get("nonbrand_search_impression_share", 0),
        "nonbrand_abs_top_impression_share": campaigns_metrics.get("nonbrand_abs_top_impression_share", 0),
        # Phase 3A: quality score metrics
        "avg_quality_score": qs_metrics.get("avg_quality_score"),
        "nonbrand_avg_quality_score": qs_metrics.get("nonbrand_avg_quality_score"),
        # Phase 3B: negative keyword metrics
        "negative_keyword_overlap_count": nk_metrics.get("negative_keyword_overlap_count", 0),
        "shopping_negative_keyword_coverage": nk_metrics.get("shopping_negative_keyword_coverage", 1.0),
        # Phase 3C: shopping structure metrics
        "shopping_campaign_product_overlap_pct": shopping_metrics.get("shopping_campaign_product_overlap_pct", 0),
        "shopping_rlsa_campaign_count": shopping_metrics.get("shopping_rlsa_campaign_count", 0),
    }

    automation_exposure = {
        "pct_spend_automated": automation_metrics.get("pct_spend_automated", 0),
        "pct_spend_pmax": automation_metrics.get("pct_spend_pmax", 0),
        "pmax_channel_concentration": automation_metrics.get("pmax_channel_concentration", 0),
        "bidding_strategy_diversity": automation_metrics.get("bidding_strategy_diversity", 1),
        # Phase 2: bidding + PMax metrics
        "campaigns_with_maximize_clicks": campaigns_metrics.get("campaigns_with_maximize_clicks", 0),
        "pmax_brand_exclusion_count": campaigns_metrics.get("pmax_brand_exclusion_count", -1),
        # Phase 3D: PMax audience split
        "pmax_prospecting_campaign_count": pmax_aud_metrics.get("pmax_prospecting_campaign_count", 0),
        "pmax_retargeting_campaign_count": pmax_aud_metrics.get("pmax_retargeting_campaign_count", 0),
        # Phase 3E: customer lists health
        "days_since_customer_list_refresh": cl_metrics.get("days_since_customer_list_refresh", 0),
        "customer_list_match_rate": cl_metrics.get("customer_list_match_rate", 1.0),
        # Phase 3F: NCA bid settings
        "nca_bid_adjustment": nca_metrics.get("nca_bid_adjustment", 0),
        "nca_bid_validation": nca_metrics.get("nca_bid_validation", True),
    }

    measurement_integrity = {
        "attribution_model_count": measurement_metrics.get("attribution_model_count", 1),
        "dda_adoption_rate": measurement_metrics.get("dda_adoption_rate", 0),
        "lookback_window_consistency": measurement_metrics.get("lookback_window_consistency", True),
        "conversion_action_count": measurement_metrics.get("conversion_action_count", 0),
        "ga4_ads_revenue_discrepancy": measurement_metrics.get("ga4_ads_revenue_discrepancy", None),
        # Phase 2: conversion source + enhanced conversions
        "conversion_source_count": measurement_metrics.get("conversion_source_count", 0),
        "conversion_source_variance": measurement_metrics.get("conversion_source_variance", 0),
        "enhanced_conversions_enabled": measurement_metrics.get("enhanced_conversions_enabled", None),
    }

    capital_allocation = {
        "avg_budget_utilization": campaigns_metrics.get("avg_budget_utilization", 0),
        "spend_concentration_hhi": campaigns_metrics.get("spend_concentration_hhi", 0),
        "roas_variance_coefficient": campaigns_metrics.get("roas_variance_coefficient", 0),
        "zero_conversion_spend_pct": campaigns_metrics.get("zero_conversion_spend_pct", 0),
        "campaign_count": campaigns_metrics.get("campaign_count", 0),
        # Phase 3H: profit-based bidding detection
        "profit_based_bidding": raw_data.get("_audit_config", {}).get("profit_based_bidding", False),
        "revenue_based_bidding": campaigns_metrics.get("has_troas_campaigns", False),
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

    # ── GA4 normalization (optional) ──────────────────────────────
    if ga4_raw_data:
        try:
            from engine.normalization.ga4_channel_performance import build_ga4_channel_performance
            from engine.normalization.attribution_config import build_attribution_config

            ga4_channel_df = build_ga4_channel_performance(
                ga4_channel_data=ga4_raw_data.get("channel_revenue", []),
            )

            attribution_df = build_attribution_config(
                google_ads_conversions=raw_data.get("conversion_actions", []),
                ga4_attribution=ga4_raw_data.get("attribution", []),
            )

            # Use paid_vs_organic data for apples-to-apples comparisons
            paid_vs_organic = ga4_raw_data.get("paid_vs_organic", [])
            ga4_paid_revenue = sum(
                float(r.get("totalRevenue", 0) or 0)
                for r in paid_vs_organic if r.get("category") == "paid"
            )
            ga4_paid_conversions = sum(
                float(r.get("conversions", 0) or 0)
                for r in paid_vs_organic if r.get("category") == "paid"
            )
            ga4_total_revenue = sum(
                float(r.get("totalRevenue", 0) or 0) for r in paid_vs_organic
            )

            # Google Ads totals from campaigns DataFrame
            gads_revenue = float(campaigns_df["conversions_value"].sum()) if not campaigns_df.empty and "conversions_value" in campaigns_df.columns else 0
            gads_conversions = float(campaigns_df["conversions"].sum()) if not campaigns_df.empty and "conversions" in campaigns_df.columns else 0

            # Revenue discrepancy: GA4 paid revenue vs Google Ads conversions_value (as %)
            if ga4_paid_revenue > 0 and gads_revenue > 0:
                rev_disc = abs(ga4_paid_revenue - gads_revenue) / max(ga4_paid_revenue, gads_revenue) * 100
                measurement_integrity["ga4_ads_revenue_discrepancy"] = round(rev_disc, 2)

            # Conversion discrepancy: GA4 paid conversions vs Google Ads conversions (as %)
            if ga4_paid_conversions > 0 and gads_conversions > 0:
                conv_disc = abs(ga4_paid_conversions - gads_conversions) / max(ga4_paid_conversions, gads_conversions) * 100
                measurement_integrity["ga4_ads_conversion_discrepancy"] = round(conv_disc, 2)

            # Capital allocation: paid_revenue_share (ratio 0-1)
            if ga4_total_revenue > 0:
                capital_allocation["paid_revenue_share"] = round(ga4_paid_revenue / ga4_total_revenue, 4)

            # Phase 3G: GA4 mid-funnel events
            from engine.normalization.ga4_events import compute_ga4_events_metrics
            ga4_events_metrics = compute_ga4_events_metrics(
                events_data=ga4_raw_data.get("events_list", []),
            )
            if ga4_events_metrics.get("tracked_funnel_events") is not None:
                measurement_integrity["tracked_funnel_events"] = ga4_events_metrics["tracked_funnel_events"]

            logger.info("ga4_normalization_complete")
        except Exception as e:
            logger.warning("ga4_normalization_failed", error=str(e))

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
    raw_data: dict | None = None,
    ga4_raw_data: dict | None = None,
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

    # Inject raw extractor data for HTML/PDF template rendering
    if raw_data:
        scorecard["_raw_data"] = {
            k: v for k, v in raw_data.items()
            if k not in ("extraction_stats", "_brand_name")
        }
    if ga4_raw_data:
        scorecard["_ga4_raw_data"] = ga4_raw_data

    scorecard_path = save_scorecard(scorecard, os.path.join(run_dir, "scorecard.json"))

    # ── Generate confidence report ────────────────────────────────
    try:
        from engine.reporting.confidence_report import generate_confidence_report

        confidence_data = generate_confidence_report(
            scorecard=scorecard,
            extraction_stats=scoring_results.get("extraction_stats", []),
        )
        confidence_path = os.path.join(run_dir, "confidence_report.json")
        with open(confidence_path, "w") as f:
            json.dump(confidence_data, f, indent=2, default=str)
        logger.info("confidence_report_saved", path=confidence_path)

        # Store in scorecard for frontend access
        scorecard["_confidence"] = confidence_data
    except Exception as e:
        logger.warning("confidence_report_failed", error=str(e))

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
