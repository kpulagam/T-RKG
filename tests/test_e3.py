#!/usr/bin/env python3
"""Tests for E3, the multi-jurisdiction balanced preset.

These tests pin down the three properties the paper's §VIII-E "limitation
closed" claim rests on:

  * The DEFAULT generator emits ZERO records with a non-empty
    additional_jurisdictions, so existing datasets/results are untouched
    (the multi-jurisdiction overlay is strictly additive / opt-in).
  * The balanced preset actually populates the overlay.
  * On a genuine dual-jurisdiction record, the JURISDICTION family is
    *verified, not just enabled*: both GDPR-CPRA and GDPR-PIPEDA fire.
  * The GDPR Art. 17(3) defeasibility (Axiom 4) suppresses a HOLD_DELETION
    conflict when, and only when, the holding matter carries an exemption.
"""

import unittest
from datetime import datetime

from trkg.synthetic import (
    GeneratorConfig, SyntheticDataGenerator, balanced_config,
    generate_test_dataset,
)
from trkg.schema import Record, RecordType, Jurisdiction, Matter
from trkg.conflict import ConflictDetector, Regulation, ConflictType


def _record(**kw):
    base = dict(
        id="r_test", type=RecordType.EMAIL, title="t",
        created=datetime(2021, 1, 1), modified=datetime(2021, 1, 2),
    )
    base.update(kw)
    return Record(**base)


class TestDefaultIsInert(unittest.TestCase):
    def test_default_preset_emits_zero_multijurisdiction(self):
        store = generate_test_dataset(num_records=3000, seed=42)
        offenders = [r.id for r in store.records.values()
                     if r.additional_jurisdictions]
        self.assertEqual(
            offenders, [],
            "default generator must emit zero records with a non-empty "
            "additional_jurisdictions (overlay is opt-in)")

    def test_default_config_probability_is_zero(self):
        self.assertEqual(GeneratorConfig().multi_jurisdiction_probability, 0.0)


class TestBalancedPreset(unittest.TestCase):
    def test_balanced_preset_emits_multijurisdiction(self):
        cfg = balanced_config(num_records=3000)
        self.assertGreater(cfg.multi_jurisdiction_probability, 0.0)
        store = SyntheticDataGenerator(cfg, seed=42).generate()
        multi = [r for r in store.records.values() if r.additional_jurisdictions]
        self.assertGreater(len(multi), 0,
                           "balanced preset must populate the overlay")
        # Every overlaid record is an EU PII record (the dual-privacy setup).
        for r in multi:
            self.assertEqual(r.jurisdiction, Jurisdiction.EU)
            self.assertTrue(r.contains_pii)


class TestJurisdictionFamilyFires(unittest.TestCase):
    """The family must be verified, not merely enabled."""

    def setUp(self):
        self.det = ConflictDetector()

    def test_gdpr_cpra_and_pipeda_fire_on_dual_jurisdiction(self):
        rec = _record(
            jurisdiction=Jurisdiction.EU,
            additional_jurisdictions=[Jurisdiction.US_CA, Jurisdiction.CA],
            contains_pii=True,
        )
        applicable = self.det.infer_applicable_regulations(rec)
        for reg in (Regulation.GDPR, Regulation.CPRA, Regulation.PIPEDA):
            self.assertIn(reg, applicable, f"{reg} should apply")

        conflicts = self.det.detect_conflicts_for_record(rec)
        pairs = {frozenset((c.regulation_a, c.regulation_b)) for c in conflicts
                 if c.conflict_type == ConflictType.JURISDICTION}
        self.assertIn(frozenset((Regulation.GDPR, Regulation.CPRA)), pairs,
                      "GDPR-CPRA JURISDICTION conflict must fire")
        self.assertIn(frozenset((Regulation.GDPR, Regulation.PIPEDA)), pairs,
                      "GDPR-PIPEDA JURISDICTION conflict must fire")

    def test_no_jurisdiction_conflict_without_overlay(self):
        # EU-only PII record: GDPR applies, but neither CPRA nor PIPEDA, so the
        # JURISDICTION family is silent. Confirms the overlay is what fires it.
        rec = _record(jurisdiction=Jurisdiction.EU, contains_pii=True)
        conflicts = self.det.detect_conflicts_for_record(rec)
        juris = [c for c in conflicts
                 if c.conflict_type == ConflictType.JURISDICTION]
        self.assertEqual(juris, [])


class TestAxiom4Suppression(unittest.TestCase):
    """GDPR Art. 17(3) defeasibility on HOLD_DELETION."""

    def _hold_conflicts(self, exemption: bool):
        matter = Matter(
            id="matter_x", name="M", hold_start=datetime(2024, 1, 1),
            is_active=True,
            legal_obligation_flag=exemption,
        )
        det = ConflictDetector(matters={"matter_x": matter})
        rec = _record(
            jurisdiction=Jurisdiction.EU, contains_pii=True,
            hold_matters=["matter_x"],
        )
        return det.detect_conflicts_for_record(
            rec, active_holds=["matter_x"]), det

    def test_hold_deletion_fires_without_exemption(self):
        conflicts, _ = self._hold_conflicts(exemption=False)
        hold = [c for c in conflicts
                if c.conflict_type == ConflictType.HOLD_DELETION]
        self.assertTrue(hold, "GDPR hold-deletion must fire without exemption")

    def test_axiom4_suppresses_hold_deletion_with_exemption(self):
        conflicts, det = self._hold_conflicts(exemption=True)
        hold = [c for c in conflicts
                if c.conflict_type == ConflictType.HOLD_DELETION]
        self.assertEqual(hold, [],
                         "Art. 17(3) exemption must suppress the conflict")
        self.assertEqual(det.suppressed_exemption_count, 1)


if __name__ == "__main__":
    unittest.main()
