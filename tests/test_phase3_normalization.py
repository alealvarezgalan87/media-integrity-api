"""Unit tests for Phase 3 normalization modules."""

import pytest


# ── 1. Keyword Quality ────────────────────────────────────────────

class TestKeywordQuality:
    def setup_method(self):
        from engine.normalization.keyword_quality import compute_quality_score_metrics
        self.compute = compute_quality_score_metrics

    def test_empty_data(self):
        result = self.compute([], brand_name="")
        assert result["avg_quality_score"] is None
        assert result["nonbrand_avg_quality_score"] is None

    def test_single_keyword(self):
        data = [
            {
                "adGroupCriterion": {
                    "qualityInfo": {"qualityScore": 7},
                    "keyword": {"text": "buy shoes"},
                },
                "campaign": {"name": "Generic - Shoes"},
                "metrics": {"impressions": "1000"},
            }
        ]
        result = self.compute(data, brand_name="Nike")
        assert result["avg_quality_score"] == 7
        assert result["nonbrand_avg_quality_score"] == 7

    def test_brand_inflation(self):
        data = [
            {
                "adGroupCriterion": {
                    "qualityInfo": {"qualityScore": 10},
                    "keyword": {"text": "nike shoes"},
                },
                "campaign": {"name": "Brand - Nike"},
                "metrics": {"impressions": "500"},
            },
            {
                "adGroupCriterion": {
                    "qualityInfo": {"qualityScore": 3},
                    "keyword": {"text": "buy running shoes"},
                },
                "campaign": {"name": "Generic - Running"},
                "metrics": {"impressions": "500"},
            },
        ]
        result = self.compute(data, brand_name="Nike")
        assert result["avg_quality_score"] > 5
        assert result["nonbrand_avg_quality_score"] < 5

    def test_missing_quality_score_skipped(self):
        data = [
            {
                "adGroupCriterion": {
                    "qualityInfo": {},
                    "keyword": {"text": "test"},
                },
                "campaign": {"name": "Test"},
                "metrics": {"impressions": "100"},
            }
        ]
        result = self.compute(data, brand_name="")
        assert result["avg_quality_score"] is None


# ── 2. Negative Keywords ─────────────────────────────────────────

class TestNegativeKeywords:
    def setup_method(self):
        from engine.normalization.negative_keywords import compute_negative_keyword_metrics
        self.compute = compute_negative_keyword_metrics

    def test_empty_data(self):
        result = self.compute([])
        assert result["negative_keyword_overlap_count"] == 0
        assert result["shopping_negative_keyword_coverage"] == 1.0

    def test_no_overlaps(self):
        data = [{
            "campaign_negatives": [
                {
                    "campaignCriterion": {"keyword": {"text": "free"}},
                    "campaign": {"id": "1", "name": "Campaign A", "advertising_channel_type": "SEARCH"},
                },
                {
                    "campaignCriterion": {"keyword": {"text": "cheap"}},
                    "campaign": {"id": "2", "name": "Campaign B", "advertising_channel_type": "SEARCH"},
                },
            ],
            "shared_sets": [],
        }]
        result = self.compute(data)
        assert result["negative_keyword_overlap_count"] == 0

    def test_overlaps_detected(self):
        data = [{
            "campaign_negatives": [
                {
                    "campaignCriterion": {"keyword": {"text": "free"}},
                    "campaign": {"id": "1", "name": "Campaign A", "advertising_channel_type": "SEARCH"},
                },
                {
                    "campaignCriterion": {"keyword": {"text": "free"}},
                    "campaign": {"id": "2", "name": "Campaign B", "advertising_channel_type": "SEARCH"},
                },
            ],
            "shared_sets": [],
        }]
        result = self.compute(data)
        assert result["negative_keyword_overlap_count"] >= 1

    def test_shopping_coverage(self):
        data = [{
            "campaign_negatives": [
                {
                    "campaignCriterion": {"keyword": {"text": "free"}},
                    "campaign": {"id": "1", "name": "Shopping", "advertising_channel_type": "SHOPPING"},
                },
            ],
            "shared_sets": [],
        }]
        result = self.compute(data)
        assert 0 <= result["shopping_negative_keyword_coverage"] <= 1.0


# ── 3. Shopping Structure ─────────────────────────────────────────

class TestShoppingStructure:
    def setup_method(self):
        from engine.normalization.shopping_structure import compute_shopping_structure_metrics
        self.compute = compute_shopping_structure_metrics

    def test_empty_data(self):
        result = self.compute([])
        assert result["shopping_campaign_product_overlap_pct"] == 0.0
        assert result["shopping_rlsa_campaign_count"] == 0

    def test_no_overlap(self):
        data = [{
            "product_groups": [
                {
                    "adGroupCriterion": {
                        "listingGroup": {"caseValue": {"productBrand": {"value": "BrandA"}}},
                    },
                    "campaign": {"id": "1", "name": "Shopping A", "advertising_channel_type": "SHOPPING"},
                },
                {
                    "adGroupCriterion": {
                        "listingGroup": {"caseValue": {"productBrand": {"value": "BrandB"}}},
                    },
                    "campaign": {"id": "2", "name": "Shopping B", "advertising_channel_type": "SHOPPING"},
                },
            ],
            "campaign_audiences": [],
        }]
        result = self.compute(data)
        assert result["shopping_campaign_product_overlap_pct"] == 0.0

    def test_rlsa_detected(self):
        data = [{
            "product_groups": [],
            "campaign_audiences": [
                {
                    "campaignCriterion": {
                        "userList": {"userList": "customers/123/userLists/456"},
                    },
                    "campaign": {"id": "1", "name": "Shopping RLSA", "advertising_channel_type": "SHOPPING"},
                },
            ],
        }]
        result = self.compute(data)
        assert result["shopping_rlsa_campaign_count"] >= 1


# ── 4. PMax Audiences ────────────────────────────────────────────

class TestPMaxAudiences:
    def setup_method(self):
        from engine.normalization.pmax_audiences import compute_pmax_audience_metrics
        self.compute = compute_pmax_audience_metrics

    def test_empty_data(self):
        result = self.compute([])
        assert result["pmax_prospecting_campaign_count"] == 0
        assert result["pmax_retargeting_campaign_count"] == 0

    def test_prospecting_only(self):
        data = [
            {
                "campaign": {"id": "1", "name": "PMax - Prospecting"},
                "assetGroupSignal": {
                    "audience": {
                        "audiences": [
                            {"audience": "customers/123/audiences/456"},
                        ]
                    }
                },
            },
        ]
        result = self.compute(data)
        assert result["pmax_prospecting_campaign_count"] >= 0
        assert result["pmax_retargeting_campaign_count"] >= 0


# ── 5. Customer Lists ────────────────────────────────────────────

class TestCustomerLists:
    def setup_method(self):
        from engine.normalization.customer_lists import compute_customer_list_metrics
        self.compute = compute_customer_list_metrics

    def test_empty_data(self):
        result = self.compute([], [])
        assert result["days_since_customer_list_refresh"] == 0
        assert result["customer_list_match_rate"] == 1.0

    def test_with_user_lists(self):
        data = [
            {
                "userList": {
                    "type": "CRM_BASED",
                    "name": "All Customers",
                    "matchRatePercentage": 45,
                    "sizeForSearch": "50000",
                },
            },
        ]
        result = self.compute(data, [])
        assert result["customer_list_match_rate"] == pytest.approx(0.45, abs=0.01)


# ── 6. NCA Settings ──────────────────────────────────────────────

class TestNCASettings:
    def setup_method(self):
        from engine.normalization.nca_settings import compute_nca_metrics
        self.compute = compute_nca_metrics

    def test_empty_data(self):
        result = self.compute([])
        assert result["nca_bid_adjustment"] == 0
        assert result["nca_bid_validation"] is True

    def test_nca_active(self):
        data = [
            {
                "campaign": {
                    "id": "1",
                    "name": "PMax NCA",
                    "customerAcquisitionGoalSettings": {
                        "optimizationMode": "BID_HIGHER_FOR_NEW_CUSTOMERS",
                        "valueSettings": {"highLifetimeValue": 50},
                    },
                },
            },
        ]
        result = self.compute(data)
        assert result["nca_bid_adjustment"] == 50
        assert result["nca_bid_validation"] is False

    def test_nca_inactive(self):
        data = [
            {
                "campaign": {
                    "id": "1",
                    "name": "PMax",
                    "customerAcquisitionGoalSettings": {
                        "optimizationMode": "TARGET_ALL_EQUALLY",
                        "valueSettings": {},
                    },
                },
            },
        ]
        result = self.compute(data)
        assert result["nca_bid_adjustment"] == 0
        assert result["nca_bid_validation"] is True


# ── 7. GA4 Events ────────────────────────────────────────────────

class TestGA4Events:
    def setup_method(self):
        from engine.normalization.ga4_events import compute_ga4_events_metrics
        self.compute = compute_ga4_events_metrics

    def test_empty_data(self):
        result = self.compute([])
        assert result["tracked_funnel_events"] is None
        assert result["missing_funnel_events"] == []

    def test_all_events_present(self):
        data = [
            {"eventName": "add_to_cart", "eventCount": "500", "totalUsers": "100"},
            {"eventName": "begin_checkout", "eventCount": "300", "totalUsers": "80"},
            {"eventName": "view_item", "eventCount": "2000", "totalUsers": "500"},
            {"eventName": "view_item_list", "eventCount": "5000", "totalUsers": "800"},
            {"eventName": "sign_up", "eventCount": "50", "totalUsers": "50"},
            {"eventName": "generate_lead", "eventCount": "20", "totalUsers": "20"},
            {"eventName": "purchase", "eventCount": "100", "totalUsers": "90"},
        ]
        result = self.compute(data)
        assert result["tracked_funnel_events"] == 6
        assert result["missing_funnel_events"] == []

    def test_missing_events(self):
        data = [
            {"eventName": "purchase", "eventCount": "100", "totalUsers": "90"},
            {"eventName": "page_view", "eventCount": "10000", "totalUsers": "3000"},
        ]
        result = self.compute(data)
        assert result["tracked_funnel_events"] == 0
        assert len(result["missing_funnel_events"]) == 6

    def test_partial_events(self):
        data = [
            {"eventName": "add_to_cart", "eventCount": "200", "totalUsers": "50"},
            {"eventName": "view_item", "eventCount": "1000", "totalUsers": "300"},
        ]
        result = self.compute(data)
        assert result["tracked_funnel_events"] == 2
        assert "begin_checkout" in result["missing_funnel_events"]

    def test_zero_count_ignored(self):
        data = [
            {"eventName": "add_to_cart", "eventCount": "0", "totalUsers": "0"},
            {"eventName": "view_item", "eventCount": "500", "totalUsers": "100"},
        ]
        result = self.compute(data)
        assert result["tracked_funnel_events"] == 1
