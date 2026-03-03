"""Confidence Report Generator.

Produces a JSON document detailing data completeness and reliability
for each component of the audit scoring.
"""

import structlog
from datetime import datetime, timezone

logger = structlog.get_logger(__name__)


def generate_confidence_report(scorecard: dict, extraction_stats: list | dict) -> dict:
    """Generate a confidence report from scorecard and extraction stats.

    Args:
        scorecard: Full scorecard dict with domain_scores, tables, _ga4_raw_data.
        extraction_stats: List or dict from the extraction stage with extractor results.

    Returns:
        Dict ready to serialize as confidence_report.json.
    """
    domain_scores = scorecard.get("domain_scores", {})
    ga4_raw = scorecard.get("_ga4_raw_data", {})

    data_sources = _assess_data_sources(extraction_stats, ga4_raw)
    domain_confidence = _assess_domain_confidence(domain_scores, scorecard)
    red_flags_info = _assess_red_flags(scorecard)

    completeness_values = [
        d.get("data_completeness", 0)
        for d in domain_confidence.values()
    ]
    avg_completeness = (
        sum(completeness_values) / len(completeness_values)
        if completeness_values else 0
    )

    if avg_completeness >= 0.8:
        overall = "High"
    elif avg_completeness >= 0.5:
        overall = "Medium"
    else:
        overall = "Low"

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_confidence": overall,
        "overall_data_completeness": round(avg_completeness, 3),
        "data_sources": data_sources,
        "domain_confidence": domain_confidence,
        "red_flags": red_flags_info,
        "scoring_metadata": {
            "composite_score": scorecard.get("composite_score"),
            "risk_band": scorecard.get("risk_band"),
            "confidence_level": scorecard.get("confidence", "Unknown"),
        },
    }

    logger.info(
        "confidence_report_generated",
        overall=overall,
        completeness=round(avg_completeness, 3),
        domains=len(domain_confidence),
    )

    return report


def _assess_data_sources(extraction_stats, ga4_raw: dict) -> dict:
    """Assess which data sources were used and their status."""
    # Normalize extraction_stats to a list
    if isinstance(extraction_stats, dict):
        stats_list = [
            {"table": k, "status": v}
            for k, v in extraction_stats.items()
            if k not in ("ga4_source",)
        ]
        ga4_source = extraction_stats.get("ga4_source")
    elif isinstance(extraction_stats, list):
        stats_list = extraction_stats
        ga4_source = None
    else:
        stats_list = []
        ga4_source = None

    extractors_run = len(stats_list)
    extractors_ok = sum(1 for s in stats_list if s.get("status") in ("complete", "ok"))
    extractors_failed = sum(1 for s in stats_list if s.get("status") == "failed")

    sources = {
        "google_ads": {
            "status": "connected" if extractors_run > 0 else "unknown",
            "extractors_run": extractors_run,
            "extractors_ok": extractors_ok,
            "extractors_failed": extractors_failed,
        },
    }

    # GA4 source detection
    effective_source = ga4_source or ga4_raw.get("source")
    if ga4_raw and any(ga4_raw.get(k) for k in ["channel_revenue", "paid_vs_organic", "attribution"]):
        sources["ga4"] = {
            "status": "connected",
            "source": effective_source or "ga4_api",
            "extractors": [k for k in ga4_raw.keys() if k != "source" and ga4_raw.get(k)],
        }
        if effective_source == "bigquery":
            sources["bigquery"] = {"status": "connected", "used_as_ga4_source": True}
        else:
            sources["bigquery"] = {"status": "not_used"}
    else:
        sources["ga4"] = {"status": "not_available"}
        sources["bigquery"] = {"status": "not_available"}

    return sources


def _assess_domain_confidence(domain_scores, scorecard: dict) -> dict:
    """Assess confidence per scoring domain."""
    result = {}

    if isinstance(domain_scores, dict):
        for domain_name, ds in domain_scores.items():
            if not isinstance(ds, dict):
                continue
            sub_scores = ds.get("sub_scores", {})
            missing = [k for k, v in sub_scores.items() if v is None or v == 0]

            result[domain_name] = {
                "score": ds.get("value"),
                "weight": ds.get("weight"),
                "data_completeness": ds.get("data_completeness", 0),
                "sub_score_count": len(sub_scores),
                "sub_scores_with_data": len(sub_scores) - len(missing),
                "missing_data": missing,
            }
    elif isinstance(domain_scores, list):
        for ds in domain_scores:
            if not isinstance(ds, dict):
                continue
            domain_name = ds.get("domain", "unknown")
            sub_scores = ds.get("sub_scores", {})
            missing = [k for k, v in sub_scores.items() if v is None or v == 0]

            result[domain_name] = {
                "score": ds.get("value"),
                "weight": ds.get("weight"),
                "data_completeness": ds.get("data_completeness", 0),
                "sub_score_count": len(sub_scores),
                "sub_scores_with_data": len(sub_scores) - len(missing),
                "missing_data": missing,
            }

    return result


def _assess_red_flags(scorecard: dict) -> dict:
    """Assess red flag evaluation coverage."""
    red_flags = scorecard.get("red_flags", [])
    if not isinstance(red_flags, list):
        red_flags = []

    by_severity: dict[str, int] = {}
    by_domain: dict[str, int] = {}

    for rf in red_flags:
        if isinstance(rf, dict):
            sev = rf.get("severity", "unknown")
            dom = rf.get("domain", "unknown")
        elif hasattr(rf, "severity"):
            sev = rf.severity
            dom = rf.domain
        else:
            continue
        by_severity[sev] = by_severity.get(sev, 0) + 1
        by_domain[dom] = by_domain.get(dom, 0) + 1

    return {
        "total_triggered": len(red_flags),
        "by_severity": by_severity,
        "by_domain": by_domain,
    }
