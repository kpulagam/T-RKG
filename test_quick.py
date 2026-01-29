#!/usr/bin/env python3
"""Quick verification that T-RKG is working."""

import sys
sys.path.insert(0, '.')

def main():
    print("=" * 60)
    print("T-RKG Quick Verification")
    print("=" * 60)
    
    # Test 1: Import
    print("\n1. Testing imports...")
    try:
        from trkg import (
            TRKGStore, generate_minimal_dataset,
            ConflictDetector, GovernanceReasoner,
            load_ontology, RecordType, RelationType
        )
        print("   ✓ All imports successful")
    except ImportError as e:
        print(f"   ✗ Import failed: {e}")
        return False
    
    # Test 2: Ontology
    print("\n2. Testing ontology...")
    ontology = load_ontology()
    stats = ontology.get_statistics()
    print(f"   ✓ Loaded {stats['num_regulations']} regulations, {stats['num_jurisdictions']} jurisdictions")
    
    # Test 3: Data generation
    print("\n3. Testing data generation...")
    store = generate_minimal_dataset(seed=42)
    print(f"   ✓ Generated {len(store.records)} records, {len(store.relationships)} relationships")
    
    # Test 4: Hold propagation
    print("\n4. Testing hold propagation...")
    seeds = list(store.records.keys())[:10]
    propagated = store.propagate_hold(seeds, [RelationType.ATTACHMENT, RelationType.THREAD], max_depth=5)
    print(f"   ✓ Propagated from {len(seeds)} seeds to {len(propagated)} records")
    
    # Test 5: Conflict detection
    print("\n5. Testing conflict detection...")
    detector = ConflictDetector(store)
    conflicts = detector.detect_all_conflicts()
    summary = detector.get_conflict_summary()
    print(f"   ✓ Detected {summary['total_conflicts']} conflicts, {summary['affected_records']} affected records")
    
    # Test 6: Reasoning
    print("\n6. Testing reasoning engine...")
    reasoner = GovernanceReasoner(store)
    sample = list(store.records.values())[0]
    result = reasoner.reason_about_record(sample)
    print(f"   ✓ Reasoned about record: {len(result.inferred_regulations)} regulations apply")
    
    print("\n" + "=" * 60)
    print("✓ ALL TESTS PASSED - T-RKG is ready!")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
