"""Regression tests for experiments/stats_utils.py.

The headline guard (test_clean_separation_hits_floor_not_zero) pins the bug
fixed in E1: a two-sided paired permutation test can NEVER return p=0; its floor
is 2/2**n. A clean, large, uniformly-signed separation must land exactly on that
floor, not below it. Before the tolerance fix, float-order divergence between
`observed` and the per-mask statistic dropped the identity/all-flip permutations
and returned an impossible p=0.0.
"""

import unittest

from experiments.stats_utils import (
    paired_permutation_test, cohens_d_paired, SEEDS,
)


class TestPairedPermutationFloor(unittest.TestCase):
    def test_clean_separation_hits_floor_not_zero(self):
        # 10 paired samples, a is uniformly and substantially above b — exactly
        # the E1 clean-regime composed-vs-siloed shape that triggered the bug.
        a = [0.99, 0.98, 0.97, 0.99, 1.00, 0.96, 0.98, 0.99, 0.97, 0.98]
        b = [0.27, 0.25, 0.26, 0.28, 0.24, 0.27, 0.26, 0.25, 0.27, 0.26]
        n = len(a)
        floor = 2 / (2 ** n)
        observed, p = paired_permutation_test(a, b)
        self.assertGreater(observed, 0.0)
        self.assertNotEqual(p, 0.0)               # impossible for a two-sided test
        self.assertGreaterEqual(p, floor)         # never below the analytic floor
        self.assertAlmostEqual(p, floor)          # maximal separation => floor exactly

    def test_floor_value_matches_paper(self):
        # n=10 floor is the 0.001953125 the manuscript cites (2/2**10).
        self.assertAlmostEqual(2 / (2 ** 10), 0.001953125)
        self.assertEqual(len(SEEDS), 10)

    def test_no_difference_gives_p_one(self):
        x = [0.5, 0.6, 0.4, 0.55, 0.45]
        observed, p = paired_permutation_test(x, x)
        self.assertEqual(observed, 0.0)
        self.assertEqual(p, 1.0)

    def test_p_never_zero_across_many_clean_gaps(self):
        # Any uniformly-signed gap, however large, must still report >= floor.
        for gap in (0.5, 0.7, 0.9, 5.0, 100.0):
            a = [gap + i * 1e-3 for i in range(10)]
            b = [0.0 for _ in range(10)]
            _, p = paired_permutation_test(a, b)
            self.assertGreater(p, 0.0, f"gap={gap} returned p=0")
            self.assertGreaterEqual(p, 2 / (2 ** 10))

    def test_cohens_d_large_for_clean_gap(self):
        a = [0.99, 0.98, 0.97, 0.99, 1.00, 0.96, 0.98, 0.99, 0.97, 0.98]
        b = [0.27, 0.25, 0.26, 0.28, 0.24, 0.27, 0.26, 0.25, 0.27, 0.26]
        d = cohens_d_paired(a, b)
        self.assertGreater(d, 5.0)


if __name__ == "__main__":
    unittest.main()
