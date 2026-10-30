"""Slice evidence is mandatory; a disparity flags review without blocking."""
import json
import os
from pathlib import Path
import warnings

import numpy as np
import pytest


@pytest.fixture(scope="module")
def slice_metrics():
    path = Path(os.environ.get("EVAL_METRICS_PATH", "/tmp/eval_metrics.json"))
    assert path.is_file(), f"Missing evaluation metrics: {path}"
    return json.loads(path.read_text())


def test_all_loyalty_tiers_have_valid_evaluation(slice_metrics):
    slices = slice_metrics["slice_results"]
    assert set(slices) == {"Bronze", "Silver", "Gold", "Platinum"}
    assert sum(s["n"] for s in slices.values()) == slice_metrics["n_val_samples"]
    for result in slices.values():
        assert result["n"] >= result["positives"] > 0
        assert np.isfinite(result["recall"]) and 0 <= result["recall"] <= 1
        assert result["recall"] == pytest.approx(result["true_positives"] / result["positives"])


def test_recall_gap_is_reported_for_approval(slice_metrics):
    recalls = {tier: result["recall"] for tier, result in slice_metrics["slice_results"].items()}
    gap = max(recalls.values()) - min(recalls.values())
    assert slice_metrics["fairness_recall_gap"] == pytest.approx(gap)
    if gap > .10:
        warnings.warn(f"FAIRNESS REVIEW: loyalty-tier recall gap {gap:.1%} exceeds 10 percentage points; {recalls}")
