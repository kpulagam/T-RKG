#!/usr/bin/env python3
"""Tests for E5 (experiments/e5_composition.py), the composition ablation.

Run on a small dataset / two seeds so the suite stays fast. The decisive
properties checked here are the same ones the paper rests on:
  * the decomposed view yields zero cross-domain conflicts,
  * the composed view yields a positive number,
  * decomposition cannot *increase* applicability recall,
  * the output JSON carries the per-seed arrays and paired statistics.
"""

import unittest

from experiments import e5_composition as e5


class TestE5Run(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Two seeds, a corpus large enough that the (EU ∩ PII ∩ public-company
        # financial) retention-deletion population is reliably non-empty.
        cls.out = e5.run(seeds=[42, 123], num_records=5000)

    def test_structure(self):
        for key in ("experiment", "per_seed", "aggregates", "paired_tests"):
            self.assertIn(key, self.out)
        self.assertEqual(self.out["experiment"], "E5")
        self.assertEqual(self.out["n_seeds"], 2)

    def test_decomposed_has_zero_cross_domain(self):
        self.assertTrue(all(v == 0 for v in self.out["per_seed"]["decomposed_xdom"]),
                        "decomposition must eliminate cross-domain conflicts")

    def test_composed_has_cross_domain(self):
        self.assertGreater(sum(self.out["per_seed"]["composed_xdom"]), 0,
                           "composed view should surface cross-domain conflicts")

    def test_decomposition_does_not_raise_recall(self):
        for c, d in zip(self.out["per_seed"]["composed_recall"],
                        self.out["per_seed"]["decomposed_recall"]):
            self.assertGreaterEqual(c + 1e-9, d)

    def test_paired_tests_present(self):
        for key in ("total_conflicts", "cross_domain", "applicability_f1"):
            t = self.out["paired_tests"][key]
            self.assertIn("p_value", t)
            self.assertIn("cohens_d", t)
            self.assertIn("observed_mean_diff", t)

    def test_cross_domain_diff_is_positive(self):
        # Composed minus decomposed cross-domain must be > 0 on average.
        self.assertGreater(
            self.out["paired_tests"]["cross_domain"]["observed_mean_diff"], 0)


if __name__ == "__main__":
    unittest.main()
