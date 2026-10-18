"""Focused tests for evaluation correctness and leakage boundaries."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from churn_training_skeleton import top_mask, bootstrap_lift_ci, FEATURE_COLUMNS

class EvaluationTests(unittest.TestCase):
    def test_ties_do_not_expand_budget(self):
        mask = top_mask(np.ones(100))
        self.assertEqual(int(mask.sum()), 10)
        self.assertTrue(mask[:10].all())
    def test_paired_identical_models_have_zero_lift(self):
        y = np.array([0, 1] * 50)
        scores = np.linspace(0, 1, 100)
        self.assertEqual(bootstrap_lift_ci(y, scores, scores, n=100), [0., 0.])
    def test_strong_signal_has_positive_interval(self):
        y = np.array([0, 1] * 100)
        low, high = bootstrap_lift_ci(y, y.astype(float), np.ones(200)*.5, n=100)
        self.assertGreater(low, 0)
    def test_leakage_columns_excluded(self):
        self.assertFalse(set(FEATURE_COLUMNS) & {'customer_id', 'churn_label', 'churn_risk_score', 'event_time', 'loyalty_tier'})

if __name__ == '__main__':
    unittest.main()
