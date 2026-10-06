import copy
import math
import unittest

from jobs.fundamental_context import assess, change, metrics


class ContextualAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.history = {"annual": {}, "quarters": {}, "balance": {}, "cash": {}, "returns": {}}
        for year in range(2023, 2027):
            period = f"{year}-03-31"
            factor = 1.1 ** (year - 2023)
            self.history["annual"][period] = {
                "months": 12,
                "revenue": 1000 * factor,
                "operating": 200 * factor,
                "net": 100 * factor,
                "interest": 10 * factor,
                "ebit": 180 * factor,
                "margin": 20,
                "payout": 30,
            }
            self.history["balance"][period] = {"debt": 100, "equity": 200, "de": 0.5}
            self.history["cash"][period] = 110 * factor
            self.history["returns"][period] = 20
        for year, factor in [(2025, 1), (2026, 1.1)]:
            self.history["quarters"][f"{year}-06-30"] = {
                "revenue": 250 * factor,
                "net": 25 * factor,
                "ebit": 45 * factor,
            }
        self.m = metrics(self.history)
        self.base = dict(
            Symbol="TEST",
            Sector="Information Technology",
            Industry="Software",
            Broad_Industry="IT - Software",
            Business_Type="Non_Financial_or_Capital_Markets",
            Debt_Equity=0.5,
            ROCE=20,
            OPM=20,
            PE=20,
            Promoter_Pledge=0,
            Promoter_Encumbrance=0,
            Encumbrance_Total_Capital=0,
            Promoter_YoY=0,
            _equity=200,
            _net_profit=130,
            _last_annual_profit=130,
            _context_metrics=self.m,
            Dividend_Yield=0,
        )

    def rate(self, row_changes=None, metric_changes=None):
        row = copy.deepcopy(self.base)
        row.update(row_changes or {})
        row["_context_metrics"].update(metric_changes or {})
        peers = [dict(self.base, Symbol=f"P{i}") for i in range(5)]
        result = assess(row, peers)
        if result["score"] is not None:
            score = result["score"]
            self.assertTrue(math.isfinite(score) and 0 <= score <= 100)
            expected = next(
                label
                for lower, label in [
                    (90, "Very Strong"),
                    (75, "Strong"),
                    (60, "Moderate"),
                    (40, "Weak"),
                    (0, "Very Weak"),
                ]
                if score >= lower
            )
            self.assertEqual(result["label"], expected)
            self.assertLessEqual(score, result["raw_score"])
        return result

    def test_missing_dividend_yield_is_not_treated_as_a_paid_dividend(self):
        missing = self.rate({"Dividend_Yield": None})
        zero = self.rate({"Dividend_Yield": 0})
        self.assertEqual(missing, zero)

    def test_half_equity_debt_can_be_supported(self):
        result = self.rate()
        self.assertEqual(result["dimensions"]["Leverage"], "Strong")
        self.assertEqual(result["label"], "Very Strong")

    def test_identical_debt_with_losses_has_different_assessment(self):
        good = self.rate()
        poor = self.rate(
            {"_net_profit": -100, "_last_annual_profit": -80},
            {
                "Loss_Years_3Y": 3,
                "Profitable_Years_3Y": 0,
                "Core_EBIT": -50,
                "Core_Profit_Before_Tax": -60,
                "Latest_Quarter_Profit": -20,
            },
        )
        self.assertNotEqual(good["label"], poor["label"])
        self.assertEqual(poor["label"], "Very Weak")

    def test_zero_debt_is_not_automatic_business_quality(self):
        poor = self.rate(
            {"Debt_Equity": 0, "_net_profit": -100, "_last_annual_profit": -80},
            {
                "Loss_Years_3Y": 3,
                "Core_EBIT": -50,
                "Core_Profit_Before_Tax": -60,
                "Latest_Quarter_Profit": -20,
            },
        )
        self.assertEqual(poor["label"], "Very Weak")

    def test_borrowing_and_profitable_growth_can_be_healthy(self):
        result = self.rate({"Debt_Equity": 1}, {"Debt_EBITDA": 2, "Interest_Coverage": 4})
        self.assertEqual(result["dimensions"]["Leverage"], "Strong")
        self.assertIn(result["label"], {"Strong", "Very Strong"})

    def test_cash_quality_changes_same_debt_assessment(self):
        result = self.rate(
            metric_changes={
                "Cash_Conversion": -0.2,
                "Latest_Operating_Cash_Flow": -100,
                "Negative_Cash_Flow_Years": 2,
                "Positive_Cash_Flow_Years": 1,
            }
        )
        self.assertEqual(result["dimensions"]["Cash_Flow"], "Weak")
        self.assertNotIn(result["label"], {"Strong", "Very Strong"})

    def test_growth_without_interest_service_support_is_not_strong(self):
        result = self.rate(
            metric_changes={
                "Interest_Coverage": 0.8,
                "Cash_Conversion": -0.2,
                "Latest_Operating_Cash_Flow": -100,
                "Negative_Cash_Flow_Years": 2,
            }
        )
        self.assertEqual(result["label"], "Very Weak")

    def test_mature_stable_cash_generator_need_not_have_high_growth(self):
        result = self.rate(
            metric_changes={
                "Revenue_Growth_YoY": 0,
                "Profit_Growth_YoY": 0,
                "Quarter_Revenue_Growth_YoY": 0,
                "Quarter_Operating_Profit_Growth_YoY": 0,
            }
        )
        self.assertEqual(result["dimensions"]["Growth"], "Strong")
        self.assertIn(result["label"], {"Strong", "Very Strong"})

    def test_improving_expansion_returns_can_support_strength(self):
        result = self.rate({"ROCE": 14}, {"ROCE_Change_YoY_PP": 1})
        self.assertEqual(result["dimensions"]["Capital_Efficiency"], "Strong")

    def test_same_low_roce_without_support_is_not_strong(self):
        result = self.rate(
            {"ROCE": 14},
            {"ROCE_Change_YoY_PP": -3, "Revenue_Growth_YoY": -10, "Profit_Growth_YoY": -20},
        )
        self.assertNotIn(result["label"], {"Strong", "Very Strong"})

    def test_low_margin_can_be_validated_by_turnover_returns_and_cash(self):
        result = self.rate({"OPM": 2})
        self.assertEqual(result["dimensions"]["Operating_Performance"], "Strong")

    def test_single_recent_loss_is_not_persistent_distress(self):
        result = self.rate(metric_changes={"Latest_Quarter_Profit": -1})
        self.assertEqual(result["label"], "Moderate")
        self.assertNotEqual(result["profile"], "Persistent_operating_or_debt_service_distress")

    def test_declining_annual_and_quarterly_performance_is_joint_warning(self):
        result = self.rate(
            metric_changes={
                "Revenue_Growth_YoY": -20,
                "Profit_Growth_YoY": -30,
                "Quarter_Revenue_Growth_YoY": -10,
                "Quarter_Operating_Profit_Growth_YoY": -20,
            }
        )
        self.assertEqual(result["dimensions"]["Growth"], "Weak")
        self.assertNotIn(result["label"], {"Strong", "Very Strong"})

    def test_financial_business_not_penalized_for_industrial_debt_cfo(self):
        result = self.rate(
            {"Business_Type": "Regulated_Financial", "Debt_Equity": 8},
            {"Latest_Operating_Cash_Flow": -100, "Negative_Cash_Flow_Years": 3},
        )
        self.assertEqual(result["label"], "Limited Assessment")
        self.assertIsNone(result["score"])
        self.assertNotIn("Leverage", result["dimensions"])

    def test_missing_cash_evidence_is_not_weak_cash(self):
        result = self.rate(
            metric_changes={
                "Latest_Operating_Cash_Flow": None,
                "Cash_Conversion": None,
                "Cash_Conversion_Years": 0,
                "Positive_Cash_Flow_Years": 0,
                "Negative_Cash_Flow_Years": 0,
            }
        )
        self.assertEqual(result["label"], "Limited Assessment")
        self.assertIsNone(result["score"])

    def test_missing_history_cannot_be_made_good_with_low_debt(self):
        result = self.rate({"Debt_Equity": 0}, {"Profit_History_Years": 1})
        self.assertEqual(result["label"], "Limited Assessment")

    def test_known_equity_risk_survives_missing_history(self):
        result = self.rate({"_equity": -1}, {"Profit_History_Years": 1})
        self.assertEqual(result["label"], "Very Weak")

    def test_nonpledge_encumbrance_distinct_from_large_pledge(self):
        nonpledge = self.rate({"Promoter_Encumbrance": 100})
        pledge = self.rate({"Promoter_Pledge": 50})
        self.assertEqual(nonpledge["label"], "Moderate")
        self.assertEqual(pledge["label"], "Very Weak")

    def test_premium_pe_with_profitable_growth_has_context(self):
        result = self.rate({"PE": 100})
        self.assertEqual(result["valuation"], "Premium multiple with profitable growth support")
        self.assertEqual(result["label"], "Very Strong")

    def test_premium_pe_without_growth_gets_different_valuation(self):
        result = self.rate(
            {"PE": 100},
            {
                "Revenue_Growth_YoY": -15,
                "Profit_Growth_YoY": -25,
                "Quarter_Revenue_Growth_YoY": -10,
            },
        )
        self.assertIn("without established", result["valuation"])

    def test_individual_owner_flows_do_not_establish_operating_health(self):
        good = self.rate({"FII_YoY": -10, "DII_YoY": -10, "Retail_YoY": 20})
        same = self.rate({"FII_YoY": 10, "DII_YoY": 10, "Retail_YoY": -20})
        self.assertEqual(good["label"], same["label"])

    def test_nonstandard_fiscal_period_not_fabricated_growth(self):
        h = copy.deepcopy(self.history)
        h["annual"]["2026-03-31"]["months"] = 18
        m = metrics(h)
        self.assertIsNone(m["Revenue_Growth_YoY"])
        self.assertIsNone(m["Profit_CAGR_3Y"])
        self.assertIsNone(m["Cash_Conversion"])

    def test_loss_base_not_reported_as_ordinary_profit_growth(self):
        self.assertIsNone(change(100, -50))
        self.assertIsNone(change(100, 0))

    def test_cash_and_profit_periods_must_match(self):
        h = copy.deepcopy(self.history)
        h["annual"].pop("2026-03-31")
        self.assertIsNone(metrics(h)["Cash_Conversion"])

    def test_barely_passing_growth_is_not_a_perfect_score(self):
        result = self.rate(
            metric_changes={
                "Revenue_Growth_YoY": 1,
                "Profit_Growth_YoY": 1,
                "Cash_Conversion": 0.71,
                "Interest_Coverage": 3.1,
            }
        )
        self.assertLess(result["raw_score"], 95)
        self.assertLess(result["component_scores"]["Growth"], 85)

    def test_cash_quality_affects_ranking_within_supported_profile(self):
        thin = self.rate(metric_changes={"Cash_Conversion": 0.71})
        substantial = self.rate(metric_changes={"Cash_Conversion": 1.3})
        self.assertLess(thin["raw_score"], substantial["raw_score"])

    def test_gap_in_history_not_silently_compared_to_three_year_cagr(self):
        h = copy.deepcopy(self.history)
        h["annual"].pop("2023-03-31")
        self.assertIsNone(metrics(h)["Revenue_CAGR_3Y"])


if __name__ == "__main__":
    unittest.main()
