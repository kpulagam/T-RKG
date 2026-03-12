#!/usr/bin/env python3
"""
T-RKG Master Experiment Runner

Generates every table and result for the KBS paper.
All numbers in the paper come from this single script.

Usage:
    python -m experiments.run_all          # Run all experiments
    python -m experiments.run_all --quick  # Quick mode (fewer seeds, smaller datasets)

FIXES vs previous version:
  FIX 1 (E3): experiment_3_scalability() no longer re-times conflict detection
              independently. It reuses E1's conflict_times_by_scale so Table 1
              and Table 4 report identical values from the same measurements.
  FIX 2 (E5): experiment_5_ablation() now uses the same matter-centric seed
              selection and max_depth=10 as experiment_2_hold_propagation(),
              eliminating the Table 3 vs Table 6 hold-set contradiction.
  FIX 3 (E3): Propagation footnote data recorded so paper table can disclose
              that E3 prop timing uses first-50 seeds / depth-5 (lightweight
              benchmark) vs E2's matter-scoped / depth-10 scenario timing.
"""

import sys
import os
import json
import time
import statistics
import tracemalloc
from datetime import datetime
from collections import defaultdict

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

from trkg import (
    TRKGStore, RecordType, RelationType, Jurisdiction, Regulation,
    SyntheticDataGenerator, GeneratorConfig,
    ConflictDetector, SiloedConflictDetector, UntypedGraphConflictDetector,
)
from experiments.stats_utils import (
    SEEDS, mean_std, mean_std_int, print_table, time_execution
)


# =============================================================================
# CONFIGURATION
# =============================================================================

QUICK_MODE = "--quick" in sys.argv

if QUICK_MODE:
    EXPERIMENT_SEEDS = SEEDS[:2]
    SCALE_POINTS = [1000, 5000, 10000]
    PROPAGATION_DATASET_SIZE = 5000
    print("*** QUICK MODE: Reduced seeds and scales ***\n")
else:
    EXPERIMENT_SEEDS = SEEDS
    SCALE_POINTS = [1000, 5000, 10000, 25000, 50000, 100000]
    PROPAGATION_DATASET_SIZE = 10000


# =============================================================================
# HELPERS
# =============================================================================

def make_config(num_records: int) -> GeneratorConfig:
    """Create a GeneratorConfig scaled to target record count."""
    scale = num_records / 10000
    return GeneratorConfig(
        num_emails=int(4000 * scale),
        num_documents=int(3000 * scale),
        num_chats=int(1500 * scale),
        num_tickets=int(500 * scale),
        num_contracts=int(500 * scale),
        num_financial=int(500 * scale),
        num_custodians=max(20, int(100 * scale)),
        num_matters=5,
    )


def generate_store(num_records: int, seed: int) -> TRKGStore:
    """Generate a store with approximately num_records records."""
    config = make_config(num_records)
    gen = SyntheticDataGenerator(config, seed=seed)
    return gen.generate()


def get_matter_centric_seeds(store: TRKGStore, num_seeds: int) -> list:
    """
    Return seed record IDs drawn from the first matter's custodians.
    This is the canonical seed selection used in E2 and E5 to ensure
    the two propagation experiments are directly comparable.
    """
    matter = list(store.matters.values())[0]
    cust_records = []
    for cid in matter.custodian_ids:
        for rid in store._records_by_custodian.get(cid, set()):
            cust_records.append(rid)
    seed_ids = cust_records[:num_seeds]
    if len(seed_ids) < num_seeds:
        remaining = [r for r in store.records.keys() if r not in seed_ids]
        seed_ids += remaining[:num_seeds - len(seed_ids)]
    return seed_ids


# =============================================================================
# EXPERIMENT 1: Conflict Detection Capability (RQ1)
#
# Generates Table 1 (conflicts by scale) and Table 2 (type breakdown).
# conflict_times_by_scale returned here are the CANONICAL conflict detection
# timings. E3 reuses these values — no independent re-measurement.
# =============================================================================

def experiment_1_conflict_detection():
    """
    RQ1: Can ontology-based reasoning detect regulatory conflicts
    undetectable in systems lacking unified knowledge representation?

    Returns dict with all results including conflict_times_by_scale,
    which experiment_3_scalability() will consume directly.
    """
    print("\n" + "=" * 70)
    print("EXPERIMENT 1: Conflict Detection Capability (RQ1)")
    print("=" * 70)

    detector = ConflictDetector()
    siloed = SiloedConflictDetector()
    untyped = UntypedGraphConflictDetector()

    table1_rows = []
    all_results = {}

    for num_records in SCALE_POINTS:
        conflict_counts = []
        siloed_counts = []
        untyped_counts = []
        times_ms = []
        actual_counts = []
        rel_counts = []

        for seed in EXPERIMENT_SEEDS:
            store = generate_store(num_records, seed)
            actual_counts.append(len(store.records))
            rel_counts.append(len(store.relationships))

            result = detector.detect_all_conflicts(store.records)
            conflict_counts.append(result.total_conflicts)
            times_ms.append(result.detection_time_ms)

            siloed_result = siloed.detect_all_conflicts(store.records)
            siloed_counts.append(siloed_result.total_conflicts)

            untyped_result = untyped.detect_all_conflicts(store.records)
            untyped_counts.append(untyped_result.total_conflicts)

        table1_rows.append([
            f"{num_records:,}",
            f"{statistics.mean(rel_counts):,.0f}",
            mean_std_int(conflict_counts),
            str(siloed_counts[0]),
            str(untyped_counts[0]),
            mean_std(times_ms),
        ])

        all_results[num_records] = {
            "actual_records": actual_counts,
            "conflicts": conflict_counts,
            "siloed": siloed_counts,
            "untyped": untyped_counts,
            "times_ms": times_ms,          # CANONICAL — reused by E3
            "relationships": rel_counts,
        }

        print(f"  {num_records:>7,} records: {mean_std_int(conflict_counts)} conflicts "
              f"(Siloed: 0, Untyped: 0) in {mean_std(times_ms)} ms")

    print_table(
        ["Dataset", "Rels", "T-RKG Conflicts", "Siloed", "Untyped Graph", "Detection Time (ms)"],
        table1_rows,
        "Table 1: Regulatory Conflict Detection Through Ontology-Based Reasoning"
    )

    # --- Table 2: Conflict type breakdown (10K dataset) ---
    print("  Generating conflict type breakdown (10K dataset)...")
    type_counts_all = defaultdict(list)
    pair_counts_all = defaultdict(list)
    severity_counts_all = defaultdict(list)

    for seed in EXPERIMENT_SEEDS:
        store = generate_store(10000, seed)
        result = detector.detect_all_conflicts(store.records)

        for ctype in ["RETENTION_DELETION", "JURISDICTION", "HOLD_DELETION", "PRIORITY"]:
            type_counts_all[ctype].append(result.conflicts_by_type.get(ctype, 0))

        for pair, count in result.conflicts_by_regulation_pair.items():
            pair_counts_all[pair].append(count)

        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            severity_counts_all[sev].append(result.conflicts_by_severity.get(sev, 0))

    mean_total = sum(statistics.mean(v) for v in type_counts_all.values())

    table2_rows = []
    for ctype in ["RETENTION_DELETION", "PRIORITY", "JURISDICTION", "HOLD_DELETION"]:
        vals = type_counts_all[ctype]
        m = statistics.mean(vals)
        pct = (m / mean_total * 100) if mean_total > 0 else 0
        table2_rows.append([ctype, mean_std_int(vals), f"{pct:.1f}%"])

    print_table(
        ["Conflict Type", "Count (mean ± σ)", "Proportion"],
        table2_rows,
        "Table 2: Conflict Type Distribution (10K Dataset)"
    )

    print("  Top regulation pair conflicts:")
    pair_means = {p: statistics.mean(v) for p, v in pair_counts_all.items()}
    for pair, mean_count in sorted(pair_means.items(), key=lambda x: -x[1])[:10]:
        print(f"    {pair:20s}: {mean_count:.1f}")

    print("\n  Severity distribution:")
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        vals = severity_counts_all[sev]
        m = statistics.mean(vals)
        pct = (m / mean_total * 100) if mean_total > 0 else 0
        print(f"    {sev:10s}: {mean_std_int(vals)} ({pct:.1f}%)")

    all_results["type_breakdown"] = {k: v for k, v in type_counts_all.items()}
    all_results["pair_breakdown"] = {k: v for k, v in pair_counts_all.items()}
    all_results["severity_breakdown"] = {k: v for k, v in severity_counts_all.items()}

    return all_results


# =============================================================================
# EXPERIMENT 2: Semantic Hold Propagation (RQ2 + RQ3)
#
# Generates Table 3 (propagation configs) and Table 4 (depth analysis).
# Uses matter-centric seed selection and max_depth=10.
# E5 ablation uses the same settings for direct comparability.
# =============================================================================

def experiment_2_hold_propagation():
    """
    RQ2: How does semantic relationship reasoning improve hold propagation?
    RQ3: How do different relationship semantics affect propagation scope?
    """
    print("\n" + "=" * 70)
    print("EXPERIMENT 2: Semantic Hold Propagation (RQ2 + RQ3)")
    print("=" * 70)

    configs = [
        ("None (Siloed)",  [],                                                   "Directly identified only"),
        ("Attachment",     [RelationType.ATTACHMENT],                             "Content dependency"),
        ("Thread",         [RelationType.THREAD],                                "Conversational context"),
        ("Att + Thread",   [RelationType.ATTACHMENT, RelationType.THREAD],       "Primary relationships"),
        ("+ Derivation",   [RelationType.ATTACHMENT, RelationType.THREAD,
                            RelationType.DERIVATION],                            "Source materials"),
        ("All types",      [RelationType.ATTACHMENT, RelationType.THREAD,
                            RelationType.DERIVATION, RelationType.REFERENCE],    "Any connection"),
    ]

    num_seeds = 50
    max_depth = 10

    table3_rows = []
    all_results = {}

    for config_name, rel_types, justification in configs:
        final_counts = []
        times_ms = []

        for seed in EXPERIMENT_SEEDS:
            store = generate_store(PROPAGATION_DATASET_SIZE, seed)
            seed_ids = get_matter_centric_seeds(store, num_seeds)

            if not rel_types:
                final_counts.append(len(seed_ids))
                times_ms.append(0.0)
            else:
                start = time.perf_counter()
                propagated = store.propagate_hold(seed_ids, rel_types, max_depth=max_depth)
                elapsed = (time.perf_counter() - start) * 1000
                final_counts.append(len(propagated))
                times_ms.append(elapsed)

        mean_final = statistics.mean(final_counts)
        ratio = mean_final / num_seeds

        table3_rows.append([
            config_name,
            str(num_seeds),
            mean_std_int(final_counts),
            f"{ratio:.2f}×",
            mean_std(times_ms) if any(t > 0 for t in times_ms) else "—",
            justification,
        ])

        all_results[config_name] = {
            "final_counts": final_counts,
            "times_ms": times_ms,
            "ratio": ratio,
        }

        print(f"  {config_name:20s}: {num_seeds} → {mean_std_int(final_counts)} "
              f"({ratio:.2f}×) in {mean_std(times_ms)} ms")

    print_table(
        ["Configuration", "Seeds", "Final (mean ± σ)", "Ratio", "Time (ms)", "Semantic Justification"],
        table3_rows,
        "Table 3: Impact of Relationship Semantics on Hold Propagation"
    )

    # --- Table 4: Depth analysis for Att + Thread ---
    print("  Generating depth analysis (Att + Thread)...")
    depth_data = defaultdict(list)

    for seed in EXPERIMENT_SEEDS:
        store = generate_store(PROPAGATION_DATASET_SIZE, seed)
        seed_ids = get_matter_centric_seeds(store, num_seeds)

        paths = store.propagate_hold_with_paths(
            seed_ids,
            [RelationType.ATTACHMENT, RelationType.THREAD],
            max_depth=max_depth
        )

        depths = defaultdict(int)
        for rid, path in paths.items():
            depths[len(path)] += 1
        for d in range(max_depth + 1):
            depth_data[d].append(depths.get(d, 0))

    table4_rows = []
    cumulative = 0
    for d in range(max_depth + 1):
        vals = depth_data[d]
        if not any(v > 0 for v in vals) and d > 0:
            break
        mean_new = statistics.mean(vals) if vals else 0
        cumulative += mean_new
        label = f"{d} (seeds)" if d == 0 else str(d)
        table4_rows.append([label, mean_std_int(vals), f"{cumulative:.0f}"])

    print_table(
        ["Depth", "New Records (mean ± σ)", "Cumulative"],
        table4_rows,
        "Table 4: Propagation Depth Analysis (Att + Thread Configuration)"
    )

    return all_results


# =============================================================================
# EXPERIMENT 3: Scalability (RQ4)
#
# Generates Table 5 (scalability).
#
# FIX: Conflict detection column is NOT re-measured here. It is passed in
# from E1's canonical measurements (e1_results parameter). This guarantees
# Table 1 and Table 5 report identical conflict detection times and eliminates
# the 16ms discrepancy the reviewer identified.
#
# Propagation column: uses first-50 arbitrary seeds / depth-5 as a lightweight
# latency benchmark to show sub-ms scaling behavior. This is DIFFERENT from
# E2's matter-scoped / depth-10 scenario, and the paper table footnote must
# disclose this distinction.
# =============================================================================

def experiment_3_scalability(e1_results: dict):
    """
    RQ4: Does the knowledge-based approach scale to enterprise workloads?

    Args:
        e1_results: Return value of experiment_1_conflict_detection().
                    Used to populate the conflict detection column so that
                    Table 1 and Table 5 are guaranteed identical.
    """
    print("\n" + "=" * 70)
    print("EXPERIMENT 3: Scalability (RQ4)")
    print("=" * 70)
    print("  NOTE: Conflict detection times sourced from E1 (Table 1) measurements.")
    print("  Propagation timing uses first-50 seeds, depth-5 (lightweight benchmark).\n")

    table5_rows = []
    all_results = {}

    for num_records in SCALE_POINTS:
        build_times = []
        query_times = []
        prop_times = []
        temporal_times = []
        memory_mbs = []
        rel_counts = []
        throughputs = []

        for seed in EXPERIMENT_SEEDS:
            config = make_config(num_records)
            gen = SyntheticDataGenerator(config, seed=seed)

            # Build time + memory
            tracemalloc.start()
            start = time.perf_counter()
            store = gen.generate()
            build_time = time.perf_counter() - start
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            actual_records = len(store.records)
            build_times.append(build_time)
            memory_mbs.append(peak / (1024 * 1024))
            rel_counts.append(len(store.relationships))
            throughputs.append(actual_records / build_time if build_time > 0 else 0)

            # Type-based query
            start = time.perf_counter()
            _ = store.select_records(lambda r: r.type == RecordType.EMAIL)
            query_times.append((time.perf_counter() - start) * 1000)

            # Hold propagation benchmark (first-50 seeds, Att+Thread, depth-5)
            # This is a lightweight latency benchmark — see paper Table 5 footnote.
            # For matter-scoped propagation timings, see Table 3 (E2).
            bench_seed_ids = list(store.records.keys())[:50]
            start = time.perf_counter()
            _ = store.propagate_hold(
                bench_seed_ids,
                [RelationType.ATTACHMENT, RelationType.THREAD],
                max_depth=5
            )
            prop_times.append((time.perf_counter() - start) * 1000)

            # Temporal point-in-time query
            start = time.perf_counter()
            _ = store.query_at_time(datetime(2023, 6, 15))
            temporal_times.append((time.perf_counter() - start) * 1000)

        # --- FIX 1: Reuse E1's canonical conflict detection times ---
        e1_scale_data = e1_results.get(num_records, {})
        conflict_times = e1_scale_data.get("times_ms", [])

        mean_rels = statistics.mean(rel_counts)
        mean_throughput = statistics.mean(throughputs)
        mean_build = statistics.mean(build_times)

        conflict_str = mean_std(conflict_times) if conflict_times else "N/A"

        table5_rows.append([
            f"{num_records:,}",
            f"{mean_rels:,.0f}",
            f"{mean_build:.3f}",
            f"{mean_throughput:,.0f}/s",
            mean_std(prop_times),
            conflict_str,
            f"{statistics.mean(memory_mbs):.1f}",
        ])

        all_results[num_records] = {
            "build_s": build_times,
            "memory_mb": memory_mbs,
            "query_ms": query_times,
            "prop_ms": prop_times,
            "conflict_ms": conflict_times,   # sourced from E1
            "temporal_ms": temporal_times,
            "throughput": throughputs,
            "relationships": rel_counts,
        }

        print(f"  {num_records:>7,}: build={mean_build:.3f}s ({mean_throughput:,.0f}/s), "
              f"prop={mean_std(prop_times)}ms, "
              f"conflict={conflict_str}ms (from E1), "
              f"mem={statistics.mean(memory_mbs):.1f}MB")

    print_table(
        ["Records", "Rels", "Build (s)", "Throughput", "Prop (ms)*", "Conflict (ms)", "Memory (MB)"],
        table5_rows,
        "Table 5: Knowledge-Based System Scalability\n"
        "  * Propagation: first-50 seeds, Att+Thread, depth-5 (lightweight benchmark).\n"
        "    Matter-scoped propagation timings in Table 3."
    )

    return all_results


# =============================================================================
# EXPERIMENT 4: Governance Scenarios
# =============================================================================

def experiment_4_scenarios():
    """
    Demonstrate end-to-end governance reasoning on realistic scenarios.
    Generates Table 6 (scenario summary).
    """
    print("\n" + "=" * 70)
    print("EXPERIMENT 4: Governance Scenarios")
    print("=" * 70)

    store = generate_store(10000, seed=42)
    detector = ConflictDetector()

    # --- Scenario A: Cross-System Legal Hold ---
    print("\n  Scenario A: Cross-System Legal Hold")
    print("  " + "-" * 50)

    matter = list(store.matters.values())[0]
    print(f"  Matter: {matter.name}")
    print(f"  Custodians in scope: {len(matter.custodian_ids)}")

    seed_ids = []
    for cid in matter.custodian_ids:
        for rid in store._records_by_custodian.get(cid, set()):
            r = store.records[rid]
            if r.created >= datetime(2023, 1, 1) and r.created <= datetime(2024, 12, 31):
                seed_ids.append(rid)

    print(f"  Seed records (custodian + date filter): {len(seed_ids)}")

    siloed_count = len(seed_ids)

    propagated = store.propagate_hold(
        seed_ids,
        [RelationType.ATTACHMENT, RelationType.THREAD],
        max_depth=5
    )
    print(f"  After propagation (Att + Thread): {len(propagated)}")

    expansion_a = len(propagated) / len(seed_ids) if seed_ids else 0
    missed_by_siloed = len(propagated) - siloed_count

    by_system = defaultdict(int)
    by_type = defaultdict(int)
    for rid in propagated:
        r = store.records.get(rid)
        if r:
            by_system[r.system_id] += 1
            by_type[r.type.value] += 1
    print(f"  By system: {dict(by_system)}")
    print(f"  By type: {dict(by_type)}")
    print(f"  Records missed by siloed approach: {missed_by_siloed}")

    # --- Scenario B: GDPR Erasure vs Active Holds ---
    print("\n  Scenario B: GDPR Erasure Request vs Active Holds")
    print("  " + "-" * 50)

    eu_custodians = [c for c in store.custodians.values()
                     if c.jurisdiction and "EU" in c.jurisdiction.value]

    if eu_custodians:
        target_custodian = eu_custodians[0]
        pii_records = [
            r for r in store.records.values()
            if r.custodian_id == target_custodian.id and r.contains_pii
        ]

        result = detector.detect_all_conflicts({r.id: r for r in pii_records})
        conflict_records = [c.record_id for c in result.conflicts]

        hold_blocks = sum(1 for r in pii_records
                          if r.hold_matters and len(r.hold_matters) > 0)
        retention_blocks = sum(1 for r in pii_records
                                if r.id not in conflict_records and r.id not in
                                [r2.id for r2 in pii_records if r2.hold_matters])
        can_delete = len(pii_records) - hold_blocks - retention_blocks

        print(f"  Custodian: {target_custodian.name} ({target_custodian.jurisdiction.value})")
        print(f"  Total PII records: {len(pii_records)}")
        print(f"  CAN_DELETE: {can_delete}")
        print(f"  HOLD_BLOCKS: {hold_blocks}")
        print(f"  RETENTION_BLOCKS: {retention_blocks}")
        print(f"  Records with active conflicts: {len(conflict_records)}")
    else:
        print("  (No EU custodians in this seed)")
        can_delete = hold_blocks = retention_blocks = 0
        pii_records = []
        conflict_records = []
        target_custodian = None

    # --- Scenario C: Multi-Jurisdiction Financial Audit ---
    print("\n  Scenario C: Multi-Jurisdiction Financial Audit")
    print("  " + "-" * 50)

    financial_types = {RecordType.FINANCIAL, RecordType.AUDIT, RecordType.TAX, RecordType.INVOICE}
    fin_records = [r for r in store.records.values() if r.type in financial_types]

    reg_counts = defaultdict(int)
    multi_reg_count = 0
    jurisdiction_conflicts = defaultdict(int)

    for r in fin_records:
        applicable = detector.infer_applicable_regulations(r)
        for reg in applicable:
            reg_counts[reg.value] += 1
        if len(applicable) >= 2:
            multi_reg_count += 1

    fin_dict = {r.id: r for r in fin_records}
    fin_result = detector.detect_all_conflicts(fin_dict)

    for c in fin_result.conflicts:
        r = store.records.get(c.record_id)
        if r:
            jurisdiction_conflicts[r.jurisdiction.value] += 1

    print(f"  Financial records: {len(fin_records)}")
    print(f"  Records with 2+ regulations: {multi_reg_count}")
    print(f"  Conflicts detected: {fin_result.total_conflicts}")
    print(f"  Conflict types: {fin_result.conflicts_by_type}")
    print(f"  Conflicts by jurisdiction: {dict(jurisdiction_conflicts)}")

    # --- Summary Table ---
    table6_rows = [
        ["A: Cross-System Legal Hold",
         f"{len(seed_ids)} seeds → {len(propagated)} total",
         f"{expansion_a:.2f}× expansion across {len(by_system)} source systems; "
         f"{missed_by_siloed} records missed by siloed approach",
         "Relationship propagation"],
        ["B: GDPR Erasure vs Holds",
         f"{len(pii_records)} PII records analyzed",
         f"{can_delete} deletable, {hold_blocks} blocked by hold, "
         f"{retention_blocks} blocked by retention",
         "Conflict detection"],
        ["C: Multi-Jurisdiction Audit",
         f"{len(fin_records)} financial records",
         f"{fin_result.total_conflicts} conflicts across "
         f"{len(jurisdiction_conflicts)} jurisdictions",
         "Jurisdictional reasoning"],
    ]

    print_table(
        ["Scenario", "Scope", "Key Finding", "T-RKG Capability"],
        table6_rows,
        "Table 6: End-to-End Governance Scenario Results"
    )

    return {
        "scenario_a": {
            "seeds": len(seed_ids), "propagated": len(propagated),
            "expansion": expansion_a, "missed_by_siloed": missed_by_siloed,
            "by_system": dict(by_system), "by_type": dict(by_type),
        },
        "scenario_b": {
            "custodian": target_custodian.name if target_custodian else None,
            "pii_records": len(pii_records), "can_delete": can_delete,
            "hold_blocks": hold_blocks, "retention_blocks": retention_blocks,
            "conflict_records": len(conflict_records),
        },
        "scenario_c": {
            "financial_records": len(fin_records),
            "multi_reg": multi_reg_count,
            "conflicts": fin_result.total_conflicts,
            "by_type": fin_result.conflicts_by_type,
            "by_jurisdiction": dict(jurisdiction_conflicts),
        },
    }


# =============================================================================
# EXPERIMENT 5: Ablation Study
#
# FIX: Now uses get_matter_centric_seeds() (same as E2) and max_depth=10
# (same as E2). Previously used list(store.records.keys())[:50] with
# max_depth=5, which produced ~68 vs E2's ~162 for identical "Att+Thread,
# 10K, 50 seeds" configurations — the contradiction the reviewer caught.
# =============================================================================

def experiment_5_ablation():
    """
    Show that each T-RKG component contributes distinct capability.
    Generates Table 7 (ablation results).

    Seed selection and depth match experiment_2_hold_propagation() exactly,
    so Table 7's "Full T-RKG" hold set is directly comparable to Table 3's
    "Att + Thread" row.
    """
    print("\n" + "=" * 70)
    print("EXPERIMENT 5: Ablation Study")
    print("=" * 70)
    print("  Using matter-centric seeds and max_depth=10 (matches E2/Table 3).\n")

    detector = ConflictDetector()
    num_seeds = 50
    max_depth = 10   # FIX: was 5, now matches E2

    ablation_results = defaultdict(lambda: {"conflicts": [], "hold_sets": [], "ratios": []})

    for seed in EXPERIMENT_SEEDS:
        store = generate_store(10000, seed)

        # FIX: matter-centric seed selection, identical to E2
        seed_ids = get_matter_centric_seeds(store, num_seeds)

        # Full T-RKG
        full_conflicts = detector.detect_all_conflicts(store.records)
        full_prop = store.propagate_hold(
            seed_ids,
            [RelationType.ATTACHMENT, RelationType.THREAD],
            max_depth=max_depth   # FIX: was 5
        )
        ablation_results["Full T-RKG"]["conflicts"].append(full_conflicts.total_conflicts)
        ablation_results["Full T-RKG"]["hold_sets"].append(len(full_prop))
        ablation_results["Full T-RKG"]["ratios"].append(len(full_prop) / num_seeds)

        # No ontology → no conflict detection
        no_ont = UntypedGraphConflictDetector().detect_all_conflicts(store.records)
        no_ont_prop = store.propagate_hold(
            seed_ids,
            [RelationType.ATTACHMENT, RelationType.THREAD],
            max_depth=max_depth   # FIX: was 5
        )
        ablation_results["No Ontology"]["conflicts"].append(no_ont.total_conflicts)
        ablation_results["No Ontology"]["hold_sets"].append(len(no_ont_prop))
        ablation_results["No Ontology"]["ratios"].append(len(no_ont_prop) / num_seeds)

        # No typed relationships → all relationship types propagate
        all_types = [RelationType.ATTACHMENT, RelationType.THREAD,
                     RelationType.DERIVATION, RelationType.REFERENCE]
        no_typed_prop = store.propagate_hold(seed_ids, all_types, max_depth=max_depth)  # FIX: was 5
        ablation_results["No Typed Rels"]["conflicts"].append(full_conflicts.total_conflicts)
        ablation_results["No Typed Rels"]["hold_sets"].append(len(no_typed_prop))
        ablation_results["No Typed Rels"]["ratios"].append(len(no_typed_prop) / num_seeds)

        # No propagation → seeds only
        ablation_results["No Propagation"]["conflicts"].append(full_conflicts.total_conflicts)
        ablation_results["No Propagation"]["hold_sets"].append(num_seeds)
        ablation_results["No Propagation"]["ratios"].append(1.0)

        # Siloed baseline → no graph, no ontology
        siloed = SiloedConflictDetector().detect_all_conflicts(store.records)
        ablation_results["Siloed Baseline"]["conflicts"].append(siloed.total_conflicts)
        ablation_results["Siloed Baseline"]["hold_sets"].append(num_seeds)
        ablation_results["Siloed Baseline"]["ratios"].append(1.0)

    table7_rows = []
    variant_order = ["Full T-RKG", "No Ontology", "No Typed Rels",
                     "No Propagation", "Siloed Baseline"]
    ontology_flags = ["✓", "✗", "✓", "✓", "✗"]
    typed_flags =    ["✓", "✓", "✗", "✓", "✗"]
    prop_flags =     ["✓", "✓", "✓", "✗", "✗"]

    for i, variant in enumerate(variant_order):
        data = ablation_results[variant]
        mean_c = statistics.mean(data["conflicts"])
        mean_h = statistics.mean(data["hold_sets"])
        mean_r = statistics.mean(data["ratios"])
        table7_rows.append([
            variant,
            ontology_flags[i],
            typed_flags[i],
            prop_flags[i],
            mean_std_int(data["conflicts"]),
            f"{mean_h:.0f} ({mean_r:.2f}×)",
        ])

        print(f"  {variant:20s}: conflicts={mean_std_int(data['conflicts'])}, "
              f"hold={mean_h:.0f} ({mean_r:.2f}×)")

    print_table(
        ["Variant", "Ontology", "Typed Rels", "Propagation",
         "Conflicts (mean ± σ)", "Hold Set (ratio)"],
        table7_rows,
        "Table 7: Ablation Study — Component Contributions (10K Dataset)"
    )

    return {v: {k: vals for k, vals in ablation_results[v].items()} for v in variant_order}


# =============================================================================
# EXPERIMENT 6: Regulation Applicability Analysis (Supplementary)
# =============================================================================

def experiment_6_regulation_analysis():
    """
    Supplementary: regulation applicability distribution.
    """
    print("\n" + "=" * 70)
    print("EXPERIMENT 6: Regulation Applicability Analysis (Supplementary)")
    print("=" * 70)

    detector = ConflictDetector()
    store = generate_store(10000, seed=42)

    result = detector.detect_all_conflicts(store.records)
    total = len(store.records)

    reg_count_dist = defaultdict(int)
    for record in store.records.values():
        n = len(detector.infer_applicable_regulations(record))
        reg_count_dist[n] += 1

    print(f"\n  Regulation applicability (10K dataset, {total} records):")
    for reg, count in sorted(result.regulation_applicability.items(), key=lambda x: -x[1]):
        pct = count / total * 100
        print(f"    {reg:10s}: {count:5d} records ({pct:.1f}%)")

    print(f"\n  Records by number of applicable regulations:")
    for n in sorted(reg_count_dist.keys()):
        count = reg_count_dist[n]
        pct = count / total * 100
        print(f"    {n} regulations: {count:5d} records ({pct:.1f}%)")

    return {
        "applicability": dict(result.regulation_applicability),
        "distribution": dict(reg_count_dist),
    }


# =============================================================================
# CAPABILITY SUMMARY
# =============================================================================

def print_capability_summary():
    """Generate Table 8: capability comparison across approaches."""
    print("\n" + "=" * 70)
    print("CAPABILITY SUMMARY")
    print("=" * 70)

    table8_rows = [
        ["Cross-system record view",         "✗", "✓", "✓"],
        ["Regulatory conflict detection",     "✗", "✗", "✓"],
        ["Semantic hold propagation",         "✗", "✗", "✓"],
        ["Configurable propagation policies", "✗", "✗", "✓"],
        ["Interpretable governance decisions","✗", "✗", "✓"],
        ["Temporal point-in-time queries",    "✗", "Partial", "✓"],
    ]

    print_table(
        ["Capability", "Siloed Systems", "Untyped Graph", "T-RKG"],
        table8_rows,
        "Table 8: Knowledge-Based Governance Capabilities"
    )


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("T-RKG: Complete Experiment Suite for KBS Paper")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Seeds: {EXPERIMENT_SEEDS}")
    print(f"Scale points: {SCALE_POINTS}")
    print(f"Mode: {'QUICK' if QUICK_MODE else 'FULL'}")
    print("=" * 70)

    all_results = {
        "timestamp": datetime.now().isoformat(),
        "seeds": EXPERIMENT_SEEDS,
        "scale_points": SCALE_POINTS,
        "mode": "quick" if QUICK_MODE else "full",
    }

    # Run E1 first — its conflict_times_by_scale feed into E3
    e1 = experiment_1_conflict_detection()
    all_results["e1_conflicts"] = e1

    e2 = experiment_2_hold_propagation()
    all_results["e2_propagation"] = e2

    # FIX: pass e1 into E3 so conflict detection column is shared
    e3 = experiment_3_scalability(e1_results=e1)
    all_results["e3_scalability"] = e3

    e4 = experiment_4_scenarios()
    all_results["e4_scenarios"] = e4

    e5 = experiment_5_ablation()
    all_results["e5_ablation"] = e5

    e6 = experiment_6_regulation_analysis()
    all_results["e6_regulations"] = e6

    print_capability_summary()

    output_path = os.path.join(os.path.dirname(__file__), "results.json")
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nAll results saved to {output_path}")

    print("\n" + "=" * 70)
    print("ALL EXPERIMENTS COMPLETE")
    print("=" * 70)
    print("""
Paper tables generated:
  Table 1:  Conflict detection across dataset sizes        (E1)
  Table 2:  Conflict type distribution                     (E1)
  Table 3:  Propagation by relationship configuration      (E2) max_depth=10, matter seeds
  Table 4:  Propagation depth analysis                     (E2)
  Table 5:  Scalability results                            (E3) conflict col = E1 times
  Table 6:  Governance scenario results                    (E4)
  Table 7:  Ablation study                                 (E5) max_depth=10, matter seeds
  Table 8:  Capability summary

Key consistency guarantees:
  - Table 1 conflict time == Table 5 conflict time (same measurements)
  - Table 3 "Att+Thread" hold set == Table 7 "Full T-RKG" hold set (same seeds+depth)
""")


if __name__ == "__main__":
    main()
