#!/usr/bin/env python3
"""Tests for T-RKG system."""

import unittest
from datetime import datetime, timedelta

from trkg import (
    TRKGStore, Record, Custodian, Matter, Relationship,
    RecordType, RelationType, GovernanceState, Jurisdiction,
    generate_minimal_dataset, generate_test_dataset,
    ConflictDetector, GovernanceReasoner, load_ontology
)


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
            id="emp_001", name="John Smith", email="john@example.com", department="Engineering"
        )
        self.assertEqual(custodian.department, "Engineering")
        self.assertTrue(custodian.is_active)


class TestStore(unittest.TestCase):
    def setUp(self):
        self.store = TRKGStore()
        self.custodian = Custodian(id="emp_001", name="John Smith", email="john@example.com", department="Engineering")
        self.store.add_custodian(self.custodian)
        
        self.email = Record(id="email_001", type=RecordType.EMAIL, title="Test Email",
                           created=datetime(2024, 1, 15), modified=datetime(2024, 1, 15), custodian_id="emp_001")
        self.store.add_record(self.email)
        
        self.attachment = Record(id="doc_001", type=RecordType.DOCUMENT, title="Attachment.pdf",
                                created=datetime(2024, 1, 15), modified=datetime(2024, 1, 15), custodian_id="emp_001")
        self.store.add_record(self.attachment)
        
        self.rel = Relationship(id="rel_001", source_id="email_001", target_id="doc_001",
                               relation_type=RelationType.ATTACHMENT, valid_from=datetime(2024, 1, 15))
        self.store.add_relationship(self.rel)
    
    def test_add_and_get_record(self):
        record = self.store.get_record("email_001")
        self.assertIsNotNone(record)
        self.assertEqual(record.title, "Test Email")
    
    def test_select_records(self):
        emails = self.store.select_records(lambda r: r.type == RecordType.EMAIL)
        self.assertEqual(len(emails), 1)
    
    def test_get_related_records(self):
        related = self.store.get_related_records("email_001", relation_types=[RelationType.ATTACHMENT])
        self.assertEqual(len(related), 1)
        self.assertEqual(related[0][0], "doc_001")


class TestHoldPropagation(unittest.TestCase):
    def setUp(self):
        self.store = generate_minimal_dataset(seed=42)
    
    def test_propagation_expands(self):
        seed_ids = list(self.store.records.keys())[:10]
        propagated = self.store.propagate_hold(seed_ids, [RelationType.ATTACHMENT, RelationType.THREAD], max_depth=5)
        self.assertGreaterEqual(len(propagated), len(seed_ids))
    
    def test_apply_and_release_hold(self):
        seed_ids = list(self.store.records.keys())[:5]
        assignments = self.store.apply_hold("test_matter", seed_ids)
        self.assertEqual(len(assignments), 5)
        
        held = self.store.get_records_on_hold("test_matter")
        self.assertEqual(len(held), 5)
        
        released = self.store.release_hold("test_matter", reason="Test complete")
        self.assertEqual(released, 5)


class TestConflictDetection(unittest.TestCase):
    def setUp(self):
        self.store = generate_minimal_dataset(seed=42)
    
    def test_detect_conflicts(self):
        detector = ConflictDetector(self.store)
        conflicts = detector.detect_all_conflicts()
        # May or may not have conflicts depending on data
        self.assertIsInstance(conflicts, list)
    
    def test_conflict_summary(self):
        detector = ConflictDetector(self.store)
        summary = detector.get_conflict_summary()
        self.assertIn("total_conflicts", summary)
        self.assertIn("affected_records", summary)


class TestOntology(unittest.TestCase):
    def test_load_ontology(self):
        ontology = load_ontology()
        self.assertIsNotNone(ontology)
        self.assertGreater(len(ontology.regulations), 0)
    
    def test_get_regulations_for_jurisdiction(self):
        ontology = load_ontology()
        us_regs = ontology.get_regulations_for_jurisdiction("US")
        self.assertIn("SOX", us_regs)
    
    def test_propagates_hold(self):
        ontology = load_ontology()
        self.assertTrue(ontology.propagates_hold("ATTACHMENT"))
        self.assertFalse(ontology.propagates_hold("REFERENCE"))


class TestReasoning(unittest.TestCase):
    def setUp(self):
        self.store = generate_minimal_dataset(seed=42)
    
    def test_reason_about_record(self):
        reasoner = GovernanceReasoner(self.store)
        record = list(self.store.records.values())[0]
        result = reasoner.reason_about_record(record)
        self.assertIsNotNone(result)
        self.assertEqual(result.record_id, record.id)
    
    def test_reasoning_statistics(self):
        reasoner = GovernanceReasoner(self.store)
        stats = reasoner.get_reasoning_statistics()
        self.assertGreater(stats.total_records, 0)


class TestDataGeneration(unittest.TestCase):
    def test_minimal_dataset(self):
        store = generate_minimal_dataset(seed=42)
        self.assertGreater(len(store.records), 0)
        self.assertGreater(len(store.custodians), 0)
    
    def test_scaled_dataset(self):
        store = generate_test_dataset(num_records=1000, seed=42)
        self.assertGreater(len(store.records), 800)
        self.assertLess(len(store.records), 1200)


if __name__ == "__main__":
    unittest.main()
