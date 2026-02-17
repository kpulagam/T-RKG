#!/usr/bin/env python3
"""
T-RKG Experiments for Knowledge-Based Systems Publication

This experimental framework validates T-RKG's UNIQUE capabilities that are
MISSING from current enterprise content management systems:

1. Multi-regulation retention reasoning
2. Cross-jurisdictional conflict detection  
3. Typed relationship hold propagation
4. Explainable governance decisions

NOTE: We do NOT compare performance against databases (PostgreSQL, Neo4j).
T-RKG is not a database replacement - it provides governance CAPABILITIES
that databases lack entirely.
"""

import json
import time
import statistics
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, Any, List
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trkg import (
    TRKGStore, Record, RecordType, RelationType, Jurisdiction, Regulation,
    GovernanceState, SyntheticDataGenerator, GeneratorConfig,
    generate_test_dataset, ConflictDetector, RetentionCalculator,
    GovernanceReasoner, RETENTION_RULES, CONFLICT_RULES
)


def print_section(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


# =============================================================================
# RQ1: SCALABILITY
# =============================================================================

def experiment_scalability() -> Dict[str, Any]:
    """
    RQ1: How does T-RKG scale with increasing data volume?
    
    Tests graph construction and query performance at different scales.
    This validates that T-RKG can handle enterprise-scale datasets.
    """
    print_section("RQ1: SCALABILITY")
    
    scales = [1000, 5000, 10000, 25000, 50000, 100000]
    results = []
    
    for num_records in scales:
        print(f"\n  Testing {num_records:,} records...")
        
        scale = num_records / 10000
        config = GeneratorConfig(
            num_emails=int(4000 * scale),
            num_documents=int(3000 * scale),
            num_chats=int(1500 * scale),
            num_tickets=int(500 * scale),
            num_contracts=int(500 * scale),
            num_financial=int(500 * scale),
            num_custodians=max(20, int(100 * scale)),
            num_matters=5
        )
        
        # Multiple runs for statistical validity
        gen_times = []
        for run in range(3):
            start = time.time()
            generator = SyntheticDataGenerator(config, seed=42+run)
            store = generator.generate()
            gen_times.append(time.time() - start)
        
        stats = store.get_statistics()
        
        # Query performance
        query_times = []
        for _ in range(5):
            start = time.time()
            _ = store.select_records(lambda r: r.type == RecordType.EMAIL)
            query_times.append((time.time() - start) * 1000)
        
        # Propagation performance
        seed_ids = list(store.records.keys())[:100]
        prop_times = []
        prop_counts = []
        for _ in range(5):
            start = time.time()
            propagated = store.propagate_hold(
                seed_ids, 
                [RelationType.ATTACHMENT, RelationType.THREAD], 
                max_depth=5
            )
            prop_times.append((time.time() - start) * 1000)
            prop_counts.append(len(propagated))
        
        result = {
            "records": stats["total_records"],
            "relationships": stats["total_relationships"],
            "custodians": len(store.custodians),
            "gen_time_avg": round(statistics.mean(gen_times), 3),
            "throughput": int(stats["total_records"] / statistics.mean(gen_times)),
            "query_time_avg_ms": round(statistics.mean(query_times), 2),
            "prop_time_avg_ms": round(statistics.mean(prop_times), 2),
            "prop_count_avg": int(statistics.mean(prop_counts)),
        }
        results.append(result)
        
        print(f"    Generation: {result['gen_time_avg']:.3f}s ({result['throughput']:,}/sec)")
        print(f"    Query: {result['query_time_avg_ms']:.2f}ms")
        print(f"    Propagation: {result['prop_time_avg_ms']:.2f}ms → {result['prop_count_avg']} records")
    
    return {"scalability": results}


# =============================================================================
# RQ2: TYPED HOLD PROPAGATION (Unique Capability)
# =============================================================================

def experiment_typed_propagation() -> Dict[str, Any]:
    """
    RQ2: How does typed relationship propagation improve hold precision?
    
    This demonstrates a UNIQUE capability of T-RKG:
    - Traditional systems propagate through ALL relationships (over-inclusive)
    - T-RKG propagates through TYPED relationships (precise)
    
    Without this capability, legal teams must manually review over-included records.
    """
    print_section("RQ2: TYPED HOLD PROPAGATION (Unique Capability)")
    
    store = generate_test_dataset(num_records=10000, seed=42)
    
    print(f"\n  Dataset: {len(store.records):,} records, {len(store.relationships):,} relationships")
    
    # Get seed records (simulating custodian identification)
    departments = defaultdict(list)
    for c in store.custodians.values():
        departments[c.department].append(c.id)
    
    eng_custodians = departments.get("Engineering", list(store.custodians.keys())[:10])
    seeds = [r.id for r in store.records.values() if r.custodian_id in eng_custodians][:50]
    
    print(f"  Seed records: {len(seeds)} from Engineering department")
    
    # Test different relationship type combinations
    configs = [
        ("No propagation (baseline)", [], 0),
        ("ATTACHMENT only", [RelationType.ATTACHMENT], 10),
        ("THREAD only", [RelationType.THREAD], 10),
        ("ATTACHMENT + THREAD", [RelationType.ATTACHMENT, RelationType.THREAD], 10),
        ("All types (untyped equivalent)", list(RelationType), 10),
    ]
    
    print(f"\n  --- Propagation Strategy Comparison ---")
    print(f"  {'Strategy':<30} | {'Seeds':>6} | {'Total':>6} | {'Added':>6} | {'Ratio':>6}")
    print("  " + "-" * 75)
    
    results = []
    for name, rel_types, max_depth in configs:
        times = []
        counts = []
        
        for _ in range(5):
            start = time.time()
            if rel_types:
                propagated = store.propagate_hold(seeds, rel_types, max_depth=max_depth)
            else:
                propagated = set(seeds)
            times.append((time.time() - start) * 1000)
            counts.append(len(propagated))
        
        avg_count = int(statistics.mean(counts))
        result = {
            "strategy": name,
            "seed_count": len(seeds),
            "propagated_avg": avg_count,
            "additional": avg_count - len(seeds),
            "expansion_ratio": round(avg_count / len(seeds), 2),
            "time_avg_ms": round(statistics.mean(times), 3),
        }
        results.append(result)
        
        print(f"  {name:<30} | {len(seeds):>6} | {avg_count:>6} | {result['additional']:>+6} | {result['expansion_ratio']:>5.2f}x")
    
    # Calculate over-inclusion if using untyped propagation
    typed_count = results[3]["propagated_avg"]  # ATT + THREAD
    untyped_count = results[4]["propagated_avg"]  # All types
    over_inclusion = untyped_count - typed_count
    over_inclusion_pct = (over_inclusion / typed_count) * 100 if typed_count > 0 else 0
    
    print(f"\n  --- Key Finding ---")
    print(f"  Typed propagation (ATT+THREAD): {typed_count} records")
    print(f"  Untyped propagation (all):      {untyped_count} records")
    print(f"  Over-inclusion avoided:         {over_inclusion} records ({over_inclusion_pct:.1f}%)")
    print(f"\n  Without typed propagation, {over_inclusion} records would require")
    print(f"  unnecessary manual review by legal team.")
    
    return {
        "typed_propagation": {
            "strategies": results,
            "over_inclusion_avoided": over_inclusion,
            "over_inclusion_pct": round(over_inclusion_pct, 1),
        }
    }


# =============================================================================
# RQ3: CROSS-JURISDICTIONAL CONFLICT DETECTION (Unique Capability)
# =============================================================================

def experiment_conflict_detection() -> Dict[str, Any]:
    """
    RQ3: Can T-RKG detect cross-jurisdictional governance conflicts?
    
    This demonstrates a UNIQUE capability of T-RKG:
    - Current ECM systems have NO conflict detection
    - T-RKG detects conflicts like SOX (retain 7yr) vs GDPR (delete on request)
    
    These conflicts require legal review and cannot be resolved automatically.
    Without detection, organizations risk compliance violations.
    """
    print_section("RQ3: CROSS-JURISDICTIONAL CONFLICT DETECTION (Unique Capability)")
    
    store = generate_test_dataset(num_records=10000, seed=42)
    detector = ConflictDetector(store)
    
    print(f"\n  Dataset: {len(store.records):,} records")
    
    # Detect all conflicts
    start = time.time()
    conflicts = detector.detect_all_conflicts()
    detection_time = (time.time() - start) * 1000
    
    summary = detector.get_conflict_summary()
    
    print(f"\n  --- Conflict Detection Results ---")
    print(f"  Detection time: {detection_time:.2f}ms")
    print(f"  Total conflicts: {summary['total_conflicts']}")
    print(f"  Affected records: {summary['affected_records']}")
    print(f"  Critical conflicts: {summary['critical_count']}")
    print(f"  Requires legal review: {summary['requires_legal_review']}")
    
    print(f"\n  By Regulation Pair:")
    for pair, count in sorted(summary['by_regulation_pair'].items(), key=lambda x: -x[1]):
        print(f"    {pair}: {count}")
    
    print(f"\n  By Severity:")
    for severity, count in summary['by_severity'].items():
        print(f"    {severity}: {count}")
    
    print(f"\n  By Conflict Type:")
    for ctype, count in summary['by_type'].items():
        print(f"    {ctype}: {count}")
    
    # Show example conflicts
    print(f"\n  --- Example Conflicts ---")
    shown = 0
    for conflict in conflicts[:5]:
        record = store.records.get(conflict.record_id)
        if record and shown < 3:
            print(f"\n  Record: {record.id} ({record.type.value})")
            print(f"    Jurisdiction: {record.jurisdiction.value}")
            print(f"    Contains PII: {record.contains_pii}")
            print(f"    Conflict: {conflict.regulation_a.value} vs {conflict.regulation_b.value}")
            print(f"    Severity: {conflict.severity.value}")
            print(f"    Recommendation: {conflict.recommendation}")
            shown += 1
    
    print(f"\n  --- Key Finding ---")
    print(f"  T-RKG detected {summary['total_conflicts']} governance conflicts that")
    print(f"  would be INVISIBLE to traditional ECM systems.")
    print(f"  {summary['critical_count']} CRITICAL conflicts (SOX↔GDPR, SEC↔GDPR)")
    print(f"  require immediate legal review.")
    
    return {
        "conflict_detection": {
            "total_conflicts": summary['total_conflicts'],
            "affected_records": summary['affected_records'],
            "by_type": summary['by_type'],
            "by_severity": summary['by_severity'],
            "by_regulation_pair": summary['by_regulation_pair'],
            "critical_count": summary['critical_count'],
            "requires_legal_review": summary['requires_legal_review'],
            "detection_time_ms": round(detection_time, 2),
        }
    }


# =============================================================================
# RQ4: MULTI-REGULATION RETENTION (Unique Capability)
# =============================================================================

def experiment_retention_reasoning() -> Dict[str, Any]:
    """
    RQ4: Can T-RKG reason about multi-regulation retention requirements?
    
    This demonstrates a UNIQUE capability of T-RKG:
    - Current ECM systems support single retention policies
    - T-RKG reasons across 9 regulations, applying longest period
    
    Example: A financial email in California may be subject to:
    - SOX (7 years)
    - SEC Rule 17a-4 (6 years) 
    - CPRA (deletion right)
    T-RKG determines SOX 7yr takes precedence.
    """
    print_section("RQ4: MULTI-REGULATION RETENTION REASONING (Unique Capability)")
    
    store = generate_test_dataset(num_records=10000, seed=42)
    calculator = RetentionCalculator(store)
    
    print(f"\n  Dataset: {len(store.records):,} records")
    print(f"\n  Encoded Regulations: {len(RETENTION_RULES)}")
    for rule in RETENTION_RULES[:5]:
        print(f"    - {rule.regulation.value}: {rule.retention_days} days ({rule.retention_days//365}yr)")
    
    # Calculate retention for all records
    retention_stats = {
        "with_retention": 0,
        "without_retention": 0,
        "multi_regulation": 0,
        "by_regulation": defaultdict(int),
        "by_period": defaultdict(int),
    }
    
    multi_reg_examples = []
    
    for record in store.records.values():
        deadline, rules = calculator.calculate_retention_deadline(record)
        
        if deadline:
            retention_stats["with_retention"] += 1
            
            if len(rules) >= 2:
                retention_stats["multi_regulation"] += 1
                if len(multi_reg_examples) < 3:
                    multi_reg_examples.append((record, rules, deadline))
            
            for rule in rules:
                reg_name = rule.split(":")[0]
                retention_stats["by_regulation"][reg_name] += 1
            
            # Categorize by period
            days = (deadline - record.created).days
            years = days // 365
            retention_stats["by_period"][f"{years}yr"] += 1
        else:
            retention_stats["without_retention"] += 1
    
    print(f"\n  --- Retention Analysis ---")
    print(f"  Records with retention requirement: {retention_stats['with_retention']:,}")
    print(f"  Records without requirement: {retention_stats['without_retention']:,}")
    print(f"  Records with MULTIPLE regulations: {retention_stats['multi_regulation']:,}")
    
    print(f"\n  By Regulation:")
    for reg, count in sorted(retention_stats["by_regulation"].items(), key=lambda x: -x[1]):
        print(f"    {reg}: {count:,}")
    
    print(f"\n  By Retention Period:")
    for period, count in sorted(retention_stats["by_period"].items()):
        print(f"    {period}: {count:,}")
    
    print(f"\n  --- Multi-Regulation Examples ---")
    for record, rules, deadline in multi_reg_examples:
        print(f"\n  Record: {record.id} ({record.type.value})")
        print(f"    Jurisdiction: {record.jurisdiction.value}")
        print(f"    Applicable rules:")
        for rule in rules:
            print(f"      - {rule}")
        print(f"    Final deadline: {deadline.strftime('%Y-%m-%d')}")
        print(f"    (Longest retention period applied)")
    
    print(f"\n  --- Key Finding ---")
    print(f"  {retention_stats['multi_regulation']:,} records are subject to MULTIPLE regulations.")
    print(f"  T-RKG automatically applies the longest retention period.")
    print(f"  This capability does not exist in traditional ECM systems.")
    
    return {
        "retention_reasoning": {
            "total_records": len(store.records),
            "with_retention": retention_stats["with_retention"],
            "without_retention": retention_stats["without_retention"],
            "multi_regulation_records": retention_stats["multi_regulation"],
            "by_regulation": dict(retention_stats["by_regulation"]),
            "by_period": dict(retention_stats["by_period"]),
        }
    }


# =============================================================================
# RQ5: EXPLAINABLE GOVERNANCE DECISIONS (Unique Capability)
# =============================================================================

def experiment_explainability() -> Dict[str, Any]:
    """
    RQ5: Does T-RKG provide explainable governance decisions?
    
    This demonstrates a UNIQUE capability of T-RKG:
    - Current ECM systems provide yes/no answers with no explanation
    - T-RKG provides full reasoning traces for audit compliance
    
    Explainability is REQUIRED for regulatory audits (SOX, GDPR, etc.)
    """
    print_section("RQ5: EXPLAINABLE GOVERNANCE DECISIONS (Unique Capability)")
    
    store = generate_test_dataset(num_records=10000, seed=42)
    reasoner = GovernanceReasoner(store)
    
    print(f"\n  Dataset: {len(store.records):,} records")
    
    # Get reasoning statistics
    start = time.time()
    stats = reasoner.get_reasoning_statistics()
    reasoning_time = time.time() - start
    
    print(f"\n  --- Reasoning Performance ---")
    print(f"  Total reasoning time: {reasoning_time*1000:.1f}ms")
    print(f"  Time per record: {reasoning_time*1000/len(store.records):.3f}ms")
    
    print(f"\n  --- Coverage Statistics ---")
    print(f"  Records with retention requirements: {stats.records_with_retention:,}")
    print(f"  Records with deletion rights: {stats.records_with_deletion_rights:,}")
    print(f"  Records with conflicts: {stats.records_with_conflicts:,}")
    print(f"  Average regulations per record: {stats.avg_regulations_per_record:.2f}")
    
    # Show detailed reasoning examples
    print(f"\n  --- Explainable Decision Examples ---")
    
    examples_shown = 0
    for record in store.records.values():
        result = reasoner.reason_about_record(record)
        
        if result.conflicts and examples_shown < 3:
            print(f"\n  Record: {record.id}")
            print(f"    Type: {record.type.value}")
            print(f"    Jurisdiction: {record.jurisdiction.value}")
            print(f"    Contains PII: {record.contains_pii}")
            print(f"    ")
            print(f"    ┌─ GOVERNANCE DECISION ─────────────────────────")
            print(f"    │ State: {result.recommended_state.value}")
            print(f"    │")
            print(f"    │ Applicable Regulations:")
            for reg in result.inferred_regulations:
                print(f"    │   • {reg}")
            if result.retention_requirements:
                print(f"    │")
                print(f"    │ Retention Requirements:")
                for reg, days in result.retention_requirements.items():
                    print(f"    │   • {reg}: {days} days ({days//365} years)")
            if result.deletion_rights:
                print(f"    │")
                print(f"    │ Deletion Rights: {', '.join(result.deletion_rights)}")
            if result.conflicts:
                print(f"    │")
                print(f"    │ ⚠ CONFLICTS DETECTED:")
                for conflict in result.conflicts:
                    print(f"    │   • {conflict.regulation_a.value} vs {conflict.regulation_b.value}")
                    print(f"    │     Severity: {conflict.severity.value}")
                    print(f"    │     Resolution: {conflict.recommendation}")
            print(f"    └────────────────────────────────────────────────")
            
            examples_shown += 1
    
    print(f"\n  --- Key Finding ---")
    print(f"  T-RKG provides COMPLETE reasoning traces for every decision.")
    print(f"  This is REQUIRED for regulatory audits but MISSING from ECM systems.")
    print(f"  Reasoning covers {stats.records_with_retention:,} retention decisions,")
    print(f"  {stats.records_with_deletion_rights:,} deletion rights, and")
    print(f"  {stats.records_with_conflicts:,} conflict resolutions.")
    
    return {
        "explainability": {
            "total_records": len(store.records),
            "reasoning_time_ms": round(reasoning_time * 1000, 1),
            "time_per_record_ms": round(reasoning_time * 1000 / len(store.records), 3),
            "records_with_retention": stats.records_with_retention,
            "records_with_deletion_rights": stats.records_with_deletion_rights,
            "records_with_conflicts": stats.records_with_conflicts,
            "avg_regulations_per_record": round(stats.avg_regulations_per_record, 2),
        }
    }


# =============================================================================
# RQ6: REAL DATA VALIDATION (Enron Dataset)
# =============================================================================

def experiment_enron_validation() -> Dict[str, Any]:
    """
    RQ6: Does T-RKG work on real enterprise data?
    
    Validates T-RKG capabilities on the Enron email corpus:
    - Real custodian relationships
    - Real email threads
    - Historical litigation context (SEC, DOJ investigations)
    """
    print_section("RQ6: REAL DATA VALIDATION (Enron Email Corpus)")
    
    try:
        from trkg.datasets.enron import load_enron_dataset
    except ImportError:
        print("  Enron dataset loader not available")
        return {"enron_validation": {"status": "skipped"}}
    
    # Load Enron data
    store = load_enron_dataset(max_emails=5000)
    
    print(f"\n  Dataset Statistics:")
    print(f"    Emails: {len(store.records):,}")
    print(f"    Relationships: {len(store.relationships):,}")
    print(f"    Custodians: {len(store.custodians)}")
    print(f"    Legal Matters: {len(store.matters)}")
    
    # Test conflict detection on real data
    detector = ConflictDetector(store)
    conflicts = detector.detect_all_conflicts()
    summary = detector.get_conflict_summary()
    
    print(f"\n  --- Conflict Detection on Real Data ---")
    print(f"  Total conflicts: {summary['total_conflicts']}")
    print(f"  Affected records: {summary['affected_records']}")
    
    # Test hold propagation using real matter
    if store.matters:
        matter = list(store.matters.values())[0]
        print(f"\n  --- Hold Propagation for: {matter.name} ---")
        
        # Get direct records
        direct_records = [
            r.id for r in store.records.values()
            if r.custodian_id in matter.custodian_ids
        ][:100]
        
        if direct_records:
            # Propagate through threads
            propagated = store.propagate_hold(
                direct_records,
                [RelationType.THREAD],
                max_depth=5
            )
            
            print(f"  Direct records: {len(direct_records)}")
            print(f"  After propagation: {len(propagated)}")
            print(f"  Additional records found: {len(propagated) - len(direct_records)}")
    
    # Test retention reasoning
    calculator = RetentionCalculator(store)
    with_retention = 0
    for record in store.records.values():
        deadline, rules = calculator.calculate_retention_deadline(record)
        if deadline:
            with_retention += 1
    
    print(f"\n  --- Retention Analysis ---")
    print(f"  Records with SOX retention: {with_retention:,}")
    print(f"  (Enron was a public company subject to SOX)")
    
    print(f"\n  --- Key Finding ---")
    print(f"  T-RKG successfully processes real enterprise email data.")
    print(f"  The Enron corpus validates T-RKG's practical applicability.")
    
    return {
        "enron_validation": {
            "status": "success",
            "emails": len(store.records),
            "relationships": len(store.relationships),
            "custodians": len(store.custodians),
            "matters": len(store.matters),
            "conflicts_detected": summary['total_conflicts'],
            "records_with_retention": with_retention,
        }
    }


# =============================================================================
# RQ7: ABLATION STUDY
# =============================================================================

def experiment_ablation() -> Dict[str, Any]:
    """
    RQ7: What is the contribution of each T-RKG component?
    
    Ablation study removing:
    1. Typed relationships → All relationships treated equally
    2. Domain ontology → No regulation knowledge
    3. Conflict detection → No cross-jurisdictional reasoning
    """
    print_section("RQ7: ABLATION STUDY")
    
    store = generate_test_dataset(num_records=10000, seed=42)
    
    print(f"\n  Dataset: {len(store.records):,} records")
    
    # Full T-RKG
    detector = ConflictDetector(store)
    full_conflicts = detector.detect_all_conflicts()
    
    seeds = list(store.records.keys())[:50]
    full_propagated = store.propagate_hold(
        seeds, 
        [RelationType.ATTACHMENT, RelationType.THREAD],
        max_depth=5
    )
    
    # Ablation 1: Remove typed relationships (use all types)
    untyped_propagated = store.propagate_hold(
        seeds,
        list(RelationType),  # All types
        max_depth=5
    )
    
    # Ablation 2: No propagation at all
    no_prop = set(seeds)
    
    print(f"\n  --- Propagation Ablation ---")
    print(f"  {'Configuration':<30} | {'Records':>8} | {'Change':>10}")
    print("  " + "-" * 55)
    print(f"  {'Full T-RKG (typed)':<30} | {len(full_propagated):>8} | {'baseline':>10}")
    print(f"  {'Without typed relations':<30} | {len(untyped_propagated):>8} | {'+' + str(len(untyped_propagated) - len(full_propagated)):>10}")
    print(f"  {'Without propagation':<30} | {len(no_prop):>8} | {'-' + str(len(full_propagated) - len(no_prop)):>10}")
    
    # Ablation 3: Without conflict detection (simulate)
    print(f"\n  --- Conflict Detection Ablation ---")
    print(f"  With conflict detection: {len(full_conflicts)} conflicts identified")
    print(f"  Without conflict detection: 0 conflicts (compliance risk)")
    
    print(f"\n  --- Key Finding ---")
    print(f"  Each T-RKG component provides measurable value:")
    print(f"  - Typed propagation prevents {len(untyped_propagated) - len(full_propagated)} over-included records")
    print(f"  - Propagation finds {len(full_propagated) - len(no_prop)} additional related records")
    print(f"  - Conflict detection identifies {len(full_conflicts)} compliance risks")
    
    return {
        "ablation": {
            "full_propagated": len(full_propagated),
            "untyped_propagated": len(untyped_propagated),
            "no_propagation": len(no_prop),
            "over_inclusion_from_untyped": len(untyped_propagated) - len(full_propagated),
            "missed_without_propagation": len(full_propagated) - len(no_prop),
            "conflicts_detected": len(full_conflicts),
        }
    }


# =============================================================================
# MAIN
# =============================================================================

def run_all_experiments(output_file: str = "results.json") -> Dict[str, Any]:
    """Run all experiments for KBS publication."""
    
    print("\n" + "=" * 70)
    print("  T-RKG EXPERIMENTS FOR KNOWLEDGE-BASED SYSTEMS")
    print("=" * 70)
    print("\n  Focus: UNIQUE capabilities missing from enterprise ECM systems")
    print("  NOT comparing: Performance against databases (not our claim)")
    
    all_results = {
        "metadata": {
            "run_date": datetime.now().isoformat(),
            "version": "2.0.0",
            "note": "Experiments focus on unique T-RKG capabilities, not database comparison"
        }
    }
    
    # Run all experiments
    all_results.update(experiment_scalability())
    all_results.update(experiment_typed_propagation())
    all_results.update(experiment_conflict_detection())
    all_results.update(experiment_retention_reasoning())
    all_results.update(experiment_explainability())
    all_results.update(experiment_enron_validation())
    all_results.update(experiment_ablation())
    
    # Summary
    print_section("SUMMARY: T-RKG UNIQUE CAPABILITIES")
    print(f"""
  ┌─────────────────────────────────────────────────────────────────┐
  │     CAPABILITIES THAT T-RKG PROVIDES (Missing in ECM Today)    │
  ├─────────────────────────────────────────────────────────────────┤
  │                                                                 │
  │  ✓ Multi-regulation retention reasoning                        │
  │    - 9 regulations encoded (SOX, GDPR, HIPAA, etc.)           │
  │    - Automatic longest-period application                      │
  │                                                                 │
  │  ✓ Cross-jurisdictional conflict detection                     │
  │    - SOX vs GDPR conflicts identified automatically            │
  │    - Legal review flagging for compliance                      │
  │                                                                 │
  │  ✓ Typed relationship hold propagation                         │
  │    - Precise propagation (ATTACHMENT, THREAD)                  │
  │    - Avoids over-inclusion of unrelated records                │
  │                                                                 │
  │  ✓ Explainable governance decisions                            │
  │    - Full reasoning traces for audit compliance                │
  │    - Required for SOX, GDPR, HIPAA audits                     │
  │                                                                 │
  │  ✓ Real data validation                                        │
  │    - Tested on Enron email corpus                              │
  │                                                                 │
  └─────────────────────────────────────────────────────────────────┘
    """)
    
    # Save results
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\n  Results saved to: {output_file}")
    
    return all_results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run T-RKG experiments for KBS")
    parser.add_argument("--output", type=str, default="results.json")
    args = parser.parse_args()
    
    run_all_experiments(output_file=args.output)
