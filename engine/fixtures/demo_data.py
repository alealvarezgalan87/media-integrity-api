"""Realistic Google Ads fixture data for demo audits.

Generates plausible metrics that produce interesting scoring results
across all 5 domains with red flags and varied risk bands.
"""

import uuid
from datetime import datetime, timezone

DEMO_ACCOUNTS = {
    "demo-moderate": {
        "account_id": "847-291-5630",
        "account_name": "StyleHaus E-Commerce",
        "date_range": {"start": "2025-07-01", "end": "2025-12-31"},
        "demand_capture": {
            "avg_search_impression_share": 0.42,
            "avg_budget_lost_impression_share": 0.25,
            "avg_rank_lost_impression_share": 0.18,
            "avg_outranking_share": 0.35,
        },
        "automation_exposure": {
            "pct_spend_automated": 0.75,
            "pct_spend_pmax": 0.45,
            "pmax_channel_concentration": 0.38,
            "bidding_strategy_diversity": 2,
        },
        "measurement_integrity": {
            "attribution_model_count": 3,
            "dda_adoption_rate": 0.40,
            "lookback_window_consistency": False,
            "conversion_action_count": 12,
            "ga4_ads_revenue_discrepancy": None,
        },
        "capital_allocation": {
            "avg_budget_utilization": 0.72,
            "spend_concentration_hhi": 0.35,
            "roas_variance_coefficient": 0.80,
            "zero_conversion_spend_pct": 0.18,
            "campaign_count": 8,
        },
        "creative_velocity": {
            "total_asset_count": 24,
            "asset_groups_count": 4,
            "pct_best_performing": 0.15,
            "pct_good_performing": 0.30,
            "pct_low_performing": 0.20,
            "pct_disapproved": 0.03,
            "format_diversity": 4,
            "data_completeness": 0.90,
        },
        "extraction_stats": [
            {"table": "campaigns_daily", "status": "complete", "rows": 1464},
            {"table": "conversions_snapshot", "status": "complete", "rows": 12},
            {"table": "pmax_breakdown", "status": "complete", "rows": 549},
            {"table": "auction_density", "status": "complete", "rows": 186},
            {"table": "creative_velocity", "status": "complete", "rows": 96},
            {"table": "attribution_config", "status": "partial", "rows": 0},
            {"table": "ga4_channel_performance", "status": "skipped", "rows": 0},
        ],
    },
    "demo-critical": {
        "account_id": "312-876-4509",
        "account_name": "NovaParts Industrial Supply",
        "date_range": {"start": "2025-07-01", "end": "2025-12-31"},
        "demand_capture": {
            "avg_search_impression_share": 0.22,
            "avg_budget_lost_impression_share": 0.40,
            "avg_rank_lost_impression_share": 0.35,
            "avg_outranking_share": 0.18,
        },
        "automation_exposure": {
            "pct_spend_automated": 0.92,
            "pct_spend_pmax": 0.65,
            "pmax_channel_concentration": 0.72,
            "bidding_strategy_diversity": 1,
        },
        "measurement_integrity": {
            "attribution_model_count": 4,
            "dda_adoption_rate": 0.20,
            "lookback_window_consistency": False,
            "conversion_action_count": 18,
            "ga4_ads_revenue_discrepancy": None,
        },
        "capital_allocation": {
            "avg_budget_utilization": 0.45,
            "spend_concentration_hhi": 0.55,
            "roas_variance_coefficient": 1.8,
            "zero_conversion_spend_pct": 0.32,
            "campaign_count": 12,
        },
        "creative_velocity": {
            "total_asset_count": 8,
            "asset_groups_count": 3,
            "pct_best_performing": 0.05,
            "pct_good_performing": 0.15,
            "pct_low_performing": 0.45,
            "pct_disapproved": 0.12,
            "format_diversity": 2,
            "data_completeness": 0.70,
        },
        "extraction_stats": [
            {"table": "campaigns_daily", "status": "complete", "rows": 2196},
            {"table": "conversions_snapshot", "status": "complete", "rows": 18},
            {"table": "pmax_breakdown", "status": "complete", "rows": 1098},
            {"table": "auction_density", "status": "partial", "rows": 42},
            {"table": "creative_velocity", "status": "complete", "rows": 48},
            {"table": "attribution_config", "status": "skipped", "rows": 0},
            {"table": "ga4_channel_performance", "status": "skipped", "rows": 0},
        ],
    },
    "demo-excellent": {
        "account_id": "654-123-8890",
        "account_name": "Pinnacle Performance Fitness",
        "date_range": {"start": "2025-07-01", "end": "2025-12-31"},
        "demand_capture": {
            "avg_search_impression_share": 0.78,
            "avg_budget_lost_impression_share": 0.05,
            "avg_rank_lost_impression_share": 0.08,
            "avg_outranking_share": 0.72,
        },
        "automation_exposure": {
            "pct_spend_automated": 0.55,
            "pct_spend_pmax": 0.25,
            "pmax_channel_concentration": 0.20,
            "bidding_strategy_diversity": 4,
        },
        "measurement_integrity": {
            "attribution_model_count": 1,
            "dda_adoption_rate": 0.95,
            "lookback_window_consistency": True,
            "conversion_action_count": 4,
            "ga4_ads_revenue_discrepancy": None,
        },
        "capital_allocation": {
            "avg_budget_utilization": 0.88,
            "spend_concentration_hhi": 0.15,
            "roas_variance_coefficient": 0.25,
            "zero_conversion_spend_pct": 0.03,
            "campaign_count": 6,
        },
        "creative_velocity": {
            "total_asset_count": 72,
            "asset_groups_count": 4,
            "pct_best_performing": 0.30,
            "pct_good_performing": 0.40,
            "pct_low_performing": 0.08,
            "pct_disapproved": 0.01,
            "format_diversity": 7,
            "data_completeness": 0.95,
        },
        "extraction_stats": [
            {"table": "campaigns_daily", "status": "complete", "rows": 1098},
            {"table": "conversions_snapshot", "status": "complete", "rows": 4},
            {"table": "pmax_breakdown", "status": "complete", "rows": 366},
            {"table": "auction_density", "status": "complete", "rows": 312},
            {"table": "creative_velocity", "status": "complete", "rows": 288},
            {"table": "attribution_config", "status": "partial", "rows": 0},
            {"table": "ga4_channel_performance", "status": "skipped", "rows": 0},
        ],
    },
}


def get_demo_account(account_key: str = "demo-moderate") -> dict:
    """Get a demo account fixture by key."""
    return DEMO_ACCOUNTS.get(account_key, DEMO_ACCOUNTS["demo-moderate"])


def list_demo_accounts() -> list[dict]:
    """List all available demo accounts."""
    return [
        {
            "key": key,
            "account_id": acct["account_id"],
            "account_name": acct["account_name"],
        }
        for key, acct in DEMO_ACCOUNTS.items()
    ]
