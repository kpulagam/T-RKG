#!/usr/bin/env python3
"""
T-RKG Experiments for KBS Paper

Research Questions:
    RQ1: Scalability - Does T-RKG scale to enterprise volumes?
    RQ2: Hold Propagation - Does typed propagation improve precision?
    RQ3: Conflict Detection - Can T-RKG detect multi-jurisdictional conflicts?
    RQ4: Ontology Coverage - How well does the ontology cover governance concepts?
    RQ5: Reasoning Performance - What is the cost of ontological reasoning?

Usage:
    python run_experiments.py [--scale N] [--output results.json]
"""

import argparse
import json
import time
import statistics
from datetime import datetime
from collections import defaultdict
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trkg import (
    TRKGStore, RecordType, RelationType,
    SyntheticDataGenerator, GeneratorConfig, generate_test_dataset,
    ConflictDetector, GovernanceReasoner,
    load_ontology, analyze_ontology_coverage
)


def print_section(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def experiment_scalability(max_scale=100000):
    """RQ1: Scalability"""
    print_section("RQ1: SCALABILITY")
    
    scales = [1000, 5000, 10000, 25000, 50000]
    if max_scale >= 100000:
        scales.append(100000)
    
    results = []
    for num_records in scales:
        print(f"\n  Testing {num_records:,} records...")
        
        scale = num_records / 10000
        config = GeneratorConfig(
            num_emails=int(4000 * scale), num_documents=int(3000 * scale),
            num_chats=int(1500 * scale), num_tickets=int(500 * scale),
            num_contracts=int(500 * scale), num_financial=int(500 * scale),
            num_custodians=max(20, int(100 * scale)), num_matters=5
        )
        
        gen_times = []
        for run in range(3):
            start = time.time()
            generator = SyntheticDataGenerator(config, seed=42 + run)
            store = generator.generate()
            gen_times.append(time.time() - start)
        
        stats = store.get_statistics()
        
        query_times = []
        for _ in range(5):
            start = time.time()
            _ = store.get_records_by_type(RecordType.EMAIL)
            query_times.append((time.time() - start) * 1000)
        
        seed_ids = list(store.records.keys())[:100]
        prop_times, prop_counts = [], []
        for _ in range(5):
            start = time.time()
            propagated = store.propagate_hold(seed_ids, [RelationType.ATTACHMENT, RelationType.THREAD], max_depth=5)
            prop_times.append((time.time() - start) * 1000)
            prop_counts.append(len(propagated))
        
        result = {
            "records": stats["total_records"],
            "relationships": stats["total_relationships"],
            "gen_time_avg": round(statistics.mean(gen_times), 3),
            "throughput": int(stats["total_records"] / statistics.mean(gen_times)),
            "query_time_avg_ms": round(statistics.mean(query_times), 2),
            "prop_time_avg_ms": round(statistics.mean(prop_times), 2),
        }
        results.append(result)
        print(f"    Throughput: {result['throughput']:,}/sec, Query: {result['query_time_avg_ms']:.2f}ms")
    
    return {"scalability": results}


def experiment_hold_propagation():
    """RQ2: Hold Propagation"""
    print_section("RQ2: HOLD PROPAGATION")
    
    store = generate_test_dataset(num_records=10000, seed=42)
    eng_custodians = [c.id for c in store.custodians.values() if c.department == "Engineering"]
    seeds = [r.id for r in store.records.values() if r.custodian_id in eng_custodians][:50]
    
    configs = [
        ("ATTACHMENT only", [RelationType.ATTACHMENT]),
        ("THREAD only", [RelationType.THREAD]),
        ("ATT + THREAD", [RelationType.ATTACHMENT, RelationType.THREAD]),
        ("All relationships", list(RelationType)),
    ]
    
    results = []
    for name, relations in configs:
        times, counts = [], []
        for _ in range(5):
            start = time.time()
            propagated = store.propagate_hold(seeds, relations, max_depth=10)
            times.append((time.time() - start) * 1000)
            counts.append(len(propagated))
        
        results.append({
            "config": name,
            "propagated_avg": int(statistics.mean(counts)),
            "expansion_ratio": round(statistics.mean(counts) / len(seeds), 2),
            "time_avg_ms": round(statistics.mean(times), 3),
        })
        print(f"  {name}: {results[-1]['propagated_avg']} records ({results[-1]['expansion_ratio']}x)")
    
    return {"hold_propagation": results}


def experiment_conflict_detection():
    """RQ3: Conflict Detection"""
    print_section("RQ3: CONFLICT DETECTION")
    
    store = generate_test_dataset(num_records=10000, seed=42)
    detector = ConflictDetector(store)
    
    start = time.time()
    conflicts = detector.detect_all_conflicts()
    detection_time = (time.time() - start) * 1000
    
    summary = detector.get_conflict_summary()
    print(f"  Detected {summary['total_conflicts']} conflicts in {detection_time:.2f}ms")
    print(f"  Affected records: {summary['affected_records']}")
    print(f"  Critical: {summary['critical_count']}")
    
    return {"conflict_detection": {**summary, "detection_time_ms": round(detection_time, 2)}}


def experiment_ontology_coverage():
    """RQ4: Ontology Coverage"""
    print_section("RQ4: ONTOLOGY COVERAGE")
    
    store = generate_test_dataset(num_records=10000, seed=42)
    coverage = analyze_ontology_coverage(store)
    
    print(f"  Jurisdiction coverage: {coverage['jurisdiction_coverage']['coverage_ratio']:.1%}")
    print(f"  Regulation applicability: {coverage['regulation_applicability']['coverage_ratio']:.1%}")
    
    return {"ontology_coverage": coverage}


def experiment_reasoning():
    """RQ5: Reasoning Performance"""
    print_section("RQ5: REASONING PERFORMANCE")
    
    store = generate_test_dataset(num_records=10000, seed=42)
    reasoner = GovernanceReasoner(store)
    
    stats = reasoner.get_reasoning_statistics()
    print(f"  Reasoning time: {stats.reasoning_time_ms:.2f}ms for {stats.total_records} records")
    print(f"  Time per record: {stats.reasoning_time_ms / stats.total_records:.4f}ms")
    print(f"  Records with conflicts: {stats.records_with_conflicts}")
    
    return {"reasoning": {
        "total_records": stats.total_records,
        "reasoning_time_ms": stats.reasoning_time_ms,
        "records_with_conflicts": stats.records_with_conflicts,
        "total_conflicts": stats.total_conflicts
    }}


def run_all_experiments(max_scale=100000, output_file=None):
    print("\n" + "=" * 70)
    print("  T-RKG EXPERIMENTS FOR KBS SUBMISSION")
    print("=" * 70)
    
    results = {"metadata": {"run_date": datetime.now().isoformat(), "version": "2.0.0"}}
    
    results.update(experiment_scalability(max_scale))
    results.update(experiment_hold_propagation())
    results.update(experiment_conflict_detection())
    results.update(experiment_ontology_coverage())
    results.update(experiment_reasoning())
    
    if output_file:
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n  Results saved to: {output_file}")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Run T-RKG experiments")
    parser.add_argument("--scale", type=int, default=100000)
    parser.add_argument("--output", type=str, default="results.json")
    args = parser.parse_args()
    
    run_all_experiments(max_scale=args.scale, output_file=args.output)


if __name__ == "__main__":
    main()
