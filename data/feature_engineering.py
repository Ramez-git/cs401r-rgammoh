"""Customer features shared by the Glue job and local CI tests."""
from functools import reduce

import numpy as np
import pandas as pd

FEATURE_CUTOFF = "2026-04-01"
SNAPSHOT = "2026-06-30"
FEATURE_COLUMNS = [
    "days_since_last_purchase", "customer_tenure_days",
    "purchase_frequency_30d", "purchase_frequency_90d", "purchase_frequency_180d",
    "avg_order_value", "total_spend_90d", "total_lifetime_value",
    "avg_basket_size_6m", "category_diversity_score", "online_to_store_ratio",
]


def _history(transactions, snapshot_date):
    frame = transactions.copy()
    frame["purchase_date"] = pd.to_datetime(frame["purchase_date"]).dt.normalize()
    return frame.loc[frame.purchase_date <= pd.Timestamp(snapshot_date)].copy()


def _roster(transactions, customer_ids=None):
    source = transactions if customer_ids is None else customer_ids
    return source[["customer_id"]].drop_duplicates().set_index("customer_id")


def compute_recency_features(transactions, snapshot_date, customer_ids=None):
    history = _history(transactions, snapshot_date)
    dates = history.groupby("customer_id").purchase_date.agg(["min", "max"])
    result = _roster(transactions, customer_ids).join(dates)
    result["days_since_last_purchase"] = (
        pd.Timestamp(snapshot_date) - pd.to_datetime(result["max"])
    ).dt.days.fillna(999)
    result["customer_tenure_days"] = (
        pd.Timestamp(snapshot_date) - pd.to_datetime(result["min"])
    ).dt.days.fillna(0)
    return result.drop(columns=["min", "max"]).reset_index()


def compute_frequency_features(transactions, snapshot_date, customer_ids=None):
    history = _history(transactions, snapshot_date)
    result = _roster(transactions, customer_ids)
    for days in (30, 90, 180):
        recent = history.purchase_date > pd.Timestamp(snapshot_date) - pd.Timedelta(days=days)
        result[f"purchase_frequency_{days}d"] = (
            history.loc[recent].groupby("customer_id").size().reindex(result.index, fill_value=0)
        )
    return result.reset_index()


def compute_monetary_features(transactions, snapshot_date, customer_ids=None):
    history = _history(transactions, snapshot_date)
    result = _roster(transactions, customer_ids)
    grouped = history.groupby("customer_id")
    result["avg_order_value"] = grouped.order_value.mean()
    result["total_lifetime_value"] = grouped.order_value.sum()
    recent90 = history.purchase_date > pd.Timestamp(snapshot_date) - pd.Timedelta(days=90)
    recent180 = history.purchase_date > pd.Timestamp(snapshot_date) - pd.Timedelta(days=180)
    result["total_spend_90d"] = history.loc[recent90].groupby("customer_id").order_value.sum()
    result["avg_basket_size_6m"] = history.loc[recent180].groupby("customer_id").num_items.mean()
    return result.fillna(0).reset_index()


def compute_behavioral_features(transactions, snapshot_date=FEATURE_CUTOFF, customer_ids=None):
    history = _history(transactions, snapshot_date)
    result = _roster(transactions, customer_ids)
    known = history.loc[history.product_category.notna() & history.product_category.ne("unknown")]
    result["category_diversity_score"] = known.groupby("customer_id").product_category.nunique() / 8
    history["_online"] = history.channel.eq("online").astype(float)
    result["online_to_store_ratio"] = history.groupby("customer_id")._online.mean()
    return result.fillna(0).reset_index()


def compute_feature_table(transactions, snapshot_date=FEATURE_CUTOFF, customer_ids=None):
    functions = [compute_recency_features, compute_frequency_features,
                 compute_monetary_features, compute_behavioral_features]
    parts = [f(transactions, snapshot_date, customer_ids) for f in functions]
    result = reduce(lambda left, right: left.merge(right, on="customer_id", validate="one_to_one"), parts)
    result[FEATURE_COLUMNS] = result[FEATURE_COLUMNS].astype(float)
    return result[["customer_id"] + FEATURE_COLUMNS]


def build_churn_feature_set(customers, transactions, snapshot_date=FEATURE_CUTOFF):
    features = compute_feature_table(transactions, snapshot_date, customers)
    features["loyalty_tier"] = np.select(
        [features.total_lifetime_value < 500, features.total_lifetime_value < 2000,
         features.total_lifetime_value < 5000],
        ["Bronze", "Silver", "Gold"], default="Platinum",
    )
    dates = pd.to_datetime(transactions.purchase_date).dt.normalize()
    holdout = transactions.loc[(dates > pd.Timestamp(snapshot_date)) & (dates <= pd.Timestamp(SNAPSHOT))]
    features["churn_label"] = (~features.customer_id.isin(holdout.customer_id)).astype(int)
    return features
