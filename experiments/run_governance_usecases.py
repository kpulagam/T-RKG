#!/usr/bin/env python3
"""
T-RKG Governance Use Case Experiments

Demonstrates the COMPLETE governance lifecycle:
1. Retention Management - Calculate and enforce retention periods
2. Legal Hold Management - Apply holds with relationship propagation
3. Disposition Management - Determine deletion eligibility with conflict resolution

These experiments prove T-RKG's value beyond just conflict detection.
"""

import json
import time
import statistics
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, Any, List, Set, Tuple
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trkg import (
    TRKGStore, Record, Matter, RecordType, RelationType, Jurisdiction,
    GovernanceState, Regulation,
    SyntheticDataGenerator, GeneratorConfig, generate_test_dataset,
    ConflictDetector, RetentionCalculator, GovernanceReasoner,
    RETENTION_RULES, DELETION_RIGHTS, CONFLICT_RULES
)


def print_section(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


# =============================================================================
# USE CASE 1: RETENTION MANAGEMENT
# =============================================================================

def experiment_retention_management() -> Dict[str, Any]:
    """
    USE CASE 1: Retention Period Management
    
    Demonstrates:
    - Calculating retention deadlines per regulation
    - Identifying records past retention
    - Handling multi-regulation retention (longest wins)
    - Cross-jurisdictional retention requirements
    """
    print_section("USE CASE 1: RETENTION MANAGEMENT")
    
    store = generate_test_dataset(num_records=10000, seed=42)
    calculator = RetentionCalculator(store)
    
    print(f"\n  Dataset: {len(store.records):,} records")
    
    # Calculate retention for all records
    retention_stats = {
        "with_deadline": 0,
        "no_deadline": 0,
        "by_regulation": defaultdict(int),
        "by_max_period": defaultdict(int),
        "past_retention": 0,
        "within_retention": 0,
    }
    
    now = datetime.now()
    records_past_retention = []
    records_with_conflicts = []
    
    for record in store.records.values():
        deadline, rules = calculator.calculate_retention_deadline(record)
        
        if deadline:
            retention_stats["with_deadline"] += 1
            
            # Track which regulations apply
            for rule in rules:
                reg_name = rule.split(":")[0]
                retention_stats["by_regulation"][reg_name] += 1
            
            # Track max retention period
            if deadline:
                days = (deadline - record.created).days
                years = days // 365
                retention_stats["by_max_period"][f"{years}yr"] += 1
            
            # Check if past retention
            if deadline < now:
                retention_stats["past_retention"] += 1
                records_past_retention.append(record)
            else:
                retention_stats["within_retention"] += 1
        else:
            retention_stats["no_deadline"] += 1
    
    print(f"\n  Retention Analysis:")
    print(f"    Records with retention requirement: {retention_stats['with_deadline']:,}")
    print(f"    Records without requirement: {retention_stats['no_deadline']:,}")
    print(f"    Records PAST retention: {retention_stats['past_retention']:,}")
    print(f"    Records WITHIN retention: {retention_stats['within_retention']:,}")
    
    print(f"\n  By Regulation:")
    for reg, count in sorted(retention_stats["by_regulation"].items(), key=lambda x: -x[1]):
        print(f"    {reg}: {count:,}")
    
    print(f"\n  By Maximum Retention Period:")
    for period, count in sorted(retention_stats["by_max_period"].items()):
        print(f"    {period}: {count:,}")
    
    # Demonstrate multi-regulation scenario
    print(f"\n  --- Multi-Regulation Example ---")
    # Find a record with multiple regulations
    for record in store.records.values():
        deadline, rules = calculator.calculate_retention_deadline(record)
        if len(rules) >= 2:
            print(f"    Record: {record.id} ({record.type.value})")
            print(f"    Jurisdiction: {record.jurisdiction.value}")
            print(f"    Applicable rules:")
            for rule in rules:
                print(f"      - {rule}")
            print(f"    Final deadline: {deadline.strftime('%Y-%m-%d') if deadline else 'None'}")
            print(f"    (Longest retention period wins)")
            break
    
    return {
        "retention_management": {
            "total_records": len(store.records),
            "with_retention_requirement": retention_stats["with_deadline"],
            "without_requirement": retention_stats["no_deadline"],
            "past_retention": retention_stats["past_retention"],
            "within_retention": retention_stats["within_retention"],
            "by_regulation": dict(retention_stats["by_regulation"]),
            "by_max_period": dict(retention_stats["by_max_period"]),
        }
    }


# =============================================================================
# USE CASE 2: LEGAL HOLD MANAGEMENT
# =============================================================================

def experiment_legal_hold_management() -> Dict[str, Any]:
    """
    USE CASE 2: Legal Hold with Relationship Propagation
    
    Demonstrates:
    - Creating a legal matter
    - Identifying custodian records
    - Propagating holds through relationships
    - Tracking propagation paths for audit
    - Hold vs Deletion conflicts
    """
    print_section("USE CASE 2: LEGAL HOLD MANAGEMENT")
    
    store = generate_test_dataset(num_records=10000, seed=42)
    
    print(f"\n  Dataset: {len(store.records):,} records, {len(store.relationships):,} relationships")
    
    # Create a realistic legal matter
    matter = Matter(
        id="matter_smith_v_acme",
        name="Smith v. Acme Corporation",
        description="Employment discrimination litigation",
        matter_type="LITIGATION",
        hold_start=datetime(2024, 1, 15),
        custodian_ids=[],  # Will identify below
        keywords=["performance", "review", "termination"],
        date_range_start=datetime(2022, 1, 1),
        date_range_end=datetime(2024, 1, 15),
    )
    store.add_matter(matter)
    
    # Step 1: Identify custodians (e.g., HR department + specific employees)
    hr_custodians = [c.id for c in store.custodians.values() 
                    if c.department in ["HR", "Legal", "Executive"]][:15]
    matter.custodian_ids = hr_custodians
    
    print(f"\n  Matter: {matter.name}")
    print(f"  Custodians identified: {len(hr_custodians)}")
    print(f"  Date range: {matter.date_range_start.strftime('%Y-%m-%d')} to {matter.date_range_end.strftime('%Y-%m-%d')}")
    
    # Step 2: Find directly relevant records (custodian + date range)
    direct_records = []
    for record in store.records.values():
        if record.custodian_id in hr_custodians:
            if matter.date_range_start <= record.created <= matter.date_range_end:
                direct_records.append(record.id)
    
    print(f"\n  Direct records (custodian + date range): {len(direct_records)}")
    
    # Step 3: Propagate through relationships
    print(f"\n  --- Hold Propagation Analysis ---")
    
    propagation_results = []
    
    # Test different propagation strategies
    strategies = [
        ("No propagation", [], 0),
        ("Attachments only", [RelationType.ATTACHMENT], 5),
        ("Attachments + Threads", [RelationType.ATTACHMENT, RelationType.THREAD], 5),
        ("All propagating types", [RelationType.ATTACHMENT, RelationType.THREAD, RelationType.DERIVATION], 5),
    ]
    
    for name, rel_types, max_depth in strategies:
        if rel_types:
            propagated = store.propagate_hold(direct_records, rel_types, max_depth=max_depth)
        else:
            propagated = set(direct_records)
        
        additional = len(propagated) - len(direct_records)
        
        result = {
            "strategy": name,
            "direct_records": len(direct_records),
            "total_after_propagation": len(propagated),
            "additional_records": additional,
            "expansion_ratio": round(len(propagated) / len(direct_records), 2) if direct_records else 0
        }
        propagation_results.append(result)
        
        print(f"    {name}:")
        print(f"      Direct: {len(direct_records)} → Total: {len(propagated)} (+{additional})")
    
    # Step 4: Apply the hold with best strategy
    best_strategy = [RelationType.ATTACHMENT, RelationType.THREAD]
    final_hold_set = store.propagate_hold(direct_records, best_strategy, max_depth=5)
    
    # Apply holds
    assignments = store.apply_hold(
        matter.id,
        list(final_hold_set),
        assignment_type="DIRECT"
    )
    
    print(f"\n  --- Hold Applied ---")
    print(f"    Records under hold: {len(assignments)}")
    
    # Step 5: Identify HOLD vs DELETION conflicts
    # Records under hold that also have GDPR deletion rights
    detector = ConflictDetector(store)
    hold_deletion_conflicts = []
    
    for record_id in final_hold_set:
        record = store.records[record_id]
        if record.contains_pii and record.jurisdiction in [
            Jurisdiction.EU, Jurisdiction.EU_DE, Jurisdiction.EU_FR, Jurisdiction.UK
        ]:
            hold_deletion_conflicts.append(record_id)
    
    print(f"\n  --- Hold vs Deletion Conflicts ---")
    print(f"    Records under hold with GDPR deletion rights: {len(hold_deletion_conflicts)}")
    print(f"    These cannot be deleted despite GDPR Art. 17 request")
    print(f"    Legal basis: Litigation hold exemption (GDPR Art. 17(3)(e))")
    
    # Step 6: Audit trail
    print(f"\n  --- Audit Trail ---")
    print(f"    Hold assignments logged: {len(store.audit_log)}")
    
    # Show sample propagation path
    for ha in store.hold_assignments.values():
        if ha.propagation_path:
            print(f"    Sample propagation: {' → '.join(ha.propagation_path[:3])}...")
            break
    
    return {
        "legal_hold_management": {
            "matter": {
                "id": matter.id,
                "name": matter.name,
                "custodians": len(hr_custodians),
                "date_range": f"{matter.date_range_start.date()} to {matter.date_range_end.date()}"
            },
            "direct_records": len(direct_records),
            "propagation_strategies": propagation_results,
            "final_hold_count": len(assignments),
            "hold_vs_deletion_conflicts": len(hold_deletion_conflicts),
            "audit_events": len(store.audit_log)
        }
    }


# =============================================================================
# USE CASE 3: DISPOSITION MANAGEMENT
# =============================================================================

def experiment_disposition_management() -> Dict[str, Any]:
    """
    USE CASE 3: Disposition (Deletion) Eligibility
    
    Demonstrates:
    - Identifying records eligible for deletion
    - Checking hold blocks
    - Checking retention blocks
    - Handling deletion rights (GDPR "must delete")
    - Conflict resolution for disposition
    """
    print_section("USE CASE 3: DISPOSITION MANAGEMENT")
    
    store = generate_test_dataset(num_records=10000, seed=42)
    calculator = RetentionCalculator(store)
    detector = ConflictDetector(store)
    
    print(f"\n  Dataset: {len(store.records):,} records")
    
    # Simulate: Some records are under hold
    # Apply hold to 5% of records
    hold_records = list(store.records.keys())[:500]
    store.apply_hold("active_litigation", hold_records)
    
    now = datetime.now()
    
    # Categorize all records for disposition
    disposition_analysis = {
        "eligible_for_deletion": [],      # Past retention, no hold, no conflict
        "blocked_by_hold": [],            # Under legal hold
        "blocked_by_retention": [],       # Still within retention period
        "must_delete_gdpr": [],           # GDPR deletion right, past retention
        "must_delete_blocked": [],        # GDPR deletion right, but blocked
        "conflict_requires_review": [],   # Has unresolved conflicts
    }
    
    for record in store.records.values():
        # Check if under hold
        is_under_hold = record.id in hold_records
        
        # Calculate retention
        deadline, rules = calculator.calculate_retention_deadline(record)
        past_retention = deadline is None or deadline < now
        
        # Check for deletion rights
        has_deletion_right = False
        if record.contains_pii:
            if record.jurisdiction in [Jurisdiction.EU, Jurisdiction.EU_DE, Jurisdiction.EU_FR, Jurisdiction.UK]:
                has_deletion_right = True  # GDPR
            elif record.jurisdiction == Jurisdiction.US_CA:
                has_deletion_right = True  # CPRA
        
        # Check for conflicts
        conflicts = detector.detect_conflicts_for_record(record)
        has_conflicts = len(conflicts) > 0
        
        # Categorize
        if is_under_hold:
            disposition_analysis["blocked_by_hold"].append(record.id)
            if has_deletion_right:
                disposition_analysis["must_delete_blocked"].append(record.id)
        elif not past_retention:
            disposition_analysis["blocked_by_retention"].append(record.id)
        elif has_deletion_right and past_retention:
            if has_conflicts:
                disposition_analysis["conflict_requires_review"].append(record.id)
            else:
                disposition_analysis["must_delete_gdpr"].append(record.id)
        elif past_retention and not has_conflicts:
            disposition_analysis["eligible_for_deletion"].append(record.id)
        elif has_conflicts:
            disposition_analysis["conflict_requires_review"].append(record.id)
    
    print(f"\n  Disposition Analysis:")
    print(f"    ✓ Eligible for deletion:     {len(disposition_analysis['eligible_for_deletion']):,}")
    print(f"    ✓ MUST delete (GDPR):        {len(disposition_analysis['must_delete_gdpr']):,}")
    print(f"    ✗ Blocked by HOLD:           {len(disposition_analysis['blocked_by_hold']):,}")
    print(f"    ✗ Blocked by RETENTION:      {len(disposition_analysis['blocked_by_retention']):,}")
    print(f"    ⚠ GDPR blocked by hold:      {len(disposition_analysis['must_delete_blocked']):,}")
    print(f"    ⚠ Requires legal review:     {len(disposition_analysis['conflict_requires_review']):,}")
    
    # Calculate actionable percentages
    total = len(store.records)
    can_delete = len(disposition_analysis["eligible_for_deletion"]) + len(disposition_analysis["must_delete_gdpr"])
    blocked = len(disposition_analysis["blocked_by_hold"]) + len(disposition_analysis["blocked_by_retention"])
    needs_review = len(disposition_analysis["conflict_requires_review"]) + len(disposition_analysis["must_delete_blocked"])
    
    print(f"\n  Summary:")
    print(f"    Can delete now:      {can_delete:,} ({can_delete/total*100:.1f}%)")
    print(f"    Blocked:             {blocked:,} ({blocked/total*100:.1f}%)")
    print(f"    Needs legal review:  {needs_review:,} ({needs_review/total*100:.1f}%)")
    
    # Demonstrate disposition decision for sample records
    print(f"\n  --- Sample Disposition Decisions ---")
    
    samples = [
        ("Eligible for deletion", disposition_analysis["eligible_for_deletion"]),
        ("MUST delete (GDPR)", disposition_analysis["must_delete_gdpr"]),
        ("Blocked by hold", disposition_analysis["blocked_by_hold"]),
        ("GDPR blocked by hold", disposition_analysis["must_delete_blocked"]),
    ]
    
    for category, record_ids in samples:
        if record_ids:
            record = store.records[record_ids[0]]
            deadline, rules = calculator.calculate_retention_deadline(record)
            print(f"\n    {category}:")
            print(f"      Record: {record.id} ({record.type.value})")
            print(f"      Jurisdiction: {record.jurisdiction.value}")
            print(f"      Contains PII: {record.contains_pii}")
            print(f"      Created: {record.created.strftime('%Y-%m-%d')}")
            if deadline:
                print(f"      Retention deadline: {deadline.strftime('%Y-%m-%d')}")
            print(f"      Under hold: {record.id in hold_records}")
    
    return {
        "disposition_management": {
            "total_records": total,
            "eligible_for_deletion": len(disposition_analysis["eligible_for_deletion"]),
            "must_delete_gdpr": len(disposition_analysis["must_delete_gdpr"]),
            "blocked_by_hold": len(disposition_analysis["blocked_by_hold"]),
            "blocked_by_retention": len(disposition_analysis["blocked_by_retention"]),
            "gdpr_blocked_by_hold": len(disposition_analysis["must_delete_blocked"]),
            "requires_legal_review": len(disposition_analysis["conflict_requires_review"]),
            "summary": {
                "can_delete_pct": round(can_delete/total*100, 1),
                "blocked_pct": round(blocked/total*100, 1),
                "needs_review_pct": round(needs_review/total*100, 1)
            }
        }
    }


# =============================================================================
# USE CASE 4: COMPLETE GOVERNANCE DECISION
# =============================================================================

def experiment_governance_decision() -> Dict[str, Any]:
    """
    USE CASE 4: Complete Governance Decision with Explainability
    
    Demonstrates:
    - Full governance state determination
    - Explainable decisions (why is record in this state?)
    - Conflict resolution recommendations
    - Audit-ready decision documentation
    """
    print_section("USE CASE 4: GOVERNANCE DECISION & EXPLAINABILITY")
    
    store = generate_test_dataset(num_records=10000, seed=42)
    reasoner = GovernanceReasoner(store)
    
    print(f"\n  Dataset: {len(store.records):,} records")
    
    # Get full reasoning for all records
    start = time.time()
    stats = reasoner.get_reasoning_statistics()
    reasoning_time = time.time() - start
    
    print(f"\n  Reasoning Statistics:")
    print(f"    Time: {reasoning_time*1000:.1f}ms ({reasoning_time*1000/len(store.records):.3f}ms per record)")
    print(f"    Records with retention: {stats.records_with_retention:,}")
    print(f"    Records with deletion rights: {stats.records_with_deletion_rights:,}")
    print(f"    Records with conflicts: {stats.records_with_conflicts:,}")
    
    # Show governance decision examples
    print(f"\n  --- Sample Governance Decisions with Explainability ---")
    
    # Find interesting examples
    examples_shown = 0
    for record in store.records.values():
        result = reasoner.reason_about_record(record)
        
        # Show records with conflicts
        if result.conflicts and examples_shown < 3:
            print(f"\n  Record: {record.id}")
            print(f"    Type: {record.type.value}")
            print(f"    Jurisdiction: {record.jurisdiction.value}")
            print(f"    Contains PII: {record.contains_pii}")
            print(f"    ")
            print(f"    GOVERNANCE DECISION: {result.recommended_state.value}")
            print(f"    ")
            print(f"    Reasoning Trace:")
            for trace in result.reasoning_trace:
                print(f"      • {trace}")
            print(f"    ")
            print(f"    Applicable Regulations: {', '.join(result.inferred_regulations)}")
            if result.retention_requirements:
                print(f"    Retention Requirements:")
                for reg, days in result.retention_requirements.items():
                    print(f"      • {reg}: {days} days ({days//365} years)")
            if result.deletion_rights:
                print(f"    Deletion Rights: {', '.join(result.deletion_rights)}")
            print(f"    ")
            print(f"    CONFLICTS DETECTED: {len(result.conflicts)}")
            for conflict in result.conflicts:
                print(f"      ⚠ {conflict.regulation_a.value} vs {conflict.regulation_b.value}")
                print(f"        Type: {conflict.conflict_type.value}")
                print(f"        Severity: {conflict.severity.value}")
                print(f"        Recommendation: {conflict.recommendation}")
            
            examples_shown += 1
    
    # Aggregate governance states
    state_distribution = defaultdict(int)
    for record in store.records.values():
        result = reasoner.reason_about_record(record)
        state_distribution[result.recommended_state.value] += 1
    
    print(f"\n  --- Recommended Governance States ---")
    for state, count in sorted(state_distribution.items(), key=lambda x: -x[1]):
        pct = count / len(store.records) * 100
        print(f"    {state}: {count:,} ({pct:.1f}%)")
    
    return {
        "governance_decision": {
            "total_records": len(store.records),
            "reasoning_time_ms": round(reasoning_time * 1000, 1),
            "records_with_retention": stats.records_with_retention,
            "records_with_deletion_rights": stats.records_with_deletion_rights,
            "records_with_conflicts": stats.records_with_conflicts,
            "state_distribution": dict(state_distribution),
            "avg_regulations_per_record": stats.avg_regulations_per_record
        }
    }


# =============================================================================
# MAIN
# =============================================================================

def run_all_governance_experiments(output_file: str = None) -> Dict[str, Any]:
    """Run all governance use case experiments."""
    
    print("\n" + "=" * 70)
    print("  T-RKG GOVERNANCE USE CASE EXPERIMENTS")
    print("=" * 70)
    
    all_results = {
        "metadata": {
            "run_date": datetime.now().isoformat(),
            "description": "Complete governance lifecycle experiments"
        }
    }
    
    # Run all use case experiments
    all_results.update(experiment_retention_management())
    all_results.update(experiment_legal_hold_management())
    all_results.update(experiment_disposition_management())
    all_results.update(experiment_governance_decision())
    
    # Summary
    print_section("GOVERNANCE USE CASES SUMMARY")
    print(f"""
  ┌─────────────────────────────────────────────────────────────────┐
  │              T-RKG GOVERNANCE CAPABILITIES                      │
  ├─────────────────────────────────────────────────────────────────┤
  │                                                                 │
  │  USE CASE 1: RETENTION MANAGEMENT                               │
  │    • Multi-regulation retention calculation                     │
  │    • Longest retention period enforcement                       │
  │    • Cross-jurisdictional retention (SOX + HGB)                │
  │                                                                 │
  │  USE CASE 2: LEGAL HOLD MANAGEMENT                              │
  │    • Custodian-based record identification                      │
  │    • Relationship-aware hold propagation                        │
  │    • Hold vs deletion conflict detection                        │
  │    • Audit trail for compliance                                 │
  │                                                                 │
  │  USE CASE 3: DISPOSITION MANAGEMENT                             │
  │    • Deletion eligibility determination                         │
  │    • Hold/retention block checking                              │
  │    • GDPR "must delete" identification                          │
  │    • Conflict resolution workflow                               │
  │                                                                 │
  │  USE CASE 4: GOVERNANCE DECISION                                │
  │    • Complete state determination                               │
  │    • Explainable reasoning traces                               │
  │    • Audit-ready documentation                                  │
  │                                                                 │
  └─────────────────────────────────────────────────────────────────┘
    """)
    
    if output_file:
        with open(output_file, "w") as f:
            json.dump(all_results, f, indent=2, default=str)
        print(f"\n  Results saved to: {output_file}")
    
    return all_results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run T-RKG governance experiments")
    parser.add_argument("--output", type=str, default="governance_results.json")
    args = parser.parse_args()
    
    run_all_governance_experiments(output_file=args.output)
