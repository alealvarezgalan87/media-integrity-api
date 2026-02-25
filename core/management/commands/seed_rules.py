"""
Management command to seed the 15 default red flag rules.
Idempotent — skips rules that already exist.
"""

from django.core.management.base import BaseCommand

from core.models import RedFlagRule

DEFAULT_RULES = [
    {
        "id": "DC-LOW-IS",
        "severity": "high",
        "domain": "demand_capture_integrity",
        "condition": "avg_search_impression_share < 0.30",
        "title": "Critically Low Impression Share",
        "description": "Average search impression share is below 30%, indicating significant missed demand.",
        "recommendation": "Review budget allocation and bid strategies to increase impression share coverage.",
    },
    {
        "id": "DC-BUDGET-CONSTRAINED",
        "severity": "high",
        "domain": "demand_capture_integrity",
        "condition": "avg_budget_lost_is > 0.30",
        "title": "Budget-Constrained Campaigns",
        "description": "More than 30% of impression share is lost due to budget constraints.",
        "recommendation": "Increase budgets on high-performing campaigns or reallocate from underperformers.",
    },
    {
        "id": "DC-RANK-LOST",
        "severity": "medium",
        "domain": "demand_capture_integrity",
        "condition": "avg_rank_lost_is > 0.25",
        "title": "Rank-Constrained Campaigns",
        "description": "More than 25% of impression share is lost due to ad rank.",
        "recommendation": "Improve quality scores and review bid strategies to improve ad position.",
    },
    {
        "id": "AE-PMAX-DOMINANT",
        "severity": "high",
        "domain": "automation_exposure",
        "condition": "pmax_spend_pct > 0.70",
        "title": "PMax Over-Concentration",
        "description": "Performance Max campaigns account for more than 70% of total spend.",
        "recommendation": "Diversify campaign types to reduce dependency on a single automated system.",
    },
    {
        "id": "AE-LOW-DIVERSITY",
        "severity": "medium",
        "domain": "automation_exposure",
        "condition": "bidding_strategy_diversity < 2",
        "title": "Low Bidding Strategy Diversity",
        "description": "Account uses fewer than 2 distinct bidding strategies.",
        "recommendation": "Test different bidding strategies across campaigns for better control.",
    },
    {
        "id": "AE-CHANNEL-CONCENTRATED",
        "severity": "medium",
        "domain": "automation_exposure",
        "condition": "pmax_channel_hhi > 0.50",
        "title": "PMax Channel Concentration",
        "description": "PMax spend is heavily concentrated in one channel (HHI > 0.50).",
        "recommendation": "Review PMax asset groups and signals to encourage broader channel distribution.",
    },
    {
        "id": "MI-NO-DDA",
        "severity": "high",
        "domain": "measurement_integrity",
        "condition": "dda_adoption_rate < 0.50",
        "title": "Low Data-Driven Attribution Adoption",
        "description": "Less than 50% of conversion actions use data-driven attribution.",
        "recommendation": "Migrate conversion actions to data-driven attribution for more accurate measurement.",
    },
    {
        "id": "MI-MODEL-INCONSISTENT",
        "severity": "medium",
        "domain": "measurement_integrity",
        "condition": "attribution_model_count > 3",
        "title": "Inconsistent Attribution Models",
        "description": "Account uses more than 3 different attribution models across conversion actions.",
        "recommendation": "Standardize attribution models across all conversion actions.",
    },
    {
        "id": "MI-LOOKBACK-INCONSISTENT",
        "severity": "medium",
        "domain": "measurement_integrity",
        "condition": "lookback_window_consistency < 0.50",
        "title": "Inconsistent Lookback Windows",
        "description": "Less than 50% of conversion actions share the same lookback window.",
        "recommendation": "Standardize lookback windows for consistent measurement.",
    },
    {
        "id": "CA-LOW-UTILIZATION",
        "severity": "high",
        "domain": "capital_allocation_discipline",
        "condition": "avg_budget_utilization < 0.50",
        "title": "Low Budget Utilization",
        "description": "Average budget utilization is below 50%, indicating significant unspent budget.",
        "recommendation": "Right-size budgets or reallocate to campaigns that can use the spend effectively.",
    },
    {
        "id": "CA-HIGH-WASTE",
        "severity": "high",
        "domain": "capital_allocation_discipline",
        "condition": "zero_conversion_spend_pct > 0.20",
        "title": "High Wasted Spend",
        "description": "More than 20% of spend goes to campaigns with zero conversions.",
        "recommendation": "Pause or restructure zero-conversion campaigns immediately.",
    },
    {
        "id": "CA-ROAS-VARIANCE",
        "severity": "medium",
        "domain": "capital_allocation_discipline",
        "condition": "roas_cv > 1.5",
        "title": "High ROAS Variance",
        "description": "ROAS coefficient of variation exceeds 1.5, indicating inconsistent returns.",
        "recommendation": "Review campaign-level ROAS and reallocate budget from low performers.",
    },
    {
        "id": "CV-LOW-ASSETS",
        "severity": "medium",
        "domain": "creative_velocity",
        "condition": "total_assets < 10",
        "title": "Low Creative Asset Volume",
        "description": "Fewer than 10 creative assets in the account.",
        "recommendation": "Increase creative diversity to improve ad performance and testing velocity.",
    },
    {
        "id": "CV-HIGH-DISAPPROVAL",
        "severity": "high",
        "domain": "creative_velocity",
        "condition": "disapproval_rate > 0.10",
        "title": "High Asset Disapproval Rate",
        "description": "More than 10% of creative assets have been disapproved.",
        "recommendation": "Review and fix disapproved assets to restore delivery capacity.",
    },
    {
        "id": "CV-LOW-PERFORMERS",
        "severity": "medium",
        "domain": "creative_velocity",
        "condition": "low_performer_pct > 0.40",
        "title": "High Proportion of Low-Performing Assets",
        "description": "More than 40% of assets are rated as low performers.",
        "recommendation": "Replace low-performing assets with new creative variants.",
    },
]


class Command(BaseCommand):
    help = "Seed the default 15 red flag rules (idempotent)."

    def handle(self, *args, **options):
        created_count = 0
        skipped_count = 0

        for idx, rule_data in enumerate(DEFAULT_RULES):
            _, created = RedFlagRule.objects.get_or_create(
                id=rule_data["id"],
                defaults={
                    "severity": rule_data["severity"],
                    "domain": rule_data["domain"],
                    "condition": rule_data["condition"],
                    "title": rule_data["title"],
                    "description": rule_data["description"],
                    "recommendation": rule_data["recommendation"],
                    "enabled": True,
                    "sort_order": idx * 10,
                    "is_system": True,
                    "organization": None,
                },
            )
            if created:
                created_count += 1
            else:
                skipped_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {created_count} rules created, {skipped_count} already existed."
            )
        )
