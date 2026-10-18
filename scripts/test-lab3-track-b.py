"""Tests for policy grounding and profile boundaries, without AWS calls."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rag.offer_pipeline import OfferRAG, chunks_from_corpus, ROOT

class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.chunks=chunks_from_corpus(ROOT/'northstar-policy-docs')
        self.profile={'loyalty_tier':'Gold','top_categories':['Outdoor'],'churn_probability':.8}
    def test_chunks_are_stable_and_identifiable(self):
        self.assertEqual(self.chunks,chunks_from_corpus(ROOT/'northstar-policy-docs'))
        self.assertEqual(len(self.chunks),len({c['id'] for c in self.chunks}))
        self.assertTrue(all(len(c['text'].split()) <= 240 for c in self.chunks))
    def test_unknown_categories_are_rejected(self):
        with self.assertRaises(ValueError):
            OfferRAG.validate_profile(self.profile | {'top_categories':['Luxury Cars']})
    def test_unknown_tier_is_rejected(self):
        with self.assertRaises(ValueError):
            OfferRAG.validate_profile(self.profile | {'loyalty_tier':'Diamond'})
    def test_no_evidence_means_no_benefit_promise(self):
        self.assertNotIn('1.5',OfferRAG.approved_incentive(self.profile,[]))
    def test_rate_is_parsed_and_eligibility_is_conditional(self):
        sentence=OfferRAG.approved_incentive(self.profile,self.chunks)
        self.assertIn('If your account confirms Gold status',sentence)
        self.assertIn('1.5 points per $1',sentence)
    def test_lifetime_value_cannot_upgrade_silver(self):
        sentence=OfferRAG.approved_incentive(self.profile | {'loyalty_tier':'Silver','total_lifetime_value':1985},self.chunks)
        self.assertIn('Silver',sentence)
        self.assertNotIn('Gold',sentence)
        self.assertIn('1.25 points',sentence)
    def test_generated_policy_claims_are_rejected(self):
        errors=OfferRAG.validate_copy({'recommendation':'Explore Outdoor with free expedited shipping.','call_to_action':'Browse our selection.'},self.profile)
        self.assertTrue(errors)
    def test_neutral_copy_is_accepted(self):
        self.assertFalse(OfferRAG.validate_copy({'recommendation':'Explore our Outdoor category.','call_to_action':'Browse the selection and check your account.'},self.profile))

if __name__ == '__main__':
    unittest.main()
