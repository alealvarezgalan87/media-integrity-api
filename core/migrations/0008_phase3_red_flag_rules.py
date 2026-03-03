"""Data migration: Create Phase 3 Red Flag Rules (10 new rules, 25→35 total)."""

from django.db import migrations

PHASE3_RULES = [
    {
        "id": "DC-QS-BRAND-INFLATION",
        "severity": "medium",
        "domain": "demand_capture_integrity",
        "condition": "avg_quality_score > 7 and nonbrand_avg_quality_score < 5",
        "title": "Quality Score Inflated by Brand Keywords",
        "description": (
            "Overall Quality Score appears healthy but is inflated by branded keywords. "
            "Non-brand keywords have significantly lower QS, indicating real ad relevance "
            "and landing page issues."
        ),
        "recommendation": (
            "Report QS separately for brand and non-brand. Focus optimization on non-brand "
            "ad relevance, expected CTR, and landing page experience."
        ),
        "enabled": True,
        "is_system": True,
        "sort_order": 109,
    },
    {
        "id": "DC-NEGKW-MISMANAGEMENT",
        "severity": "high",
        "domain": "demand_capture_integrity",
        "condition": "negative_keyword_overlap_count > 10",
        "title": "Negative Keywords Mismanagement",
        "description": (
            "Negative keyword lists have overlaps across campaigns, causing wasted spend "
            "on irrelevant search terms and blocking relevant traffic."
        ),
        "recommendation": (
            "Conduct quarterly negative keyword audits. Eliminate cross-campaign overlaps. "
            "Implement shared negative keyword lists with clear ownership."
        ),
        "enabled": True,
        "is_system": True,
        "sort_order": 105,
    },
    {
        "id": "DC-SHOPPING-NEGKW-WEAK",
        "severity": "high",
        "domain": "demand_capture_integrity",
        "condition": "shopping_negative_keyword_coverage < 0.50",
        "title": "Shopping Negative Keywords Insufficient",
        "description": (
            "Shopping campaigns have insufficient negative keywords for proper traffic control. "
            "Irrelevant search terms are triggering product ads, wasting budget."
        ),
        "recommendation": (
            "Audit search term reports for Shopping campaigns. Add negative keywords for "
            "irrelevant queries. Implement tiered exclusion lists by product category."
        ),
        "enabled": True,
        "is_system": True,
        "sort_order": 111,
    },
    {
        "id": "DC-SHOPPING-OVERLAP",
        "severity": "critical",
        "domain": "demand_capture_integrity",
        "condition": "shopping_campaign_product_overlap_pct > 0.30",
        "title": "Shopping Campaign Product Overlap",
        "description": (
            "More than 30% of products are targeted by multiple Shopping campaigns without "
            "proper exclusions, causing internal competition and budget inefficiency."
        ),
        "recommendation": (
            "Implement product-level exclusions to prevent overlap. Ensure each product "
            "is served by exactly one campaign."
        ),
        "enabled": True,
        "is_system": True,
        "sort_order": 106,
    },
    {
        "id": "DC-SHOPPING-NO-RLSA",
        "severity": "high",
        "domain": "demand_capture_integrity",
        "condition": "shopping_rlsa_campaign_count == 0",
        "title": "No Remarketing Lists for Shopping Ads",
        "description": (
            "No RLSA campaigns exist for Shopping, missing the opportunity to bid more "
            "aggressively on users who already know the brand."
        ),
        "recommendation": (
            "Create a dedicated Shopping remarketing campaign with higher bids for past "
            "visitors and cart abandoners."
        ),
        "enabled": True,
        "is_system": True,
        "sort_order": 107,
    },
    {
        "id": "AE-PMAX-NO-PRO-RET-SPLIT",
        "severity": "high",
        "domain": "automation_exposure",
        "condition": "pmax_prospecting_campaign_count == 0 or pmax_retargeting_campaign_count == 0",
        "title": "PMax Missing Prospecting vs Retargeting Split",
        "description": (
            "PMax campaigns do not separate prospecting from retargeting, making it impossible "
            "to control spend allocation between new and existing customers."
        ),
        "recommendation": (
            "Create separate PMax campaigns or asset groups for prospecting and retargeting. "
            "Use customer lists to define audience segments."
        ),
        "enabled": True,
        "is_system": True,
        "sort_order": 205,
    },
    {
        "id": "AE-OUTDATED-CUSTOMER-LISTS",
        "severity": "high",
        "domain": "automation_exposure",
        "condition": "days_since_customer_list_refresh > 90 or customer_list_match_rate < 0.30",
        "title": "Outdated Customer Lists",
        "description": (
            "Customer match lists have not been refreshed in over 90 days or have a match "
            "rate below 30%, degrading audience signal quality for automated campaigns."
        ),
        "recommendation": (
            "Refresh customer lists monthly. Use automated CRM syncs. Verify match rates "
            "and supplement with first-party data."
        ),
        "enabled": True,
        "is_system": True,
        "sort_order": 206,
    },
    {
        "id": "AE-NCA-BID-UNVERIFIED",
        "severity": "medium",
        "domain": "automation_exposure",
        "condition": "nca_bid_adjustment > 0 and nca_bid_validation == false",
        "title": "New Customer Acquisition Bid Not Validated",
        "description": (
            "A new customer acquisition bid adjustment is set but has not been validated "
            "against actual customer acquisition costs and LTV data."
        ),
        "recommendation": (
            "Verify the NCA bid value against real CAC and LTV metrics. Adjust if the bid "
            "does not reflect incremental revenue from new customers."
        ),
        "enabled": True,
        "is_system": True,
        "sort_order": 208,
    },
    {
        "id": "MI-MISSING-MIDFUNNEL",
        "severity": "critical",
        "domain": "measurement_integrity",
        "condition": "tracked_funnel_events < 3",
        "title": "Missing Mid-Funnel Conversion Tracking",
        "description": (
            "The account tracks fewer than 3 mid-funnel events (e.g., only purchase). "
            "Missing Add to Cart, Begin Checkout, View Item limits audience segmentation "
            "and optimization signals."
        ),
        "recommendation": (
            "Implement tracking for: Add to Cart, Begin Checkout, View Item, View Item List, "
            "Sign Up. These are critical for awareness and prospecting campaign optimization."
        ),
        "enabled": True,
        "is_system": True,
        "sort_order": 306,
    },
    {
        "id": "CA-NO-PROFIT-BIDDING",
        "severity": "high",
        "domain": "capital_allocation_discipline",
        "condition": "profit_based_bidding == false and revenue_based_bidding == true",
        "title": "No Profit-Based Bidding Strategy",
        "description": (
            "Campaigns optimize for revenue (tROAS) without connection to actual product "
            "margins. High-revenue but low-margin products consume disproportionate budget."
        ),
        "recommendation": (
            "Implement profit-based bidding using value rules, custom labels in product feed, "
            "or margin data in conversion values. Segment campaigns by margin tier."
        ),
        "enabled": True,
        "is_system": True,
        "sort_order": 404,
    },
]


def create_phase3_rules(apps, schema_editor):
    RedFlagRule = apps.get_model("core", "RedFlagRule")
    for rule_data in PHASE3_RULES:
        RedFlagRule.objects.update_or_create(
            id=rule_data["id"],
            defaults=rule_data,
        )


def remove_phase3_rules(apps, schema_editor):
    RedFlagRule = apps.get_model("core", "RedFlagRule")
    ids = [r["id"] for r in PHASE3_RULES]
    RedFlagRule.objects.filter(id__in=ids).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_audit_slug"),
    ]

    operations = [
        migrations.RunPython(create_phase3_rules, remove_phase3_rules),
    ]
