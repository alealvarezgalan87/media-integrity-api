"""Unit tests for compound condition evaluator in red_flags.py."""

import pytest

from engine.scoring.red_flags import _evaluate_condition, _evaluate_single_condition


class TestSingleCondition:
    """Tests for atomic condition evaluation."""

    def test_greater_than_true(self):
        ok, key = _evaluate_single_condition("avg_quality_score > 7", {"avg_quality_score": 8})
        assert ok is True
        assert key == "avg_quality_score"

    def test_greater_than_false(self):
        ok, key = _evaluate_single_condition("avg_quality_score > 7", {"avg_quality_score": 5})
        assert ok is False

    def test_less_than(self):
        ok, _ = _evaluate_single_condition("nonbrand_avg_quality_score < 5", {"nonbrand_avg_quality_score": 3})
        assert ok is True

    def test_equal_true(self):
        ok, _ = _evaluate_single_condition("shopping_rlsa_campaign_count == 0", {"shopping_rlsa_campaign_count": 0})
        assert ok is True

    def test_equal_false(self):
        ok, _ = _evaluate_single_condition("shopping_rlsa_campaign_count == 0", {"shopping_rlsa_campaign_count": 2})
        assert ok is False

    def test_not_equal(self):
        ok, _ = _evaluate_single_condition("campaign_count != 0", {"campaign_count": 5})
        assert ok is True

    def test_gte(self):
        ok, _ = _evaluate_single_condition("pct_spend_pmax >= 0.60", {"pct_spend_pmax": 0.60})
        assert ok is True

    def test_lte(self):
        ok, _ = _evaluate_single_condition("roas_variance_coefficient <= 1.5", {"roas_variance_coefficient": 1.0})
        assert ok is True

    def test_none_value_returns_false(self):
        ok, _ = _evaluate_single_condition("avg_quality_score > 7", {"avg_quality_score": None})
        assert ok is False

    def test_missing_metric_returns_false(self):
        ok, _ = _evaluate_single_condition("avg_quality_score > 7", {})
        assert ok is False

    def test_boolean_equal_false(self):
        ok, _ = _evaluate_single_condition("nca_bid_validation == false", {"nca_bid_validation": False})
        assert ok is True

    def test_boolean_equal_true(self):
        ok, _ = _evaluate_single_condition("profit_based_bidding == true", {"profit_based_bidding": True})
        assert ok is True

    def test_boolean_equal_true_negative(self):
        ok, _ = _evaluate_single_condition("profit_based_bidding == true", {"profit_based_bidding": False})
        assert ok is False


class TestCompoundCondition:
    """Tests for 'and'/'or' compound conditions."""

    def test_and_both_true(self):
        metrics = {"avg_quality_score": 8, "nonbrand_avg_quality_score": 4}
        ok, _ = _evaluate_condition("avg_quality_score > 7 and nonbrand_avg_quality_score < 5", metrics)
        assert ok is True

    def test_and_first_false(self):
        metrics = {"avg_quality_score": 5, "nonbrand_avg_quality_score": 4}
        ok, _ = _evaluate_condition("avg_quality_score > 7 and nonbrand_avg_quality_score < 5", metrics)
        assert ok is False

    def test_and_second_false(self):
        metrics = {"avg_quality_score": 8, "nonbrand_avg_quality_score": 6}
        ok, _ = _evaluate_condition("avg_quality_score > 7 and nonbrand_avg_quality_score < 5", metrics)
        assert ok is False

    def test_and_both_false(self):
        metrics = {"avg_quality_score": 5, "nonbrand_avg_quality_score": 6}
        ok, _ = _evaluate_condition("avg_quality_score > 7 and nonbrand_avg_quality_score < 5", metrics)
        assert ok is False

    def test_or_first_true(self):
        metrics = {"days_since_customer_list_refresh": 100, "customer_list_match_rate": 0.5}
        ok, _ = _evaluate_condition(
            "days_since_customer_list_refresh > 90 or customer_list_match_rate < 0.30", metrics
        )
        assert ok is True

    def test_or_second_true(self):
        metrics = {"days_since_customer_list_refresh": 30, "customer_list_match_rate": 0.10}
        ok, _ = _evaluate_condition(
            "days_since_customer_list_refresh > 90 or customer_list_match_rate < 0.30", metrics
        )
        assert ok is True

    def test_or_both_true(self):
        metrics = {"days_since_customer_list_refresh": 120, "customer_list_match_rate": 0.10}
        ok, _ = _evaluate_condition(
            "days_since_customer_list_refresh > 90 or customer_list_match_rate < 0.30", metrics
        )
        assert ok is True

    def test_or_both_false(self):
        metrics = {"days_since_customer_list_refresh": 30, "customer_list_match_rate": 0.50}
        ok, _ = _evaluate_condition(
            "days_since_customer_list_refresh > 90 or customer_list_match_rate < 0.30", metrics
        )
        assert ok is False

    def test_and_with_boolean(self):
        metrics = {"profit_based_bidding": False, "revenue_based_bidding": True}
        ok, _ = _evaluate_condition(
            "profit_based_bidding == false and revenue_based_bidding == true", metrics
        )
        assert ok is True

    def test_and_with_boolean_not_triggered(self):
        metrics = {"profit_based_bidding": True, "revenue_based_bidding": True}
        ok, _ = _evaluate_condition(
            "profit_based_bidding == false and revenue_based_bidding == true", metrics
        )
        assert ok is False

    def test_or_with_zero_values(self):
        metrics = {"pmax_prospecting_campaign_count": 0, "pmax_retargeting_campaign_count": 3}
        ok, _ = _evaluate_condition(
            "pmax_prospecting_campaign_count == 0 or pmax_retargeting_campaign_count == 0", metrics
        )
        assert ok is True

    def test_or_neither_zero(self):
        metrics = {"pmax_prospecting_campaign_count": 2, "pmax_retargeting_campaign_count": 3}
        ok, _ = _evaluate_condition(
            "pmax_prospecting_campaign_count == 0 or pmax_retargeting_campaign_count == 0", metrics
        )
        assert ok is False

    def test_none_in_compound_and(self):
        metrics = {"avg_quality_score": None, "nonbrand_avg_quality_score": 4}
        ok, _ = _evaluate_condition("avg_quality_score > 7 and nonbrand_avg_quality_score < 5", metrics)
        assert ok is False

    def test_none_in_compound_or(self):
        metrics = {"days_since_customer_list_refresh": None, "customer_list_match_rate": 0.10}
        ok, _ = _evaluate_condition(
            "days_since_customer_list_refresh > 90 or customer_list_match_rate < 0.30", metrics
        )
        assert ok is True

    def test_simple_condition_passthrough(self):
        metrics = {"tracked_funnel_events": 1}
        ok, key = _evaluate_condition("tracked_funnel_events < 3", metrics)
        assert ok is True
        assert key == "tracked_funnel_events"


class TestAllPhase3Conditions:
    """Integration: test each Phase 3 rule condition with realistic data."""

    def test_dc_qs_brand_inflation(self):
        ok, _ = _evaluate_condition(
            "avg_quality_score > 7 and nonbrand_avg_quality_score < 5",
            {"avg_quality_score": 8.5, "nonbrand_avg_quality_score": 3.2},
        )
        assert ok is True

    def test_dc_negkw_mismanagement(self):
        ok, _ = _evaluate_condition(
            "negative_keyword_overlap_count > 10",
            {"negative_keyword_overlap_count": 25},
        )
        assert ok is True

    def test_dc_shopping_negkw_weak(self):
        ok, _ = _evaluate_condition(
            "shopping_negative_keyword_coverage < 0.50",
            {"shopping_negative_keyword_coverage": 0.3},
        )
        assert ok is True

    def test_dc_shopping_overlap(self):
        ok, _ = _evaluate_condition(
            "shopping_campaign_product_overlap_pct > 0.30",
            {"shopping_campaign_product_overlap_pct": 0.45},
        )
        assert ok is True

    def test_dc_shopping_no_rlsa(self):
        ok, _ = _evaluate_condition(
            "shopping_rlsa_campaign_count == 0",
            {"shopping_rlsa_campaign_count": 0},
        )
        assert ok is True

    def test_ae_pmax_no_pro_ret_split(self):
        ok, _ = _evaluate_condition(
            "pmax_prospecting_campaign_count == 0 or pmax_retargeting_campaign_count == 0",
            {"pmax_prospecting_campaign_count": 0, "pmax_retargeting_campaign_count": 2},
        )
        assert ok is True

    def test_ae_outdated_customer_lists(self):
        ok, _ = _evaluate_condition(
            "days_since_customer_list_refresh > 90 or customer_list_match_rate < 0.30",
            {"days_since_customer_list_refresh": 120, "customer_list_match_rate": 0.5},
        )
        assert ok is True

    def test_ae_nca_bid_unverified(self):
        ok, _ = _evaluate_condition(
            "nca_bid_adjustment > 0 and nca_bid_validation == false",
            {"nca_bid_adjustment": 50, "nca_bid_validation": False},
        )
        assert ok is True

    def test_mi_missing_midfunnel(self):
        ok, _ = _evaluate_condition(
            "tracked_funnel_events < 3",
            {"tracked_funnel_events": 1},
        )
        assert ok is True

    def test_ca_no_profit_bidding(self):
        ok, _ = _evaluate_condition(
            "profit_based_bidding == false and revenue_based_bidding == true",
            {"profit_based_bidding": False, "revenue_based_bidding": True},
        )
        assert ok is True
