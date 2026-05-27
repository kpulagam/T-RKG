"""Tests for the SHACL baseline: static-conflict coverage, declared gaps,
and a 10K-ABox smoke test."""

from datetime import datetime

from trkg.schema import (
    Record, RecordType, Jurisdiction, GovernanceState, Matter,
)
from trkg.synthetic import generate_test_dataset
from trkg.baselines import ShaclBaseline


def test_shacl_detects_static_gdpr_sox_conjunction():
    """SHACL flags the static GDPR-vs-SOX attribute conjunction."""
    now = datetime(2024, 6, 1)
    rec = Record(
        id="rec_static_violation",
        type=RecordType.INVOICE,
        title="EU public-company invoice",
        created=now, modified=now,
        custodian_id="cust_001", system_id="sys_erp",
        contains_pii=True,
        jurisdiction=Jurisdiction.EU_DE,
        metadata={"is_public_company": True},
    )
    b = ShaclBaseline()
    res = b.detect_all_conflicts({rec.id: rec})
    assert res.total_violations >= 1
    assert "Info" in res.violations_by_severity
    assert any("GDPR-vs-SOX" in m for m in res.violations_by_message)


def test_shacl_fails_to_express_temporal_conflicts():
    """SHACL Core lacks interval algebra; the baseline must declare the gap."""
    b = ShaclBaseline()
    assert "Temporal interval intersection (Allen-style)" in b.skipped_rule_families
    temporal = next(
        e for e in b.limitations["not_expressible_in_shacl"]
        if e["rule"].startswith("Temporal interval")
    )
    assert "interval algebra" in temporal["missing_feature"].lower()
    assert "spec_reference" in temporal


def test_shacl_does_not_crash_on_10k_abox():
    """pyshacl completes on a 10K-record ABox without raising."""
    store = generate_test_dataset(num_records=10000, seed=42)
    b = ShaclBaseline()
    res = b.detect_all_conflicts(store.records, store.matters)
    assert res.total_violations >= 0
    assert res.abox_triples > 10000
    assert res.detection_time_ms > 0.0


def test_shacl_skips_defeasibility_and_recursion():
    """The other two unsupported rule families are listed in `skipped_rule_families`."""
    b = ShaclBaseline()
    assert "Defeasible priority resolution" in b.skipped_rule_families
    assert "Cross-record propagation closure" in b.skipped_rule_families


def test_shacl_baseline_reports_expressible_subset():
    """The baseline reports a non-empty expressible rule set."""
    b = ShaclBaseline()
    assert b.expressible_rule_count >= 1
