"""Predicate-level tests for the GDPR Article 17(3) exemption suppression."""

from datetime import datetime

from trkg.schema import (
    Record, RecordType, Jurisdiction, GovernanceState, Regulation, Matter,
    ConflictType,
)
from trkg.conflict import ConflictDetector


def _pii_eu_record(rec_id: str = "rec_pii_eu") -> Record:
    """Record that triggers GDPR Article 17 erasure applicability."""
    now = datetime(2024, 6, 1)
    return Record(
        id=rec_id,
        type=RecordType.EMAIL,
        title="EU subject correspondence",
        created=now,
        modified=now,
        custodian_id="cust_001",
        system_id="sys_email",
        contains_pii=True,
        jurisdiction=Jurisdiction.EU_DE,
        governance_state=GovernanceState.HOLD,
    )


def _matter(obl: bool = False, clm: bool = False, mid: str = "matter_lit") -> Matter:
    return Matter(
        id=mid,
        name="Test Matter",
        matter_type="LITIGATION",
        is_active=True,
        legal_obligation_flag=obl,
        legal_claim_flag=clm,
    )


def test_hold_without_flags_yields_conflict():
    rec = _pii_eu_record()
    m = _matter(obl=False, clm=False)
    rec.hold_matters = [m.id]

    det = ConflictDetector(matters={m.id: m})
    conflicts = det.detect_conflicts_for_record(rec, active_holds=[m.id])

    hold_del = [c for c in conflicts if c.conflict_type == ConflictType.HOLD_DELETION]
    assert any(c.regulation_a == Regulation.GDPR for c in hold_del), (
        "Expected a GDPR Hold-Deletion conflict when neither exemption flag is set"
    )
    assert det.suppressed_exemption_count == 0


def test_hold_with_legal_obligation_suppresses_conflict():
    rec = _pii_eu_record()
    m = _matter(obl=True, clm=False)
    rec.hold_matters = [m.id]

    det = ConflictDetector(matters={m.id: m})
    conflicts = det.detect_conflicts_for_record(rec, active_holds=[m.id])

    hold_del = [c for c in conflicts if c.conflict_type == ConflictType.HOLD_DELETION
                and c.regulation_a == Regulation.GDPR]
    assert hold_del == [], (
        "GDPR Hold-Deletion conflict should be suppressed under Art. 17(3)(b)"
    )
    assert det.suppressed_exemption_count == 1


def test_hold_with_legal_claim_suppresses_conflict():
    rec = _pii_eu_record()
    m = _matter(obl=False, clm=True)
    rec.hold_matters = [m.id]

    det = ConflictDetector(matters={m.id: m})
    conflicts = det.detect_conflicts_for_record(rec, active_holds=[m.id])

    hold_del = [c for c in conflicts if c.conflict_type == ConflictType.HOLD_DELETION
                and c.regulation_a == Regulation.GDPR]
    assert hold_del == [], (
        "GDPR Hold-Deletion conflict should be suppressed under Art. 17(3)(e)"
    )
    assert det.suppressed_exemption_count == 1


def test_flags_dont_affect_records_not_on_that_matter():
    rec = _pii_eu_record()
    exempt = _matter(obl=True, clm=True, mid="matter_exempt")
    unrelated = _matter(obl=False, clm=False, mid="matter_unrelated")
    rec.hold_matters = [unrelated.id]

    det = ConflictDetector(matters={exempt.id: exempt, unrelated.id: unrelated})
    conflicts = det.detect_conflicts_for_record(rec, active_holds=[unrelated.id])

    hold_del = [c for c in conflicts if c.conflict_type == ConflictType.HOLD_DELETION
                and c.regulation_a == Regulation.GDPR]
    assert len(hold_del) == 1, (
        "Exemption on a different matter must not suppress the conflict"
    )
    assert det.suppressed_exemption_count == 0


def test_flags_dont_affect_non_hold_deletion_conflicts():
    """Flags must not influence pairwise (e.g. GDPR-vs-SOX) conflicts."""
    now = datetime(2024, 6, 1)
    rec = Record(
        id="rec_fin",
        type=RecordType.FINANCIAL,
        title="EU public-company invoice",
        created=now, modified=now,
        custodian_id="cust_001", system_id="sys_erp",
        contains_pii=True,
        jurisdiction=Jurisdiction.EU_DE,
        metadata={"is_public_company": True},
    )
    m = _matter(obl=True, clm=True)

    det = ConflictDetector(matters={m.id: m})
    # active_holds intentionally omitted so the Hold-Deletion branch is skipped.
    conflicts = det.detect_conflicts_for_record(rec)

    pairwise = [c for c in conflicts if c.conflict_type != ConflictType.HOLD_DELETION]
    assert len(pairwise) >= 1, (
        "Pairwise conflicts must be unaffected by matter exemption flags"
    )
    assert det.suppressed_exemption_count == 0


def test_no_matters_dict_falls_back_to_no_suppression():
    """Without a matters dict, suppression cannot fire."""
    rec = _pii_eu_record()
    m = _matter(obl=True, clm=True)
    rec.hold_matters = [m.id]

    det = ConflictDetector()
    conflicts = det.detect_conflicts_for_record(rec, active_holds=[m.id])

    hold_del = [c for c in conflicts if c.conflict_type == ConflictType.HOLD_DELETION
                and c.regulation_a == Regulation.GDPR]
    assert len(hold_del) == 1
    assert det.suppressed_exemption_count == 0


def test_independent_bernoulli_sampling_in_generator():
    """Different seeds should produce different exemption-flag configurations."""
    from trkg.synthetic import generate_test_dataset

    configs = []
    for seed in (42, 123, 456, 789, 1024):
        store = generate_test_dataset(num_records=1000, seed=seed)
        configs.append(tuple(
            (m.legal_obligation_flag, m.legal_claim_flag)
            for m in store.matters.values()
        ))
    assert len(set(configs)) >= 2, (
        "Exemption flags appear to be deterministic across seeds -- the "
        "sampling is not independent of the RNG."
    )
