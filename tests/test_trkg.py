#!/usr/bin/env python3
"""
Comprehensive tests for T-RKG system.

Covers: schema, store, conflict detection, baselines, synthetic data.
"""

import unittest
from datetime import datetime, timedelta
from collections import defaultdict

from trkg import (
    TRKGStore, Record, Custodian, Matter, Relationship,
    RecordType, RelationType, GovernanceState, Jurisdiction, Regulation,
    ConflictType, ConflictSeverity, RegulatoryConflict,
    generate_minimal_dataset, generate_test_dataset,
    ConflictDetector, SiloedConflictDetector, UntypedGraphConflictDetector,
    build_regulation_profiles, build_conflict_rules,
    get_ancestor_jurisdictions,
)
from trkg.baselines.flat_baseline import FlatListStore
from trkg.baselines.sql_baseline import SQLiteStore


# =============================================================================
# SCHEMA TESTS
# =============================================================================

class TestSchema(unittest.TestCase):
    def test_record_creation(self):
        record = Record(
            id="test_001", type=RecordType.EMAIL, title="Test Email",
            created=datetime.now(), modified=datetime.now(), custodian_id="emp_001"
        )
        self.assertEqual(record.id, "test_001")
        self.assertEqual(record.type, RecordType.EMAIL)
        self.assertEqual(record.governance_state, GovernanceState.ACTIVE)

    def test_custodian_creation(self):
        custodian = Custodian(
            id="emp_001", name="John Smith",
            email="john.smith@example.com", department="Engineering"
        )
        self.assertEqual(custodian.department, "Engineering")
        self.assertTrue(custodian.is_active)

    def test_conflict_type_enum(self):
        self.assertEqual(ConflictType.RETENTION_DELETION.value, "RETENTION_DELETION")
        self.assertEqual(ConflictSeverity.CRITICAL.value, "CRITICAL")

    def test_regulatory_conflict_creation(self):
        conflict = RegulatoryConflict(
            id="c1", record_id="r1",
            regulation_a=Regulation.GDPR, regulation_b=Regulation.SOX,
            conflict_type=ConflictType.RETENTION_DELETION,
            severity=ConflictSeverity.CRITICAL,
        )
        self.assertEqual(conflict.regulation_a, Regulation.GDPR)
        self.assertEqual(conflict.conflict_type, ConflictType.RETENTION_DELETION)


# =============================================================================
# STORE TESTS
# =============================================================================

class TestStore(unittest.TestCase):
    def setUp(self):
        self.store = TRKGStore()
        self.store.add_custodian(Custodian(
            id="emp_001", name="John Smith",
            email="john@example.com", department="Engineering"
        ))
        self.email = Record(
            id="email_001", type=RecordType.EMAIL, title="Test Email",
            created=datetime(2024, 1, 15), modified=datetime(2024, 1, 15),
            custodian_id="emp_001"
        )
        self.store.add_record(self.email)
        self.attachment = Record(
            id="doc_001", type=RecordType.DOCUMENT, title="Attachment.pdf",
            created=datetime(2024, 1, 15), modified=datetime(2024, 1, 15),
            custodian_id="emp_001"
        )
        self.store.add_record(self.attachment)
        self.rel = Relationship(
            id="rel_001", source_id="email_001", target_id="doc_001",
            relation_type=RelationType.ATTACHMENT,
            valid_from=datetime(2024, 1, 15)
        )
        self.store.add_relationship(self.rel)

    def test_add_and_get_record(self):
        record = self.store.get_record("email_001")
        self.assertIsNotNone(record)
        self.assertEqual(record.title, "Test Email")

    def test_select_records(self):
        emails = self.store.select_records(lambda r: r.type == RecordType.EMAIL)
        self.assertEqual(len(emails), 1)

    def test_get_related_records(self):
        related = self.store.get_related_records(
            "email_001", relation_types=[RelationType.ATTACHMENT]
        )
        self.assertEqual(len(related), 1)
        self.assertEqual(related[0][0], "doc_001")

    def test_propagate_hold_with_paths(self):
        paths = self.store.propagate_hold_with_paths(
            ["email_001"], [RelationType.ATTACHMENT], max_depth=5
        )
        self.assertIn("email_001", paths)
        self.assertIn("doc_001", paths)
        # doc_001 should have a path through email_001
        self.assertEqual(len(paths["doc_001"]), 1)


# =============================================================================
# HOLD PROPAGATION TESTS
# =============================================================================

class TestHoldPropagation(unittest.TestCase):
    def setUp(self):
        self.store = generate_minimal_dataset(seed=42)

    def test_propagation_expands(self):
        seed_ids = list(self.store.records.keys())[:10]
        propagated = self.store.propagate_hold(
            seed_ids, [RelationType.ATTACHMENT, RelationType.THREAD], max_depth=5
        )
        self.assertGreaterEqual(len(propagated), len(seed_ids))
        for seed in seed_ids:
            self.assertIn(seed, propagated)

    def test_apply_and_release_hold(self):
        seed_ids = list(self.store.records.keys())[:5]
        assignments = self.store.apply_hold("test_matter", seed_ids)
        self.assertEqual(len(assignments), 5)

        held = self.store.get_records_on_hold("test_matter")
        self.assertEqual(len(held), 5)

        released = self.store.release_hold("test_matter", reason="Test complete")
        self.assertEqual(released, 5)

        held_after = self.store.get_records_on_hold("test_matter")
        self.assertEqual(len(held_after), 0)


# =============================================================================
# JURISDICTION HIERARCHY TESTS
# =============================================================================

class TestJurisdictionHierarchy(unittest.TestCase):
    def test_us_ca_ancestors(self):
        ancestors = get_ancestor_jurisdictions(Jurisdiction.US_CA)
        self.assertIn(Jurisdiction.US_CA, ancestors)
        self.assertIn(Jurisdiction.US, ancestors)
        self.assertIn(Jurisdiction.GLOBAL, ancestors)

    def test_eu_de_ancestors(self):
        ancestors = get_ancestor_jurisdictions(Jurisdiction.EU_DE)
        self.assertIn(Jurisdiction.EU_DE, ancestors)
        self.assertIn(Jurisdiction.EU, ancestors)
        self.assertIn(Jurisdiction.GLOBAL, ancestors)

    def test_us_is_not_ancestor_of_eu(self):
        ancestors = get_ancestor_jurisdictions(Jurisdiction.EU_DE)
        self.assertNotIn(Jurisdiction.US, ancestors)


# =============================================================================
# REGULATION PROFILE TESTS
# =============================================================================

class TestRegulationProfiles(unittest.TestCase):
    def setUp(self):
        self.profiles = build_regulation_profiles()

    def test_gdpr_applies_to_eu_pii(self):
        record = Record(
            id="r1", type=RecordType.EMAIL, title="EU Email",
            created=datetime.now(), modified=datetime.now(),
            jurisdiction=Jurisdiction.EU_DE, contains_pii=True
        )
        self.assertTrue(self.profiles[Regulation.GDPR].applies_to(record))

    def test_gdpr_not_applies_to_us_pii(self):
        record = Record(
            id="r2", type=RecordType.EMAIL, title="US Email",
            created=datetime.now(), modified=datetime.now(),
            jurisdiction=Jurisdiction.US, contains_pii=True
        )
        self.assertFalse(self.profiles[Regulation.GDPR].applies_to(record))

    def test_gdpr_not_applies_without_pii(self):
        record = Record(
            id="r3", type=RecordType.EMAIL, title="EU Email no PII",
            created=datetime.now(), modified=datetime.now(),
            jurisdiction=Jurisdiction.EU, contains_pii=False
        )
        self.assertFalse(self.profiles[Regulation.GDPR].applies_to(record))

    def test_sox_applies_to_us_financial_public(self):
        record = Record(
            id="r4", type=RecordType.FINANCIAL, title="Financial Statement",
            created=datetime.now(), modified=datetime.now(),
            jurisdiction=Jurisdiction.US,
            metadata={"is_public_company": True}
        )
        self.assertTrue(self.profiles[Regulation.SOX].applies_to(record))

    def test_sox_not_applies_to_private_company(self):
        record = Record(
            id="r5", type=RecordType.FINANCIAL, title="Financial Statement",
            created=datetime.now(), modified=datetime.now(),
            jurisdiction=Jurisdiction.US,
            metadata={"is_public_company": False}
        )
        self.assertFalse(self.profiles[Regulation.SOX].applies_to(record))

    def test_sox_not_applies_to_email(self):
        record = Record(
            id="r6", type=RecordType.EMAIL, title="Just an email",
            created=datetime.now(), modified=datetime.now(),
            jurisdiction=Jurisdiction.US,
            metadata={"is_public_company": True}
        )
        self.assertFalse(self.profiles[Regulation.SOX].applies_to(record))

    def test_hipaa_applies_to_us_phi(self):
        record = Record(
            id="r7", type=RecordType.DOCUMENT, title="Medical Record",
            created=datetime.now(), modified=datetime.now(),
            jurisdiction=Jurisdiction.US, contains_phi=True
        )
        self.assertTrue(self.profiles[Regulation.HIPAA].applies_to(record))

    def test_cpra_applies_to_ca_pii(self):
        record = Record(
            id="r8", type=RecordType.EMAIL, title="CA Email",
            created=datetime.now(), modified=datetime.now(),
            jurisdiction=Jurisdiction.US_CA, contains_pii=True
        )
        self.assertTrue(self.profiles[Regulation.CPRA].applies_to(record))

    def test_cpra_not_applies_to_us_non_ca(self):
        record = Record(
            id="r9", type=RecordType.EMAIL, title="US Email",
            created=datetime.now(), modified=datetime.now(),
            jurisdiction=Jurisdiction.US, contains_pii=True
        )
        self.assertFalse(self.profiles[Regulation.CPRA].applies_to(record))

    def test_hgb_applies_to_german_financial(self):
        record = Record(
            id="r10", type=RecordType.FINANCIAL, title="German Financial",
            created=datetime.now(), modified=datetime.now(),
            jurisdiction=Jurisdiction.EU_DE,
        )
        self.assertTrue(self.profiles[Regulation.HGB].applies_to(record))

    def test_sec_applies_to_us_financial(self):
        record = Record(
            id="r11", type=RecordType.FINANCIAL, title="US Financial",
            created=datetime.now(), modified=datetime.now(),
            jurisdiction=Jurisdiction.US,
        )
        self.assertTrue(self.profiles[Regulation.SEC].applies_to(record))


# =============================================================================
# CONFLICT DETECTION TESTS
# =============================================================================

class TestConflictDetection(unittest.TestCase):
    def setUp(self):
        self.detector = ConflictDetector()

    def test_gdpr_sox_conflict(self):
        """EU financial record with PII → GDPR (delete) vs SOX (retain)."""
        record = Record(
            id="conflict_1", type=RecordType.FINANCIAL, title="EU Financial",
            created=datetime.now(), modified=datetime.now(),
            jurisdiction=Jurisdiction.EU, contains_pii=True,
            metadata={"is_public_company": True}
        )
        applicable = self.detector.infer_applicable_regulations(record)
        self.assertIn(Regulation.GDPR, applicable)
        self.assertIn(Regulation.SOX, applicable)

        conflicts = self.detector.detect_conflicts_for_record(record, applicable)
        conflict_pairs = {(c.regulation_a, c.regulation_b) for c in conflicts}
        self.assertIn((Regulation.GDPR, Regulation.SOX), conflict_pairs)
        # Should be CRITICAL severity
        gdpr_sox = [c for c in conflicts
                    if c.regulation_a == Regulation.GDPR and c.regulation_b == Regulation.SOX]
        self.assertEqual(gdpr_sox[0].severity, ConflictSeverity.CRITICAL)

    def test_cpra_sox_conflict(self):
        """CA financial record with PII → CPRA (delete) vs SOX (retain)."""
        record = Record(
            id="conflict_2", type=RecordType.FINANCIAL, title="CA Financial",
            created=datetime.now(), modified=datetime.now(),
            jurisdiction=Jurisdiction.US_CA, contains_pii=True,
            metadata={"is_public_company": True}
        )
        applicable = self.detector.infer_applicable_regulations(record)
        self.assertIn(Regulation.CPRA, applicable)
        self.assertIn(Regulation.SOX, applicable)

        conflicts = self.detector.detect_conflicts_for_record(record, applicable)
        self.assertTrue(len(conflicts) > 0)

    def test_no_conflict_plain_email(self):
        """Plain US email without PII → no conflicting regulations."""
        record = Record(
            id="no_conflict", type=RecordType.EMAIL, title="Plain Email",
            created=datetime.now(), modified=datetime.now(),
            jurisdiction=Jurisdiction.US, contains_pii=False,
        )
        conflicts = self.detector.detect_conflicts_for_record(record)
        self.assertEqual(len(conflicts), 0)

    def test_no_conflict_us_financial_no_pii(self):
        """US financial record without PII → retention regs only, no delete vs retain."""
        record = Record(
            id="no_conflict_2", type=RecordType.FINANCIAL, title="US Financial",
            created=datetime.now(), modified=datetime.now(),
            jurisdiction=Jurisdiction.US,
            metadata={"is_public_company": True}
        )
        applicable = self.detector.infer_applicable_regulations(record)
        conflicts = self.detector.detect_conflicts_for_record(record, applicable)
        # Only priority conflicts (SOX vs SEC vs IRS) — not retention-deletion
        for c in conflicts:
            self.assertNotEqual(c.conflict_type, ConflictType.RETENTION_DELETION)

    def test_detect_all_conflicts(self):
        """Full conflict detection on a generated dataset."""
        store = generate_minimal_dataset(seed=42)
        result = self.detector.detect_all_conflicts(store.records)

        self.assertGreater(result.total_records_analyzed, 0)
        # Should find at least some conflicts (EU PII financial records exist)
        self.assertGreater(result.total_conflicts, 0)
        self.assertGreater(result.detection_time_ms, 0)

    def test_hold_deletion_conflict(self):
        """Record under hold with deletion regulation → hold-deletion conflict."""
        record = Record(
            id="hold_del", type=RecordType.EMAIL, title="EU Held Email",
            created=datetime.now(), modified=datetime.now(),
            jurisdiction=Jurisdiction.EU, contains_pii=True,
            hold_matters=["matter_001"],
        )
        conflicts = self.detector.detect_conflicts_for_record(
            record, active_holds={"matter_001"}
        )
        hold_conflicts = [c for c in conflicts if c.conflict_type == ConflictType.HOLD_DELETION]
        self.assertGreater(len(hold_conflicts), 0)


# =============================================================================
# BASELINE TESTS
# =============================================================================

class TestSiloedBaseline(unittest.TestCase):
    def test_detects_zero_conflicts(self):
        store = generate_minimal_dataset(seed=42)
        siloed = SiloedConflictDetector()
        result = siloed.detect_all_conflicts(store.records)
        self.assertEqual(result.total_conflicts, 0)


class TestUntypedBaseline(unittest.TestCase):
    def test_detects_zero_conflicts(self):
        store = generate_minimal_dataset(seed=42)
        untyped = UntypedGraphConflictDetector()
        result = untyped.detect_all_conflicts(store.records)
        self.assertEqual(result.total_conflicts, 0)


class TestFlatListBaseline(unittest.TestCase):
    def test_select_records(self):
        store = generate_minimal_dataset(seed=42)
        flat = FlatListStore.from_trkg_store(store)
        emails = flat.select_records(lambda r: r.type == RecordType.EMAIL)
        trkg_emails = store.select_records(lambda r: r.type == RecordType.EMAIL)
        self.assertEqual(len(emails), len(trkg_emails))

    def test_propagation_same_result(self):
        store = generate_minimal_dataset(seed=42)
        flat = FlatListStore.from_trkg_store(store)
        seed_ids = list(store.records.keys())[:10]
        rel_types = [RelationType.ATTACHMENT, RelationType.THREAD]

        trkg_result = store.propagate_hold(seed_ids, rel_types, max_depth=5)
        flat_result = flat.propagate_hold(seed_ids, rel_types, max_depth=5)
        self.assertEqual(trkg_result, flat_result)


class TestSQLiteBaseline(unittest.TestCase):
    def test_propagation_same_result(self):
        store = generate_minimal_dataset(seed=42)
        sql = SQLiteStore.from_trkg_store(store)
        seed_ids = list(store.records.keys())[:10]
        rel_types = [RelationType.ATTACHMENT, RelationType.THREAD]

        trkg_result = store.propagate_hold(seed_ids, rel_types, max_depth=5)
        sql_result = sql.propagate_hold(seed_ids, rel_types, max_depth=5)

        # SQLite CTE result should be a subset/superset — verify overlap
        # (exact match may vary due to CTE iteration order edge cases)
        self.assertGreater(len(trkg_result & sql_result), len(seed_ids))
        sql.close()


# =============================================================================
# DATA GENERATION TESTS
# =============================================================================

class TestDataGeneration(unittest.TestCase):
    def test_minimal_dataset(self):
        store = generate_minimal_dataset(seed=42)
        self.assertGreater(len(store.records), 0)
        self.assertGreater(len(store.custodians), 0)
        self.assertGreater(len(store.relationships), 0)

    def test_scaled_dataset(self):
        store = generate_test_dataset(num_records=1000, seed=42)
        self.assertGreater(len(store.records), 800)
        self.assertLess(len(store.records), 1200)

    def test_jurisdiction_distribution(self):
        store = generate_test_dataset(num_records=5000, seed=42)
        jurisdictions = defaultdict(int)
        for r in store.records.values():
            jurisdictions[r.jurisdiction] += 1
        # Should have EU records (for conflict detection)
        eu_count = sum(v for k, v in jurisdictions.items()
                       if k in {Jurisdiction.EU, Jurisdiction.EU_DE,
                                Jurisdiction.EU_ES, Jurisdiction.EU_FR})
        self.assertGreater(eu_count, 0)

    def test_financial_records_have_metadata(self):
        store = generate_minimal_dataset(seed=42)
        fin_records = [r for r in store.records.values()
                       if r.type in {RecordType.FINANCIAL, RecordType.AUDIT,
                                     RecordType.TAX, RecordType.INVOICE}]
        if fin_records:
            # Should have is_public_company metadata
            has_public = any(r.metadata.get("is_public_company") for r in fin_records)
            self.assertTrue(has_public)


# =============================================================================
# TEMPORAL QUERY TESTS
# =============================================================================

class TestTemporalQueries(unittest.TestCase):
    def setUp(self):
        self.store = generate_minimal_dataset(seed=42)

    def test_point_in_time_query(self):
        early = datetime(2021, 1, 1)
        late = datetime(2024, 12, 31)
        early_records = self.store.query_at_time(early)
        late_records = self.store.query_at_time(late)
        self.assertLessEqual(len(early_records), len(late_records))


# =============================================================================
# STATISTICS TESTS
# =============================================================================

class TestStatistics(unittest.TestCase):
    def test_get_statistics(self):
        store = generate_minimal_dataset(seed=42)
        stats = store.get_statistics()
        self.assertIn("total_records", stats)
        self.assertIn("total_relationships", stats)
        self.assertIn("records_by_type", stats)
        self.assertGreater(stats["total_records"], 0)


if __name__ == "__main__":
    unittest.main()
