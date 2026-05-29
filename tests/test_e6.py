"""Tests for E6, the SHACL-SPARQL baseline.

These exercise the three families SHACL Core cannot reach but SHACL-SPARQL can
(RETENTION_DELETION, HOLD_DELETION with Art. 17(3) defeasibility, JURISDICTION),
confirm the two still-impossible families are declared, and check that the E6
driver returns the expected structure on a small scale. Crafted ABoxes are kept
tiny because pyshacl with sh:sparql constraints is slow.
"""

import unittest
from datetime import datetime

from trkg.schema import Record, RecordType, Jurisdiction, Matter
from trkg.baselines.shacl_sparql_baseline import ShaclSparqlBaseline
from experiments import e6_shacl_sparql as e6


def _rec(rid, **kw):
    base = dict(id=rid, type=RecordType.EMAIL, title=rid,
                created=datetime(2021, 1, 1), modified=datetime(2021, 1, 2))
    base.update(kw)
    return Record(**base)


class TestShaclSparqlFamilies(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = ShaclSparqlBaseline()

    def test_retention_deletion_fires(self):
        rec = _rec("ret1", contains_pii=True, jurisdiction=Jurisdiction.EU_DE,
                   metadata={"is_public_company": True})
        res = self.b.detect_all_conflicts({rec.id: rec})
        self.assertIn("ret1", res.flagged_by_family["RETENTION_DELETION"])

    def test_jurisdiction_fires_on_dual_regime(self):
        rec = _rec("jur1", contains_pii=True, jurisdiction=Jurisdiction.EU,
                   additional_jurisdictions=[Jurisdiction.US_CA])
        res = self.b.detect_all_conflicts({rec.id: rec})
        self.assertIn("jur1", res.flagged_by_family["JURISDICTION"])

    def test_hold_deletion_fires_without_exemption(self):
        m = Matter(id="m_plain", name="M", legal_obligation_flag=False,
                   legal_claim_flag=False)
        rec = _rec("hd1", contains_pii=True, jurisdiction=Jurisdiction.EU,
                   hold_matters=["m_plain"])
        res = self.b.detect_all_conflicts({rec.id: rec}, {"m_plain": m})
        self.assertIn("hd1", res.flagged_by_family["HOLD_DELETION"])

    def test_art17_3_defeasibility_suppresses_hold_deletion(self):
        m = Matter(id="m_exempt", name="M", legal_obligation_flag=True)
        rec = _rec("hd2", contains_pii=True, jurisdiction=Jurisdiction.EU,
                   hold_matters=["m_exempt"])
        res = self.b.detect_all_conflicts({rec.id: rec}, {"m_exempt": m})
        self.assertNotIn("hd2", res.flagged_by_family["HOLD_DELETION"],
                         "Art. 17(3) exemption must suppress the SHACL violation")

    def test_skipped_families_declared(self):
        rec = _rec("x", contains_pii=True, jurisdiction=Jurisdiction.EU)
        res = self.b.detect_all_conflicts({rec.id: rec})
        rules = {s["rule"] for s in res.skipped_rule_families}
        self.assertTrue(any("PRIORITY" in r for r in rules))
        self.assertTrue(any("propagation closure" in r.lower() for r in rules))

    def test_engine_versions_recorded(self):
        rec = _rec("x", contains_pii=True, jurisdiction=Jurisdiction.EU)
        res = self.b.detect_all_conflicts({rec.id: rec})
        self.assertIn("pyshacl", res.engine)
        self.assertIn("rdflib", res.engine)


class TestE6Driver(unittest.TestCase):
    """Small-scale structural check of the E6 driver (one seed, tiny scale)."""

    SCALE = 600

    @classmethod
    def setUpClass(cls):
        cls.out = e6.run(seeds=[42], scales=[300, cls.SCALE])

    def test_structure(self):
        self.assertEqual(self.out["experiment"], "E6")
        self.assertIn(str(self.SCALE), self.out["per_scale"])
        self.assertIn("projection", self.out)

    def test_apples_to_apples_hold_context(self):
        # Both detectors share the same hold context, documented in the result.
        self.assertIn("apples-to-apples", self.out["hold_context"])

    def test_recall_and_latency_present(self):
        s = self.out["per_scale"][str(self.SCALE)]
        for f in e6.EXPRESSIBLE_FAMILIES:
            self.assertIn(f, s["recall_by_family"])
        self.assertGreater(s["sparql_detection_ms"]["mean"], 0.0)
        self.assertGreater(s["trkg_detection_ms"]["mean"], 0.0)

    def test_jurisdiction_recall_is_high(self):
        # The JURISDICTION shape mirrors T-RKG's rule closely; recall ~1.
        jr = self.out["per_scale"][str(self.SCALE)]["recall_by_family"]["JURISDICTION"]
        self.assertGreaterEqual(jr["mean"], 0.9)

    def test_projection_marks_unmeasured_scales(self):
        proj = self.out["projection"]["estimates"]
        for s in ("25000", "50000", "100000"):
            self.assertIn(s, proj)


if __name__ == "__main__":
    unittest.main()
