"""Lab 3's selected model behind the Lab 4 training contract."""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

FEATURE_COLUMNS = [
    "days_since_last_purchase", "customer_tenure_days",
    "purchase_frequency_30d", "purchase_frequency_90d", "purchase_frequency_180d",
    "avg_order_value", "total_spend_90d", "total_lifetime_value",
    "avg_basket_size_6m", "category_diversity_score", "online_to_store_ratio",
]
LABEL = "churn_label"


def top_mask(scores):
    count = max(1, math.ceil(len(scores) * .10))
    selected = np.zeros(len(scores), dtype=bool)
    selected[np.argsort(-scores, kind="stable")[:count]] = True
    return selected


def bootstrap_lift_ci(y, scores, baseline, n=2000, seed=42):
    rng, differences = np.random.default_rng(seed), []
    for _ in range(n):
        indices = rng.integers(0, len(y), len(y))
        if np.unique(y[indices]).size == 2:
            differences.append(roc_auc_score(y[indices], scores[indices])
                               - roc_auc_score(y[indices], baseline[indices]))
    if len(differences) < n * .9:
        raise ValueError("Insufficient two-class bootstrap replicates")
    return np.quantile(differences, [.025, .975]).tolist()


def evaluate_model(evaluation, scores, baseline, seed):
    y = evaluation[LABEL].to_numpy(dtype=int)
    selected = top_mask(scores)
    low, high = bootstrap_lift_ci(y, scores, baseline, seed=seed)
    auc, base_auc = roc_auc_score(y, scores), roc_auc_score(y, baseline)
    metrics = {
        "auc_roc": float(auc), "baseline_auc": float(base_auc),
        "baseline_auc_roc": float(base_auc), "auc_vs_baseline": float(auc - base_auc),
        "precision_top10": float(y[selected].mean()),
        "recall_top10": float(y[selected].sum() / y.sum()),
        "lift_ci_low": float(low), "lift_ci_high": float(high),
        "positive_rate_val": float(y.mean()), "n_val_samples": len(y),
        "n_targeted": int(selected.sum()),
    }
    slices = {}
    for tier in ["Bronze", "Silver", "Gold", "Platinum"]:
        mask = evaluation.loyalty_tier.to_numpy() == tier
        count, positives = int(mask.sum()), int(y[mask].sum())
        slices[tier] = {
            "n": count, "positives": positives,
            "true_positives": int(y[mask & selected].sum()),
            "recall": float(y[mask & selected].sum() / positives) if positives else None,
            "auc": float(roc_auc_score(y[mask], scores[mask])) if 0 < positives < count else None,
            "too_small": count < 100 or min(positives, count - positives) < 20,
        }
    recalls = [s["recall"] for s in slices.values() if s["recall"] is not None]
    metrics.update(slice_results=slices, fairness_recall_gap=float(max(recalls) - min(recalls)))
    if metrics["precision_top10"] < .50 or metrics["recall_top10"] < .25 or low <= 0:
        raise ValueError(f"Training quality gates failed: {metrics}")
    return metrics


def train(df: pd.DataFrame, seed: int = 42):
    required = ["customer_id", "loyalty_tier", LABEL] + FEATURE_COLUMNS
    missing = sorted(set(required) - set(df.columns))
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    frame = df.copy().sort_values("customer_id").reset_index(drop=True)
    if frame.empty or frame.customer_id.isna().any() or frame.customer_id.duplicated().any():
        raise ValueError("Training requires unique, non-null customer IDs")
    if frame[LABEL].isna().any() or set(frame[LABEL].unique()) != {0, 1}:
        raise ValueError("Labels must contain both binary classes")
    if frame.loyalty_tier.isna().any():
        raise ValueError("Missing loyalty tier")
    frame[FEATURE_COLUMNS] = frame[FEATURE_COLUMNS].apply(pd.to_numeric, errors="raise")
    if np.isinf(frame[FEATURE_COLUMNS].to_numpy(dtype=float)).any():
        raise ValueError("Infinite feature value")
    fit, evaluation = train_test_split(frame, test_size=.30, random_state=seed, stratify=frame[LABEL])
    fit, evaluation = fit.sort_values("customer_id"), evaluation.sort_values("customer_id")
    weight = float((fit[LABEL] == 0).sum() / (fit[LABEL] == 1).sum())
    params = dict(objective="binary:logistic", eval_metric=["logloss", "auc"],
                  max_depth=3, eta=.05, min_child_weight=5, subsample=.8,
                  colsample_bytree=.8, scale_pos_weight=weight, seed=seed, nthread=4)
    model = xgb.train(params, xgb.DMatrix(fit[FEATURE_COLUMNS], label=fit[LABEL]), num_boost_round=154)
    baseline_params = dict(params, max_depth=4, eta=.1, subsample=.9, colsample_bytree=.9)
    baseline = xgb.train(baseline_params,
                        xgb.DMatrix(fit[["days_since_last_purchase"]], label=fit[LABEL]),
                        num_boost_round=200)
    scores = model.predict(xgb.DMatrix(evaluation[FEATURE_COLUMNS]))
    baseline_scores = baseline.predict(xgb.DMatrix(evaluation[["days_since_last_purchase"]]))
    metrics = evaluate_model(evaluation, scores, baseline_scores, seed)
    metrics.update(n_train_samples=len(fit), selected_rounds=154, split_seed=seed,
                   xgboost_version=xgb.__version__)
    if "event_time" in frame:
        metrics["data_event_time"] = float(pd.to_numeric(frame.event_time).max())
    return model, metrics
