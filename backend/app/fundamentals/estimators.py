"""Reusable financial feature transforms and ordinal/balanced classifier wrappers."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from sklearn.base import BaseEstimator, ClassifierMixin, TransformerMixin, clone
from sklearn.dummy import DummyClassifier
from sklearn.utils.class_weight import compute_sample_weight
from sklearn.utils.validation import check_is_fitted

from jobs.fundamental_context import CAPITAL_INTENSIVE


def signed_log(values: Any) -> Any:
    return np.sign(values) * np.log1p(np.abs(values))


class FinancialInteractions(TransformerMixin, BaseEstimator):  # type: ignore[misc]
    """Fixed row-wise financial calculations; no target, grades or peer-label lookups."""

    def __init__(self, view: str = "rich") -> None:
        self.view = view

    def fit(self, X: pd.DataFrame, y: Any = None) -> FinancialInteractions:
        self.feature_names_in_ = np.array(X.columns, dtype=object)
        self.n_features_in_ = len(X.columns)
        if self.view not in {"rich", "compact"}:
            raise ValueError("Unknown financial feature view")
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        check_is_fitted(self, "feature_names_in_")
        if list(X.columns) != list(self.feature_names_in_):
            raise ValueError("Financial feature schema changed")
        frame = X.copy()

        def ratio(numerator: str, denominator: str, positive_only: bool = True) -> pd.Series:
            den = frame[denominator]
            allowed = den > 0 if positive_only else den != 0
            return frame[numerator].div(den.where(allowed))

        frame["Net_Profit_Margin"] = 100 * ratio("Annual_Net_Profit", "Annual_Revenue")
        frame["Core_EBIT_Margin"] = 100 * ratio("Annual_Core_EBIT", "Annual_Revenue")
        frame["Core_PBT_Margin"] = 100 * ratio("Core_Profit_Before_Tax", "Annual_Revenue")
        frame["Profit_to_Equity"] = ratio("Annual_Net_Profit", "Equity")
        frame["Core_EBIT_to_Equity"] = ratio("Annual_Core_EBIT", "Equity")
        frame["CFO_to_Equity"] = ratio("Annual_Aligned_CFO", "Equity")
        frame["CFO_to_Debt"] = ratio("Annual_Aligned_CFO", "Borrowings")
        frame["Core_EBIT_to_Debt"] = ratio("Annual_Core_EBIT", "Borrowings")
        frame["Current_Cash_to_Profit"] = ratio("Annual_Aligned_CFO", "Annual_Net_Profit")
        frame["Sales_to_Equity"] = ratio("Annual_Revenue", "Equity")
        frame["Capital_Intensive"] = frame["Sector"].isin(CAPITAL_INTENSIVE).astype(float)
        frame["Financing_Subsidiary_Cash_Supplement"] = (
            frame["Parent_Cash_Years"].notna().astype(float)
        )
        for name, parent, consolidated in [
            ("Effective_Cash_Conversion", "Parent_Cash_Conversion", "Cash_Conversion"),
            ("Effective_Cash_Years", "Parent_Cash_Years", "Cash_Conversion_Years"),
            ("Effective_CFO", "Parent_CFO", "Latest_Operating_Cash_Flow"),
            (
                "Effective_Positive_Cash_Years",
                "Parent_Positive_Cash_Years",
                "Positive_Cash_Flow_Years",
            ),
            (
                "Effective_Negative_Cash_Years",
                "Parent_Negative_Cash_Years",
                "Negative_Cash_Flow_Years",
            ),
        ]:
            # Missing supplemental conversion stays missing when a parent supplement exists.
            has_parent = frame["Parent_Cash_Years"].notna()
            frame[name] = frame[parent].where(has_parent, frame[consolidated])
        frame["Return_Adjusted_for_Leverage"] = frame["ROCE"] / (1 + frame["Debt_Equity"])
        frame["Cash_Adjusted_for_Leverage"] = frame["Effective_Cash_Conversion"] / (
            1 + frame["Debt_Equity"]
        )
        frame["Coverage_Adjusted_for_Leverage"] = frame["Interest_Coverage"] / (
            1 + frame["Debt_Equity"]
        )
        frame["Minimum_Annual_Growth"] = frame[["Revenue_Growth_YoY", "Profit_Growth_YoY"]].min(
            axis=1, skipna=False
        )
        frame["Minimum_Quarter_Core_Growth"] = frame[
            ["Quarter_Revenue_Growth_YoY", "Quarter_Operating_Profit_Growth_YoY"]
        ].min(axis=1, skipna=False)
        frame["Profit_Minus_Revenue_Growth"] = (
            frame["Profit_Growth_YoY"] - frame["Revenue_Growth_YoY"]
        )
        frame["Cash_Return_Product"] = frame["Effective_Cash_Conversion"] * frame["ROCE"]
        frame["Cash_Growth_Product"] = (
            frame["Effective_Cash_Conversion"] * frame["Minimum_Annual_Growth"]
        )
        frame["Profitable_History_Fraction"] = ratio("Profitable_Years_3Y", "Profit_History_Years")
        frame["Positive_Cash_History_Fraction"] = ratio(
            "Effective_Positive_Cash_Years", "Effective_Cash_Years"
        )
        for col in [
            "Net_Profit",
            "Annual_Net_Profit",
            "Latest_Quarter_Profit",
            "Core_EBIT",
            "Core_Profit_Before_Tax",
            "Equity",
            "Effective_CFO",
        ]:
            frame[col + "_Positive"] = (frame[col] > 0).astype(float).where(frame[col].notna())
        frame["No_Interest_Expense"] = (
            (frame["Interest_Expense"] == 0).astype(float).where(frame["Interest_Expense"].notna())
        )
        frame["No_Borrowings"] = (
            (frame["Borrowings"] == 0).astype(float).where(frame["Borrowings"].notna())
        )
        if self.view == "compact":
            core = [
                "Sector",
                "Broad_Industry",
                "Debt_Equity",
                "OPM",
                "ROCE",
                "Promoter_Pledge",
                "Promoter_YoY",
                "Promoter_Encumbrance",
                "Encumbrance_Total_Capital",
                "Interest_Coverage",
                "Interest_Expense",
                "Debt_EBITDA",
                "Debt_Equity_Change_YoY",
                "Margin_Change_YoY_PP",
                "ROCE_Change_YoY_PP",
                "Revenue_Growth_YoY",
                "Profit_Growth_YoY",
                "Operating_Profit_Growth_YoY",
                "Quarter_Revenue_Growth_YoY",
                "Quarter_Operating_Profit_Growth_YoY",
                "Revenue_CAGR_3Y",
                "Profit_CAGR_3Y",
                "Profit_History_Years",
                "Loss_Years_3Y",
            ]
            derived = [c for c in frame if c not in X]
            frame = frame[core + derived]
        numeric = frame.columns.difference(["Sector", "Broad_Industry"])
        frame[numeric] = frame[numeric].replace([np.inf, -np.inf], np.nan)
        return frame


class BalancedClassifier(ClassifierMixin, BaseEstimator):  # type: ignore[misc]
    """Calculate class balancing within every actual fit, including inner CV folds."""

    def __init__(self, estimator: Any, balance: bool = True) -> None:
        self.estimator = estimator
        self.balance = balance

    def fit(self, X: Any, y: Any) -> BalancedClassifier:
        self.estimator_ = clone(self.estimator)
        weights = compute_sample_weight("balanced", y) if self.balance else None
        self.estimator_.fit(X, y, sample_weight=weights)
        self.classes_ = self.estimator_.classes_
        self.n_features_in_ = X.shape[1]
        return self

    def predict(self, X: Any) -> Any:
        check_is_fitted(self, "estimator_")
        return self.estimator_.predict(X)

    def predict_proba(self, X: Any) -> Any:
        check_is_fitted(self, "estimator_")
        return self.estimator_.predict_proba(X)


class OrdinalClassifier(ClassifierMixin, BaseEstimator):  # type: ignore[misc]
    """Learn four cumulative label boundaries without using the fundamental score."""

    def __init__(self, estimator: Any, balance: bool = False) -> None:
        self.estimator = estimator
        self.balance = balance

    def fit(self, X: Any, y: Any) -> OrdinalClassifier:
        y = np.asarray(y)
        if not np.isin(y, np.arange(5)).all():
            raise ValueError("Ordinal labels must use the five fixed codes 0..4")
        self.classes_ = np.arange(5)
        self.n_features_in_ = X.shape[1]
        self.estimators_ = []
        for threshold in range(4):
            binary = (y > threshold).astype(int)
            estimator = (
                clone(self.estimator)
                if len(np.unique(binary)) == 2
                else DummyClassifier(strategy="constant", constant=int(binary[0]))
            )
            weights = compute_sample_weight("balanced", binary) if self.balance else None
            estimator.fit(X, binary, sample_weight=weights)
            self.estimators_.append(estimator)
        return self

    def predict_proba(self, X: Any) -> np.ndarray:
        check_is_fitted(self, "estimators_")
        cumulative = []
        for estimator in self.estimators_:
            values = estimator.predict_proba(X)
            index = list(estimator.classes_).index(1) if 1 in estimator.classes_ else None
            cumulative.append(values[:, index] if index is not None else np.zeros(len(X)))
        probabilities = np.minimum.accumulate(np.clip(np.column_stack(cumulative), 0, 1), axis=1)
        return np.column_stack(
            [
                1 - probabilities[:, 0],
                probabilities[:, :-1] - probabilities[:, 1:],
                probabilities[:, -1],
            ]
        )

    def predict(self, X: Any) -> np.ndarray:
        return np.argmax(self.predict_proba(X), axis=1)


class OrdinalRegressionClassifier(ClassifierMixin, BaseEstimator):  # type: ignore[misc]
    """Regress the five ordered label codes, then round to a label; no score input."""

    def __init__(self, estimator: Any, balance: bool = False) -> None:
        self.estimator = estimator
        self.balance = balance

    def fit(self, X: Any, y: Any) -> OrdinalRegressionClassifier:
        y = np.asarray(y)
        if not np.isin(y, np.arange(5)).all():
            raise ValueError("Ordinal labels must use the five fixed codes 0..4")
        self.classes_ = np.arange(5)
        self.n_features_in_ = X.shape[1]
        self.estimator_ = clone(self.estimator)
        weights = compute_sample_weight("balanced", y) if self.balance else None
        self.estimator_.fit(X, y, sample_weight=weights)
        return self

    def predict(self, X: Any) -> np.ndarray:
        check_is_fitted(self, "estimator_")
        # Do not manufacture probabilities from a regressor's continuous output.
        values = np.asarray(self.estimator_.predict(X), dtype=float)
        return np.clip(np.floor(values + 0.5), 0, 4).astype(int)
