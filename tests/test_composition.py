#!/usr/bin/env python3
"""Tests for the cross-system attribute partition (trkg/composition.py).

The decisive test is the validity invariant shared by E1-siloed and
E5-decomposed: under full T-RKG reasoning, the decomposed view must yield zero
cross-domain conflicts, while the composed view yields a positive number.
"""

import unittest
from datetime import datetime

from trkg import (
    Record, RecordType, Jurisdiction, Regulation,
    ConflictDetector, generate_test_dataset,
)
from trkg.composition import (
    siloed_view, assert_no_cross_system_triggers, decompose_records,
    ATTRIBUTE_HOME_SYSTEM,
)


def _cross_domain(by_type) -> int:
    return (by_type.get("RETENTION_DELETION", 0)
            + by_type.get("JURISDICTION", 0)
            + by_type.get("HOLD_DELETION", 0))


class TestSiloedView(unittest.TestCase):
    def _rec(self, system_id, **kw):
        base = dict(
            id="r", type=RecordType.FINANCIAL, title="t",
            created=datetime(2023, 1, 1), modified=datetime(2023, 1, 1),
            system_id=system_id,
        )
        base.update(kw)
        return Record(**base)

    def test_pii_masked_for_non_crm_record(self):
        rec = self._rec("sys_erp", contains_pii=True, jurisdiction=Jurisdiction.EU)
        view = siloed_view(rec)
        self.assertFalse(view.contains_pii)
        # Original is untouched (no mutation).
        self.assertTrue(rec.contains_pii)

    def test_pii_kept_for_crm_record(self):
        rec = self._rec("sys_crm", type=RecordType.TICKET,
                        contains_pii=True, jurisdiction=Jurisdiction.EU)
        view = siloed_view(rec)
        self.assertTrue(view.contains_pii)

    def test_public_company_kept_for_erp_removed_for_email(self):
        fin = self._rec("sys_erp", metadata={"is_public_company": True})
        self.assertTrue(siloed_view(fin).metadata.get("is_public_company"))

        email = self._rec("sys_email", type=RecordType.EMAIL,
                          metadata={"is_public_company": True})
        self.assertNotIn("is_public_company", siloed_view(email).metadata)

    def test_jurisdiction_never_masked(self):
        rec = self._rec("sys_erp", jurisdiction=Jurisdiction.EU_DE)
        self.assertEqual(siloed_view(rec).jurisdiction, Jurisdiction.EU_DE)

    def test_assert_no_cross_system_triggers_passes_on_view(self):
        rec = self._rec("sys_erp", contains_pii=True, contains_phi=True,
                        metadata={"is_public_company": True})
        assert_no_cross_system_triggers(siloed_view(rec))  # no raise

    def test_assert_detects_leak(self):
        # Hand-build a leaking "view": ERP record that still exposes PII (CRM-owned).
        leaking = self._rec("sys_erp", contains_pii=True)
        with self.assertRaises(AssertionError):
            assert_no_cross_system_triggers(leaking)

    def test_attribute_map_is_documented(self):
        self.assertEqual(ATTRIBUTE_HOME_SYSTEM["contains_pii"], "sys_crm")
        self.assertEqual(ATTRIBUTE_HOME_SYSTEM["is_public_company"], "sys_erp")


class TestDecompositionInvariant(unittest.TestCase):
    """The composition claim, made empirical: decomposition kills cross-domain."""

    def setUp(self):
        self.detector = ConflictDetector()
        self.store = generate_test_dataset(num_records=5000, seed=42)

    def test_composed_has_cross_domain_but_decomposed_has_none(self):
        composed = self.detector.detect_all_conflicts(self.store.records)
        composed_xdom = _cross_domain(composed.conflicts_by_type)
        self.assertGreater(composed_xdom, 0,
                           "composed view should surface cross-domain conflicts")

        decomposed_records = decompose_records(self.store.records)
        decomposed = self.detector.detect_all_conflicts(decomposed_records)
        decomposed_xdom = _cross_domain(decomposed.conflicts_by_type)
        self.assertEqual(decomposed_xdom, 0,
                         "decomposed view must have zero cross-domain conflicts; "
                         "a non-zero value means the partition leaks")

    def test_every_decomposed_view_passes_leak_assertion(self):
        for rec in decompose_records(self.store.records).values():
            assert_no_cross_system_triggers(rec)


if __name__ == "__main__":
    unittest.main()
