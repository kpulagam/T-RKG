#!/usr/bin/env python3
"""Tests for T-RKG system."""

import unittest
from datetime import datetime, timedelta

from trkg import (
    TRKGStore, Record, Custodian, Matter, Relationship,
    RecordType, RelationType, GovernanceState, Jurisdiction,
    generate_minimal_dataset, generate_test_dataset
)


class TestSchema(unittest.TestCase):
    """Test entity schema definitions."""
    
    def test_record_creation(self):
        record = Record(
            id="test_001",
            type=RecordType.EMAIL,
            title="Test Email",
            created=datetime.now(),
            modified=datetime.now(),
            custodian_id="emp_001"
        )
        self.assertEqual(record.id, "test_001")
        self.assertEqual(record.type, RecordType.EMAIL)
        self.assertEqual(record.governance_state, GovernanceState.ACTIVE)
    
    def test_custodian_creation(self):
        custodian = Custodian(
            id="emp_001",
            name="John Smith",
            email="john.smith@example.com",
            department="Engineering"
        )
        self.assertEqual(custodian.department, "Engineering")
        self.assertTrue(custodian.is_active)


class TestStore(unittest.TestCase):
    """Test TRKGStore operations."""
    
    def setUp(self):
        self.store = TRKGStore()
        
        # Add test custodian
        self.custodian = Custodian(
            id="emp_001",
            name="John Smith",
            email="john@example.com",
            department="Engineering"
        )
        self.store.add_custodian(self.custodian)
        
        # Add test records
        self.email = Record(
            id="email_001",
            type=RecordType.EMAIL,
            title="Test Email",
            created=datetime(2024, 1, 15),
            modified=datetime(2024, 1, 15),
            custodian_id="emp_001"
        )
        self.store.add_record(self.email)
        
        self.attachment = Record(
            id="doc_001",
            type=RecordType.DOCUMENT,
            title="Attachment.pdf",
            created=datetime(2024, 1, 15),
            modified=datetime(2024, 1, 15),
            custodian_id="emp_001"
        )
        self.store.add_record(self.attachment)
        
        # Add relationship
        self.rel = Relationship(
            id="rel_001",
            source_id="email_001",
            target_id="doc_001",
            relation_type=RelationType.ATTACHMENT,
            valid_from=datetime(2024, 1, 15)
        )
        self.store.add_relationship(self.rel)
    
    def test_add_and_get_record(self):
        record = self.store.get_record("email_001")
        self.assertIsNotNone(record)
        self.assertEqual(record.title, "Test Email")
    
    def test_select_records(self):
        emails = self.store.select_records(
            lambda r: r.type == RecordType.EMAIL
        )
        self.assertEqual(len(emails), 1)
        self.assertEqual(emails[0].id, "email_001")
    
    def test_get_related_records(self):
        related = self.store.get_related_records(
            "email_001",
            relation_types=[RelationType.ATTACHMENT]
        )
        self.assertEqual(len(related), 1)
        self.assertEqual(related[0][0], "doc_001")


class TestHoldPropagation(unittest.TestCase):
    """Test hold propagation algorithm."""
    
    def setUp(self):
        self.store = generate_minimal_dataset(seed=42)
    
    def test_propagation_expands(self):
        # Get some seed records
        seed_ids = list(self.store.records.keys())[:10]
        
        propagated = self.store.propagate_hold(
            seed_ids,
            [RelationType.ATTACHMENT, RelationType.THREAD],
            max_depth=5
        )
        
        # Should include at least the seeds
        self.assertGreaterEqual(len(propagated), len(seed_ids))
        for seed in seed_ids:
            self.assertIn(seed, propagated)
    
    def test_apply_and_release_hold(self):
        seed_ids = list(self.store.records.keys())[:5]
        
        # Apply hold
        assignments = self.store.apply_hold("test_matter", seed_ids)
        self.assertEqual(len(assignments), 5)
        
        # Verify records are on hold
        held = self.store.get_records_on_hold("test_matter")
        self.assertEqual(len(held), 5)
        
        # Release hold
        released = self.store.release_hold("test_matter", reason="Test complete")
        self.assertEqual(released, 5)
        
        # Verify no records on hold
        held_after = self.store.get_records_on_hold("test_matter")
        self.assertEqual(len(held_after), 0)


class TestTemporalQueries(unittest.TestCase):
    """Test temporal query functionality."""
    
    def setUp(self):
        self.store = generate_minimal_dataset(seed=42)
    
    def test_point_in_time_query(self):
        # Query at different points in time
        early = datetime(2021, 1, 1)
        late = datetime(2024, 12, 31)
        
        early_records = self.store.query_at_time(early)
        late_records = self.store.query_at_time(late)
        
        # Later query should return more records
        self.assertLessEqual(len(early_records), len(late_records))


class TestDataGeneration(unittest.TestCase):
    """Test synthetic data generation."""
    
    def test_minimal_dataset(self):
        store = generate_minimal_dataset(seed=42)
        
        self.assertGreater(len(store.records), 0)
        self.assertGreater(len(store.custodians), 0)
        self.assertGreater(len(store.relationships), 0)
    
    def test_scaled_dataset(self):
        store = generate_test_dataset(num_records=1000, seed=42)
        
        # Should be approximately 1000 records
        self.assertGreater(len(store.records), 800)
        self.assertLess(len(store.records), 1200)


class TestStatistics(unittest.TestCase):
    """Test statistics and analytics."""
    
    def test_get_statistics(self):
        store = generate_minimal_dataset(seed=42)
        stats = store.get_statistics()
        
        self.assertIn("total_records", stats)
        self.assertIn("total_relationships", stats)
        self.assertIn("records_by_type", stats)
        self.assertGreater(stats["total_records"], 0)


if __name__ == "__main__":
    unittest.main()
