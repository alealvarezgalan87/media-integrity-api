"""Cross-reference Google Ads and GA4 attribution settings — Sprint 4, Task 4.7.

Schema: Cross-platform attribution comparison.
Phase 2 (Sprint 4+).
Flag mismatches between Google Ads and GA4 attribution models.
"""

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


def build_attribution_config(
    google_ads_conversions: list[dict],
    ga4_attribution: list[dict],
) -> pd.DataFrame:
    """Build the attribution_config canonical table.

    Args:
        google_ads_conversions: Conversion action config from Google Ads.
        ga4_attribution: Attribution data from GA4.

    Returns:
        DataFrame with cross-platform attribution comparison.
    """
    # TODO: Implement normalization
    # - Cross-reference attribution models
    # - Flag model_match = false
    # - Calculate discrepancy_percentage
    raise NotImplementedError("Sprint 4 — Task 4.7")
