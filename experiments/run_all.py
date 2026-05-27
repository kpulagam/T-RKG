#!/usr/bin/env python3
"""Run every T-RKG experiment and write results.json.

Usage:
    python -m experiments.run_all          # full
    python -m experiments.run_all --quick  # fewer seeds, smaller datasets
"""

import sys
import os
import json
import time
import statistics
import tracemalloc
from datetime import datetime
from collections import defaultdict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trkg import (
    TRKGStore, RecordType, RelationType, Jurisdiction, Regulation,
    SyntheticDataGenerator, GeneratorConfig,
    ConflictDetector, SiloedConflictDetector, UntypedGraphConflictDetector,
)
from trkg.baselines.flat_baseline import FlatListStore
from trkg.baselines.sql_baseline import SQLiteStore
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
    config = make_config(num_records)
    gen = SyntheticDataGenerator(config, seed=seed)
    return gen.generate()


# =============================================================================
# EXPERIMENT 1: Conflict Detection Capability (RQ1)
# =============================================================================

def experiment_1_conflict_detection():
    """Conflict detection across scales (Tables 1, 2)."""
    print("\n" + "=" * 70)
    print("EXPERIMENT 1: Conflict Detection Capability (RQ1)")
    print("=" * 70)

    detector = ConflictDetector()
    siloed = SiloedConflictDetector()
    untyped = UntypedGraphConflictDetector()

    # Cross-domain = retention-deletion + jurisdiction + hold-deletion
    # (the families a siloed or ontology-free system structurally misses).
    table1_rows = []
    all_results = {}

    def cross_domain(by_type):
        return (by_type.get("RETENTION_DELETION", 0)
                + by_type.get("JURISDICTION", 0)
                + by_type.get("HOLD_DELETION", 0))

    for num_records in SCALE_POINTS:
        conflict_counts, conflict_cross = [], []
        siloed_counts, siloed_cross = [], []
        untyped_counts, untyped_cross = [], []
        times_ms, rel_counts = [], []

        for seed in EXPERIMENT_SEEDS:
            store = generate_store(num_records, seed)

            result = detector.detect_all_conflicts(store.records)
            conflict_counts.append(result.total_conflicts)
            conflict_cross.append(cross_domain(result.conflicts_by_type))
            times_ms.append(result.detection_time_ms)
            rel_counts.append(len(store.relationships))

            siloed_result = siloed.detect_all_conflicts(store.records)
            siloed_counts.append(siloed_result.total_conflicts)
            siloed_cross.append(cross_domain(siloed_result.conflicts_by_type))

            untyped_result = untyped.detect_all_conflicts(store.records)
            untyped_counts.append(untyped_result.total_conflicts)
            untyped_cross.append(cross_domain(untyped_result.conflicts_by_type))

        table1_rows.append([
            f"{num_records:,}",
            mean_std_int(conflict_counts),
            mean_std_int(conflict_cross),
            mean_std_int(siloed_counts),
            mean_std_int(siloed_cross),
            mean_std_int(untyped_counts),
            mean_std_int(untyped_cross),
            mean_std(times_ms),
        ])

        all_results[num_records] = {
            "conflicts": conflict_counts,
            "cross_domain": conflict_cross,
            "siloed_conflicts": siloed_counts,
            "siloed_cross_domain": siloed_cross,
            "untyped_conflicts": untyped_counts,
            "untyped_cross_domain": untyped_cross,
            "times_ms": times_ms,
            "relationships": rel_counts,
        }

        print(f"  {num_records:>7,}: "
              f"T-RKG total={mean_std_int(conflict_counts)} (cross-dom={mean_std_int(conflict_cross)}); "
              f"Siloed total={mean_std_int(siloed_counts)} (cross-dom={mean_std_int(siloed_cross)}); "
              f"No-Ont total={mean_std_int(untyped_counts)} (cross-dom={mean_std_int(untyped_cross)}); "
              f"time={mean_std(times_ms)}ms")

    print_table(
        ["Dataset",
         "T-RKG total", "T-RKG cross-dom",
         "Siloed total", "Siloed cross-dom",
         "No-Ont total", "No-Ont cross-dom",
         "T-RKG Time (ms)"],
        table1_rows,
        "Table 1: Conflict Detection Results "
        "(cross-domain = retention-deletion + jurisdiction + hold-deletion)"
    )

    # --- Table 2: Conflict type breakdown (using 10K dataset) ---
    print("\n  Conflict type breakdown (10K dataset, averaged):")
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

    table2_rows = []
    for ctype in ["RETENTION_DELETION", "JURISDICTION", "HOLD_DELETION", "PRIORITY"]:
        vals = type_counts_all[ctype]
        total_mean = statistics.mean(sum(type_counts_all[t]) for t in type_counts_all) if type_counts_all else 1
        pct = (statistics.mean(vals) / total_mean * 100) if total_mean > 0 else 0
        table2_rows.append([ctype, mean_std_int(vals), f"{pct:.0f}%"])

    print_table(
        ["Conflict Type", "Count (mean±σ)", "%"],
        table2_rows,
        "Table 2: Conflict Type Distribution (10K dataset)"
    )

    # Top regulation pairs
    print("  Top conflict regulation pairs:")
    pair_means = {p: statistics.mean(v) for p, v in pair_counts_all.items()}
    for pair, mean_count in sorted(pair_means.items(), key=lambda x: -x[1])[:8]:
        print(f"    {pair}: {mean_count:.1f}")

    # Severity breakdown
    print("\n  Severity distribution:")
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        vals = severity_counts_all[sev]
        print(f"    {sev}: {mean_std_int(vals)}")

    return all_results


# =============================================================================
# EXPERIMENT 2: Hold Propagation (RQ2 + RQ3)
# =============================================================================

def experiment_2_hold_propagation():
    """Propagation scope by relationship configuration (Tables 3, 4)."""
    print("\n" + "=" * 70)
    print("EXPERIMENT 2: Semantic Hold Propagation (RQ2 + RQ3)")
    print("=" * 70)

    configs = [
        ("None (Siloed)", []),
        ("Attachment", [RelationType.ATTACHMENT]),
        ("Thread", [RelationType.THREAD]),
        ("Att + Thread", [RelationType.ATTACHMENT, RelationType.THREAD]),
        ("+ Derivation", [RelationType.ATTACHMENT, RelationType.THREAD, RelationType.DERIVATION]),
        ("All types", [RelationType.ATTACHMENT, RelationType.THREAD,
                       RelationType.DERIVATION, RelationType.REFERENCE]),
    ]

    num_seeds = 50
    max_depth = 10

    # --- Table 3: Propagation by configuration ---
    table3_rows = []
    all_results = {}

    for config_name, rel_types in configs:
        final_counts = []
        times_ms = []

        for seed in EXPERIMENT_SEEDS:
            store = generate_store(PROPAGATION_DATASET_SIZE, seed)

            # Pick seed records from first matter's custodians
            matter = list(store.matters.values())[0]
            cust_records = []
            for cid in matter.custodian_ids:
                for rid in store._records_by_custodian.get(cid, set()):
                    cust_records.append(rid)
            seed_ids = cust_records[:num_seeds]
            if len(seed_ids) < num_seeds:
                remaining = [r for r in store.records.keys() if r not in seed_ids]
                seed_ids += remaining[:num_seeds - len(seed_ids)]

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
        ])

        all_results[config_name] = {
            "final_counts": final_counts,
            "times_ms": times_ms,
            "ratio": ratio,
        }

        print(f"  {config_name:20s}: {num_seeds} → {mean_std_int(final_counts)} "
              f"({ratio:.2f}×) in {mean_std(times_ms)} ms")

    print_table(
        ["Configuration", "Seeds", "Final (mean±σ)", "Ratio", "Time (ms)"],
        table3_rows,
        "Table 3: Propagation by Relationship Configuration"
    )

    # --- Table 4: Depth analysis for Att + Thread ---
    print("\n  Depth analysis (Att + Thread configuration):")
    depth_data = defaultdict(list)

    for seed in EXPERIMENT_SEEDS:
        store = generate_store(PROPAGATION_DATASET_SIZE, seed)
        matter = list(store.matters.values())[0]
        cust_records = []
        for cid in matter.custodian_ids:
            for rid in store._records_by_custodian.get(cid, set()):
                cust_records.append(rid)
        seed_ids = cust_records[:num_seeds]
        if len(seed_ids) < num_seeds:
            remaining = [r for r in store.records.keys() if r not in seed_ids]
            seed_ids += remaining[:num_seeds - len(seed_ids)]

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
        ["Depth", "New Records (mean±σ)", "Cumulative"],
        table4_rows,
        "Table 4: Propagation Depth Analysis (Att + Thread)"
    )

    return all_results


# =============================================================================
# EXPERIMENT 3: Scalability (RQ4)
# =============================================================================

def experiment_3_scalability():
    """Scalability across dataset sizes (Tables 5, 6)."""
    print("\n" + "=" * 70)
    print("EXPERIMENT 3: Scalability (RQ4)")
    print("=" * 70)

    detector = ConflictDetector()

    # --- Table 5: Scalability across dataset sizes ---
    table5_rows = []
    all_results = {}

    for num_records in SCALE_POINTS:
        build_times = []
        query_times = []
        prop_times = []
        conflict_times = []
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

            start = time.perf_counter()
            _ = store.select_records(lambda r: r.type == RecordType.EMAIL)
            query_times.append((time.perf_counter() - start) * 1000)

            seed_ids = list(store.records.keys())[:50]
            start = time.perf_counter()
            _ = store.propagate_hold(
                seed_ids,
                [RelationType.ATTACHMENT, RelationType.THREAD],
                max_depth=5
            )
            prop_times.append((time.perf_counter() - start) * 1000)

            start = time.perf_counter()
            _ = detector.detect_all_conflicts(store.records)
            conflict_times.append((time.perf_counter() - start) * 1000)

            start = time.perf_counter()
            _ = store.query_at_time(datetime(2023, 6, 15))
            temporal_times.append((time.perf_counter() - start) * 1000)

        mean_rels = statistics.mean(rel_counts)
        mean_throughput = statistics.mean(throughputs)

        table5_rows.append([
            f"{num_records:,}",
            f"{mean_rels:,.0f}",
            mean_std([t * 1000 for t in build_times]),
            f"{mean_throughput:,.0f}/s",
            mean_std(query_times),
            mean_std(prop_times),
            mean_std(conflict_times),
        ])

        all_results[num_records] = {
            "build_s": build_times,
            "memory_mb": memory_mbs,
            "query_ms": query_times,
            "prop_ms": prop_times,
            "conflict_ms": conflict_times,
            "temporal_ms": temporal_times,
            "throughput": throughputs,
            "relationships": rel_counts,
        }

        print(f"  {num_records:>7,}: build={mean_std([t for t in build_times])}s, "
              f"query={mean_std(query_times)}ms, "
              f"prop={mean_std(prop_times)}ms, "
              f"conflict={mean_std(conflict_times)}ms, "
              f"memory={mean_std(memory_mbs)}MB")

    print_table(
        ["Records", "Rels", "Build (ms)", "Throughput", "Query (ms)", "Prop (ms)", "Conflict (ms)"],
        table5_rows,
        "Table 5: Scalability Results"
    )

    # --- Table 6: Baseline comparison at 10K ---
    print("\n  Baseline comparison (10K dataset):")
    baseline_results = _run_baseline_comparison(detector)

    return {**all_results, "baselines": baseline_results}


def _run_baseline_comparison(detector):
    trkg_query = []
    trkg_prop = []
    trkg_conflict = []
    trkg_temporal = []
    flat_query = []
    flat_prop = []
    flat_temporal = []
    sql_query = []
    sql_prop = []
    sql_temporal = []

    for seed in EXPERIMENT_SEEDS:
        store = generate_store(10000, seed)

        flat = FlatListStore.from_trkg_store(store)
        sql = SQLiteStore.from_trkg_store(store)

        seed_ids = list(store.records.keys())[:50]
        rel_types = [RelationType.ATTACHMENT, RelationType.THREAD]

        start = time.perf_counter()
        _ = store.select_records(lambda r: r.type == RecordType.EMAIL)
        trkg_query.append((time.perf_counter() - start) * 1000)

        start = time.perf_counter()
        _ = store.propagate_hold(seed_ids, rel_types, max_depth=5)
        trkg_prop.append((time.perf_counter() - start) * 1000)

        start = time.perf_counter()
        _ = detector.detect_all_conflicts(store.records)
        trkg_conflict.append((time.perf_counter() - start) * 1000)

        start = time.perf_counter()
        _ = store.query_at_time(datetime(2023, 6, 15))
        trkg_temporal.append((time.perf_counter() - start) * 1000)

        start = time.perf_counter()
        _ = flat.select_records(lambda r: r.type == RecordType.EMAIL)
        flat_query.append((time.perf_counter() - start) * 1000)

        start = time.perf_counter()
        _ = flat.propagate_hold(seed_ids, rel_types, max_depth=5)
        flat_prop.append((time.perf_counter() - start) * 1000)

        start = time.perf_counter()
        _ = flat.query_at_time(datetime(2023, 6, 15))
        flat_temporal.append((time.perf_counter() - start) * 1000)

        start = time.perf_counter()
        _ = sql.select_records_by_type(RecordType.EMAIL)
        sql_query.append((time.perf_counter() - start) * 1000)

        start = time.perf_counter()
        _ = sql.propagate_hold(seed_ids, rel_types, max_depth=5)
        sql_prop.append((time.perf_counter() - start) * 1000)

        start = time.perf_counter()
        _ = sql.query_at_time(datetime(2023, 6, 15))
        sql_temporal.append((time.perf_counter() - start) * 1000)

        sql.close()

    def speedup(baseline, trkg):
        mb = statistics.mean(baseline)
        mt = statistics.mean(trkg)
        if mt == 0:
            return "—"
        return f"{mb / mt:.1f}×"

    table6_rows = [
        ["Type query",
         mean_std(trkg_query), mean_std(flat_query), mean_std(sql_query),
         speedup(flat_query, trkg_query), speedup(sql_query, trkg_query)],
        ["Propagation",
         mean_std(trkg_prop), mean_std(flat_prop), mean_std(sql_prop),
         speedup(flat_prop, trkg_prop), speedup(sql_prop, trkg_prop)],
        ["Conflict detect",
         mean_std(trkg_conflict), "N/A", "N/A", "N/A", "N/A"],
        ["Temporal query",
         mean_std(trkg_temporal), mean_std(flat_temporal), mean_std(sql_temporal),
         speedup(flat_temporal, trkg_temporal), speedup(sql_temporal, trkg_temporal)],
    ]

    print_table(
        ["Operation", "T-RKG (ms)", "Flat (ms)", "SQLite (ms)", "vs Flat", "vs SQL"],
        table6_rows,
        "Table 6: Baseline Comparison (10K dataset)"
    )

    return {
        "trkg": {"query": trkg_query, "prop": trkg_prop,
                 "conflict": trkg_conflict, "temporal": trkg_temporal},
        "flat": {"query": flat_query, "prop": flat_prop, "temporal": flat_temporal},
        "sql":  {"query": sql_query, "prop": sql_prop, "temporal": sql_temporal},
    }


# =============================================================================
# EXPERIMENT 4: Governance Scenarios (RQ5)
# =============================================================================

def experiment_4_scenarios():
    """End-to-end governance scenarios across seeds; reports Table 5."""
    print("\n" + "=" * 70)
    print("EXPERIMENT 4: Governance Scenarios (multi-seed)")
    print("=" * 70)

    detector = ConflictDetector()

    a_seeds, a_prop, a_systems_count = [], [], []
    a_extra_records = []
    b_pii, b_deletable, b_retention, b_conflicts = [], [], [], []
    c_fin, c_multi_reg, c_conf, c_critical_high = [], [], [], []

    for s in EXPERIMENT_SEEDS:
        store = generate_store(10000, seed=s)
        matter = list(store.matters.values())[0]

        # Scenario A: Cross-System Legal Hold
        seed_ids = []
        for cid in matter.custodian_ids:
            for rid in store._records_by_custodian.get(cid, set()):
                r = store.records[rid]
                if datetime(2023, 1, 1) <= r.created <= datetime(2024, 12, 31):
                    seed_ids.append(rid)
        propagated = store.propagate_hold(
            seed_ids, [RelationType.ATTACHMENT, RelationType.THREAD], max_depth=5
        )
        by_system = defaultdict(int)
        for rid in propagated:
            r = store.records.get(rid)
            if r:
                by_system[r.system_id] += 1
        a_seeds.append(len(seed_ids))
        a_prop.append(len(propagated))
        a_systems_count.append(len(by_system))
        a_extra_records.append(max(0, len(propagated) - len(seed_ids)))

        # Scenario B: GDPR Erasure (no pre-applied hold)
        eu_j = {Jurisdiction.EU, Jurisdiction.EU_DE,
                Jurisdiction.EU_ES, Jurisdiction.EU_FR}
        eu_cust = [c for c in store.custodians.values() if c.jurisdiction in eu_j]
        if eu_cust:
            target = eu_cust[0]
            cust_records = [
                store.records[rid]
                for rid in store._records_by_custodian.get(target.id, set())
            ]
            pii = [r for r in cust_records if r.contains_pii]

            deletable, retention_blocked, with_conflict = 0, 0, 0
            for r in pii:
                applicable = detector.infer_applicable_regulations(r)
                has_retention = any(
                    any(req.requirement_type == "RETAIN"
                        for req in detector.profiles[reg].requirements)
                    for reg in applicable if reg in detector.profiles
                )
                cs = detector.detect_conflicts_for_record(r, applicable)
                if cs:
                    with_conflict += 1
                if has_retention:
                    retention_blocked += 1
                else:
                    deletable += 1

            b_pii.append(len(pii))
            b_deletable.append(deletable)
            b_retention.append(retention_blocked)
            b_conflicts.append(with_conflict)

        # Scenario C: Multi-Jurisdiction Financial Audit
        fin_types = {RecordType.FINANCIAL, RecordType.AUDIT,
                     RecordType.TAX, RecordType.INVOICE}
        fin_records = [r for r in store.records.values() if r.type in fin_types]
        multi_reg = 0
        for r in fin_records:
            if len(detector.infer_applicable_regulations(r)) >= 2:
                multi_reg += 1
        fin_dict = {r.id: r for r in fin_records}
        fin_result = detector.detect_all_conflicts(fin_dict)
        c_fin.append(len(fin_records))
        c_multi_reg.append(multi_reg)
        c_conf.append(fin_result.total_conflicts)
        c_critical_high.append(
            fin_result.conflicts_by_severity.get("CRITICAL", 0)
            + fin_result.conflicts_by_severity.get("HIGH", 0)
        )

    print(f"\n  Scenario A (Cross-system Legal Hold, {len(EXPERIMENT_SEEDS)} seeds):")
    print(f"    seeds (custodian+date filter): {mean_std_int(a_seeds)}")
    print(f"    propagated (Att+Thread):       {mean_std_int(a_prop)}")
    print(f"    additional records via prop:   {mean_std_int(a_extra_records)}")
    print(f"    distinct systems reached:      {mean_std_int(a_systems_count)}")

    print(f"\n  Scenario B (GDPR Erasure, {len(EXPERIMENT_SEEDS)} seeds):")
    print(f"    PII records in scope:    {mean_std_int(b_pii)}")
    print(f"    Freely deletable:        {mean_std_int(b_deletable)}")
    print(f"    Blocked by retention:    {mean_std_int(b_retention)}")
    print(f"    Carrying active conflict:{mean_std_int(b_conflicts)}")

    print(f"\n  Scenario C (Multi-jurisdiction Financial Audit, "
          f"{len(EXPERIMENT_SEEDS)} seeds):")
    print(f"    Financial records:       {mean_std_int(c_fin)}")
    print(f"    With 2+ regulations:     {mean_std_int(c_multi_reg)}")
    print(f"    Conflicts detected:      {mean_std_int(c_conf)}")
    print(f"    Critical/High severity:  {mean_std_int(c_critical_high)}")

    table_rows = [
        ["A: Legal Hold",
         mean_std_int(a_seeds) + " seeds",
         f"{mean_std_int(a_prop)} after prop, +{mean_std_int(a_extra_records)} via cross-system",
         "Cross-system propagation"],
        ["B: GDPR Erasure",
         mean_std_int(b_pii) + " PII",
         f"{mean_std_int(b_deletable)} deletable, "
         f"{mean_std_int(b_retention)} retention-blocked, "
         f"{mean_std_int(b_conflicts)} conflict-bearing",
         "Conflict-aware classification"],
        ["C: Financial Audit",
         mean_std_int(c_fin) + " fin",
         f"{mean_std_int(c_conf)} conflicts ({mean_std_int(c_critical_high)} crit/high)",
         "Multi-jurisdiction reasoning"],
    ]

    print_table(
        ["Scenario", "Input", "Outcome (mean ± σ across 5 seeds)", "Capability"],
        table_rows,
        "Table 5: Governance Scenario Results (10K dataset, 5 seeds)"
    )

    return {
        "scenario_a": {"seeds": a_seeds, "propagated": a_prop,
                       "extra_records": a_extra_records,
                       "systems_count": a_systems_count},
        "scenario_b": {"pii_records": b_pii, "deletable": b_deletable,
                       "retention_blocked": b_retention,
                       "with_conflict": b_conflicts},
        "scenario_c": {"financial_records": c_fin,
                       "multi_reg_records": c_multi_reg,
                       "conflicts": c_conf,
                       "critical_high": c_critical_high},
    }


# =============================================================================
# EXPERIMENT 5: Ablation Study
# =============================================================================

def _matter_scoped_seeds(store, num_seeds: int = 50) -> list:
    """Pull seeds from the first matter; matches experiment 2's protocol."""
    matter = list(store.matters.values())[0]
    seeds = []
    for cid in matter.custodian_ids:
        for rid in store._records_by_custodian.get(cid, set()):
            seeds.append(rid)
    seeds = seeds[:num_seeds]
    if len(seeds) < num_seeds:
        rest = [r for r in store.records if r not in seeds]
        seeds += rest[:num_seeds - len(seeds)]
    return seeds


def experiment_5_ablation():
    """Component ablation (Table 6). Matter-scoped seeds at depth 10; the
    Full T-RKG hold set is directly comparable to the Att+Thread row in
    Table 3 by construction."""
    print("\n" + "=" * 70)
    print("EXPERIMENT 5: Ablation Study (matter-scoped, depth 10, multi-seed)")
    print("=" * 70)

    detector = ConflictDetector()
    siloed = SiloedConflictDetector()
    untyped = UntypedGraphConflictDetector()

    full_conf, full_set = [], []
    sil_conf, sil_cross = [], []
    unt_conf, unt_cross = [], []
    no_typed_set = []
    no_prop_set = []

    NUM_SEEDS = 50
    DEPTH = 10
    DATASET = 10000

    for s in EXPERIMENT_SEEDS:
        store = generate_store(DATASET, seed=s)
        seed_ids = _matter_scoped_seeds(store, NUM_SEEDS)

        full_c = detector.detect_all_conflicts(store.records)
        full_conf.append(full_c.total_conflicts)
        full_p = store.propagate_hold(
            seed_ids, [RelationType.ATTACHMENT, RelationType.THREAD], max_depth=DEPTH
        )
        full_set.append(len(full_p))

        unt_c = untyped.detect_all_conflicts(store.records)
        unt_conf.append(unt_c.total_conflicts)
        unt_cross.append(
            unt_c.conflicts_by_type.get("RETENTION_DELETION", 0)
            + unt_c.conflicts_by_type.get("JURISDICTION", 0)
            + unt_c.conflicts_by_type.get("HOLD_DELETION", 0)
        )

        # No typed rels: propagate all types equally.
        all_types = [RelationType.ATTACHMENT, RelationType.THREAD,
                     RelationType.DERIVATION, RelationType.REFERENCE]
        no_typed = store.propagate_hold(seed_ids, all_types, max_depth=DEPTH)
        no_typed_set.append(len(no_typed))

        no_prop_set.append(NUM_SEEDS)

        sil_c = siloed.detect_all_conflicts(store.records)
        sil_conf.append(sil_c.total_conflicts)
        sil_cross.append(
            sil_c.conflicts_by_type.get("RETENTION_DELETION", 0)
            + sil_c.conflicts_by_type.get("JURISDICTION", 0)
            + sil_c.conflicts_by_type.get("HOLD_DELETION", 0)
        )

    def fmt_ratio(vals):
        m = statistics.mean(vals)
        return f"{m:.0f} ({m / NUM_SEEDS:.2f}×)"

    table6_rows = [
        ["Full T-RKG",       "✓", "✓", "✓",
         mean_std_int(full_conf), fmt_ratio(full_set)],
        ["No Ontology",      "✗", "✓", "✓",
         f"{mean_std_int(unt_conf)} (cross-dom: {mean_std_int(unt_cross)})",
         fmt_ratio(full_set)],
        ["No Typed Rels",    "✓", "✗", "✓",
         mean_std_int(full_conf), fmt_ratio(no_typed_set)],
        ["No Propagation",   "✓", "✓", "✗",
         mean_std_int(full_conf), fmt_ratio(no_prop_set)],
        ["Siloed Baseline",  "✗", "✗", "✗",
         f"{mean_std_int(sil_conf)} (cross-dom: {mean_std_int(sil_cross)})",
         fmt_ratio(no_prop_set)],
    ]

    print_table(
        ["Variant", "Ont.", "Typed", "Prop.",
         "Conflicts (mean±σ)", "Hold Set"],
        table6_rows,
        "Table 6: Ablation Study (10K, 50 matter-scoped seeds, depth 10, 5 seeds)"
    )

    return {
        "full":         {"conflicts": full_conf, "hold_set": full_set},
        "no_ontology":  {"conflicts": unt_conf,
                         "cross_domain_conflicts": unt_cross,
                         "hold_set": full_set},
        "no_typed":     {"conflicts": full_conf, "hold_set": no_typed_set},
        "no_prop":      {"conflicts": full_conf, "hold_set": no_prop_set},
        "siloed":       {"conflicts": sil_conf,
                         "cross_domain_conflicts": sil_cross,
                         "hold_set": no_prop_set},
    }


# =============================================================================
# REGULATORY APPLICABILITY ANALYSIS
# =============================================================================

def _pr_f1(pred_fn, ground_fn, records):
    tp = fp = fn = 0
    for rec in records:
        pred = pred_fn(rec)
        truth = ground_fn(rec)
        tp += len(pred & truth)
        fp += len(pred - truth)
        fn += len(truth - pred)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)
    return precision, recall, f1


def _ground_truth_factory(detector, clean_labels):
    """Ground-truth function keyed on pre-noise labels, so the predicate
    is independent of the (possibly-noised) attributes the detector sees."""
    from trkg.schema import Record, RecordType
    profiles = detector.profiles

    def truth_for(rec):
        clean = clean_labels.get(rec.id)
        if clean is None:
            return detector.infer_applicable_regulations(rec)
        clean_rec = Record(
            id=rec.id, type=rec.type, title=rec.title,
            created=rec.created, modified=rec.modified,
            custodian_id=rec.custodian_id,
            system_id=rec.system_id,
            jurisdiction=clean["jurisdiction"],
            contains_pii=clean["contains_pii"],
            contains_phi=clean["contains_phi"],
            metadata={**rec.metadata, "is_public_company": clean["is_public_company"]},
        )
        return {reg for reg, prof in profiles.items() if prof.applies_to(clean_rec)}

    return truth_for


def experiment_8_large_seed_propagation():
    """Propagation latency vs. seed-set size (50, 500, 5000) on the 100K corpus."""
    print("\n" + "=" * 70)
    print("EXPERIMENT 8: Propagation Latency vs. Seed Set Size (100K corpus)")
    print("=" * 70)

    SEED_SIZES = [50, 500, 5000]
    DATASET = 100000 if not QUICK_MODE else 25000
    DEPTH = 5

    table_rows = []
    all_results = {}
    for seeds_n in SEED_SIZES:
        latencies, hold_sizes = [], []
        for s in EXPERIMENT_SEEDS:
            store = generate_store(DATASET, seed=s)
            seed_ids = list(store.records.keys())[:seeds_n]
            start = time.perf_counter()
            propagated = store.propagate_hold(
                seed_ids,
                [RelationType.ATTACHMENT, RelationType.THREAD],
                max_depth=DEPTH,
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            hold_sizes.append(len(propagated))
        table_rows.append([
            f"{seeds_n:,}",
            mean_std(latencies),
            mean_std_int(hold_sizes),
            f"{statistics.mean(latencies)/seeds_n*1000:.2f} µs",
        ])
        all_results[seeds_n] = {"latency_ms": latencies, "hold_size": hold_sizes}
        print(f"  Seeds={seeds_n:5,}: latency={mean_std(latencies)} ms, "
              f"hold set={mean_std_int(hold_sizes)}")

    print_table(
        ["Seed records", "Latency (ms)", "Hold set", "Per-seed cost"],
        table_rows,
        f"Table 10: Propagation latency vs. seed set size ({DATASET:,} corpus, depth {DEPTH}, 5 seeds)"
    )
    return all_results


def experiment_9_robustness_sweep():
    """Joint sweep over EU jurisdiction fraction and PII rate. Cross-domain
    conflicts depend on (PII × EU × public-company), so behaviour should
    vary smoothly with each axis."""
    print("\n" + "=" * 70)
    print("EXPERIMENT 9: Parameter Sweep Robustness (jurisdictional mix × PII)")
    print("=" * 70)

    detector = ConflictDetector()
    eu_fractions = [0.05, 0.15, 0.30, 0.40]
    pii_rates = [0.05, 0.20]

    table_rows = []
    all_results = {}
    for eu_frac in eu_fractions:
        for pii in pii_rates:
            conflicts, cross_dom, multi_reg = [], [], []
            for s in EXPERIMENT_SEEDS:
                cfg = make_config(10000)
                cfg.pii_probability = pii
                # Re-weight jurisdictions so EU + EU_DE sums to eu_frac.
                from trkg.schema import Jurisdiction
                cfg.jurisdiction_weights = {
                    Jurisdiction.US:    0.85 - eu_frac,
                    Jurisdiction.US_CA: 0.05,
                    Jurisdiction.EU:    eu_frac * 0.7,
                    Jurisdiction.EU_DE: eu_frac * 0.3,
                    Jurisdiction.UK:    0.05,
                    Jurisdiction.CA:    0.05,
                }
                store = SyntheticDataGenerator(cfg, seed=s).generate()
                r = detector.detect_all_conflicts(store.records)
                conflicts.append(r.total_conflicts)
                cross_dom.append(
                    r.conflicts_by_type.get("RETENTION_DELETION", 0)
                    + r.conflicts_by_type.get("JURISDICTION", 0)
                    + r.conflicts_by_type.get("HOLD_DELETION", 0)
                )
                multi_reg.append(sum(1 for rec in store.records.values()
                                      if len(detector.infer_applicable_regulations(rec)) >= 2))

            table_rows.append([
                f"{eu_frac*100:.0f}%",
                f"{pii*100:.0f}%",
                mean_std_int(conflicts),
                mean_std_int(cross_dom),
                mean_std_int(multi_reg),
            ])
            key = f"eu{eu_frac:.2f}_pii{pii:.2f}"
            all_results[key] = {"conflicts": conflicts, "cross_dom": cross_dom, "multi_reg": multi_reg}
            print(f"  EU={eu_frac*100:>3.0f}% × PII={pii*100:>3.0f}%: "
                  f"total={mean_std_int(conflicts)}, "
                  f"cross-dom={mean_std_int(cross_dom)}, "
                  f"multi-reg={mean_std_int(multi_reg)}")

    print_table(
        ["EU fraction", "PII rate", "Total conflicts", "Cross-domain", "Multi-reg records"],
        table_rows,
        "Table 11: Robustness to jurisdictional mix × PII rate (10K dataset, 5 seeds)"
    )
    return all_results


def experiment_7_applicability_pr_f1():
    """Per-record applicability P/R/F1 vs. an independently-constructed
    ground truth, in clean and noised regimes. In the clean regime T-RKG
    matches by construction (the table measures each baseline's gap);
    in the noised regime T-RKG's F1 drops below 1.0 and the table reports
    its robustness to data-quality issues alongside the baselines' gap."""
    print("\n" + "=" * 70)
    print("EXPERIMENT 7: Applicability P/R/F1 vs. Independently-Constructed Ground Truth")
    print("=" * 70)

    detector = ConflictDetector()
    untyped = UntypedGraphConflictDetector()

    siloed_per_record = lambda rec: (
        {r for r in SiloedConflictDetector.SYSTEM_REGULATIONS.get(rec.system_id, set())
         if r in detector.profiles and detector.profiles[r].applies_to(rec)}
    )
    untyped_per_record = lambda rec: untyped._naive_applicable(rec)
    trkg_per_record = lambda rec: detector.infer_applicable_regulations(rec)

    def run_regime(noise_juris, noise_pii, noise_meta, label):
        per_seed = {"trkg": [], "untyped": [], "siloed": []}
        for s in EXPERIMENT_SEEDS:
            cfg = make_config(10000)
            cfg.noise_jurisdiction_flip = noise_juris
            cfg.noise_pii_flip = noise_pii
            cfg.noise_metadata_flip = noise_meta
            gen = SyntheticDataGenerator(cfg, seed=s)
            store = gen.generate()
            truth_fn = _ground_truth_factory(detector, gen.clean_labels)
            records = list(store.records.values())
            for name, fn in [("trkg", trkg_per_record),
                             ("untyped", untyped_per_record),
                             ("siloed", siloed_per_record)]:
                per_seed[name].append(_pr_f1(fn, truth_fn, records))

        rows = []
        for name in ["trkg", "untyped", "siloed"]:
            precisions = [t[0] for t in per_seed[name]]
            recalls    = [t[1] for t in per_seed[name]]
            f1s        = [t[2] for t in per_seed[name]]
            rows.append([
                {"trkg": "T-RKG", "untyped": "No-Ontology", "siloed": "Siloed"}[name],
                f"{statistics.mean(precisions):.3f} ± {statistics.stdev(precisions):.3f}",
                f"{statistics.mean(recalls):.3f} ± {statistics.stdev(recalls):.3f}",
                f"{statistics.mean(f1s):.3f} ± {statistics.stdev(f1s):.3f}",
            ])
            print(f"  [{label}] {name.upper():12s}: P={statistics.mean(precisions):.3f} "
                  f"R={statistics.mean(recalls):.3f} F1={statistics.mean(f1s):.3f}")
        return rows, per_seed

    print("\n  Regime A: clean labels (no noise) -- baseline-gap measurement")
    rows_clean, seed_clean = run_regime(0.0, 0.0, 0.0, "clean")
    print_table(
        ["System", "Precision", "Recall", "F1"],
        rows_clean,
        "Table 9a: Applicability P/R/F1 -- clean regime (10K, 5 seeds)"
    )

    print("\n  Regime B: 10% jurisdiction + 10% PII + 10% public-company label noise")
    rows_noised, seed_noised = run_regime(0.10, 0.10, 0.10, "noised")
    print_table(
        ["System", "Precision", "Recall", "F1"],
        rows_noised,
        "Table 9b: Applicability P/R/F1 -- noised regime (10% per-attribute noise)"
    )

    return {"clean": seed_clean, "noised": seed_noised}


def experiment_12_noise_sweep():
    """Applicability F1 across noise rates {2%, 5%, 10%, 15%, 20%} on a
    10K corpus, 10 seeds, for T-RKG / No-Ontology / Siloed. The output is
    a sensitivity curve, not a single point."""
    print("\n" + "=" * 70)
    print("EXPERIMENT 12: Noise-rate sensitivity (F1 vs. noise level)")
    print("=" * 70)

    detector = ConflictDetector()
    untyped = UntypedGraphConflictDetector()
    rates = [0.02, 0.05, 0.10, 0.15, 0.20]

    siloed_per_record = lambda rec: (
        {r for r in SiloedConflictDetector.SYSTEM_REGULATIONS.get(rec.system_id, set())
         if r in detector.profiles and detector.profiles[r].applies_to(rec)}
    )
    untyped_per_record = lambda rec: untyped._naive_applicable(rec)
    trkg_per_record = lambda rec: detector.infer_applicable_regulations(rec)

    out = {}
    for rate in rates:
        per_seed = {"trkg": [], "untyped": [], "siloed": []}
        for s in EXPERIMENT_SEEDS:
            cfg = make_config(10000)
            cfg.noise_jurisdiction_flip = rate
            cfg.noise_pii_flip = rate
            cfg.noise_metadata_flip = rate
            gen = SyntheticDataGenerator(cfg, seed=s)
            store = gen.generate()
            truth_fn = _ground_truth_factory(detector, gen.clean_labels)
            records = list(store.records.values())
            for name, fn in [("trkg", trkg_per_record),
                             ("untyped", untyped_per_record),
                             ("siloed", siloed_per_record)]:
                per_seed[name].append(_pr_f1(fn, truth_fn, records))
        for name in ("trkg", "untyped", "siloed"):
            f1s = [t[2] for t in per_seed[name]]
            print(f"  rate={rate:.2f} {name:10s}: F1={statistics.mean(f1s):.3f} "
                  f"+- {statistics.stdev(f1s):.3f}")
        out[f"{rate:.2f}"] = per_seed
    return out


def experiment_13_block_noise():
    """Block-correlated jurisdiction noise: 10 contiguous blocks of 100
    records each have their jurisdiction overwritten with a single random
    target. Matches the i.i.d. comparator's 10% total flip rate but with
    correlated structure that the i.i.d. model cannot reproduce."""
    print("\n" + "=" * 70)
    print("EXPERIMENT 13: Block-correlated noise (jurisdiction flips in 10 contiguous blocks of 100)")
    print("=" * 70)

    import random as _r
    detector = ConflictDetector()
    untyped = UntypedGraphConflictDetector()

    siloed_per_record = lambda rec: (
        {r for r in SiloedConflictDetector.SYSTEM_REGULATIONS.get(rec.system_id, set())
         if r in detector.profiles and detector.profiles[r].applies_to(rec)}
    )
    untyped_per_record = lambda rec: untyped._naive_applicable(rec)
    trkg_per_record = lambda rec: detector.infer_applicable_regulations(rec)

    per_seed = {"trkg": [], "untyped": [], "siloed": []}
    for s in EXPERIMENT_SEEDS:
        cfg = make_config(10000)
        gen = SyntheticDataGenerator(cfg, seed=s)
        store = gen.generate()
        truth_fn = _ground_truth_factory(detector, gen.clean_labels)
        # Apply block-correlated jurisdiction flips on top of clean labels.
        rng = _r.Random(s + 7919)
        records = list(store.records.values())
        n_blocks = 10
        block_size = 100
        for _ in range(n_blocks):
            start = rng.randint(0, max(0, len(records) - block_size))
            target = rng.choice(list(Jurisdiction))
            for r in records[start:start + block_size]:
                r.jurisdiction = target
        for name, fn in [("trkg", trkg_per_record),
                         ("untyped", untyped_per_record),
                         ("siloed", siloed_per_record)]:
            per_seed[name].append(_pr_f1(fn, truth_fn, records))

    for name in ("trkg", "untyped", "siloed"):
        f1s = [t[2] for t in per_seed[name]]
        print(f"  block-noise {name:10s}: F1={statistics.mean(f1s):.3f} "
              f"+- {statistics.stdev(f1s):.3f}")
    return per_seed


def experiment_10_exemption_impact():
    """GDPR Art. 17(3) exemption impact on Hold-Deletion conflicts.

    For each seed: generate a 10K dataset, distribute holds round-robin
    across all matters over the EU+PII population, then run
    detect_all_conflicts with and without the matters dict on the
    detector. Reports both Hold-Deletion counts and the suppressed count.
    """
    print("\n" + "=" * 70)
    print("EXPERIMENT 10: GDPR Art. 17(3) Exemption Impact")
    print("=" * 70)

    counts_with, counts_without, suppressed, eu_pii_pop = [], [], [], []
    obligation_flag_rate, claim_flag_rate = [], []
    for seed in EXPERIMENT_SEEDS:
        store = generate_store(10000, seed=seed)
        matters = list(store.matters.values())
        # EU+PII population: the records GDPR Art. 17 erasure attaches to.
        eu = {Jurisdiction.EU, Jurisdiction.EU_DE,
              Jurisdiction.EU_ES, Jurisdiction.EU_FR}
        targets = [r.id for r in store.records.values()
                   if r.contains_pii and r.jurisdiction in eu]
        # Round-robin the holds across matters so suppression reflects the
        # population-level exemption rate, not one matter's binary state.
        import random as _r
        _rng = _r.Random(seed)
        for tid in targets:
            m = _rng.choice(matters)
            store.apply_hold(m.id, [tid], assignment_type="DIRECT")
        eu_pii_pop.append(len(targets))

        active = {m.id for m in matters}

        det_no = ConflictDetector()
        res_no = det_no.detect_all_conflicts(store.records, active_hold_matters=active)
        hd_no = res_no.conflicts_by_type.get("HOLD_DELETION", 0)

        det_yes = ConflictDetector(matters=store.matters)
        res_yes = det_yes.detect_all_conflicts(store.records, active_hold_matters=active)
        hd_yes = res_yes.conflicts_by_type.get("HOLD_DELETION", 0)

        counts_without.append(hd_no)
        counts_with.append(hd_yes)
        suppressed.append(det_yes.suppressed_exemption_count)

        obligation_flag_rate.append(
            sum(1 for m in matters if m.legal_obligation_flag) / max(1, len(matters))
        )
        claim_flag_rate.append(
            sum(1 for m in matters if m.legal_claim_flag) / max(1, len(matters))
        )

    print(f"\n  EU+PII population (seed-level):     {eu_pii_pop}")
    print(f"  Hold-Deletion conflicts (no suppr): {mean_std_int(counts_without)}")
    print(f"  Hold-Deletion conflicts (suppression active): {mean_std_int(counts_with)}")
    print(f"  Suppressed by exemption:             {mean_std_int(suppressed)}")
    print(f"  Per-seed obligation-flag rate:       {[f'{r:.2f}' for r in obligation_flag_rate]}")
    print(f"  Per-seed claim-flag rate:            {[f'{r:.2f}' for r in claim_flag_rate]}")

    return {
        "eu_pii_population_per_seed": eu_pii_pop,
        "hold_deletion_without_suppression": counts_without,
        "hold_deletion_with_suppression": counts_with,
        "suppressed_by_exemption": suppressed,
        "obligation_flag_rate_per_seed": obligation_flag_rate,
        "claim_flag_rate_per_seed": claim_flag_rate,
        "matter_population": [5] * len(EXPERIMENT_SEEDS),  # num_matters fixed at 5
    }


def experiment_11_shacl_baseline():
    """Run the SHACL Core baseline across all scales so Table 7 can carry
    a SHACL column. Only the static-constraint subset is expressible;
    skipped rule families are listed in shacl_limitations.json and in
    the JSON output."""
    print("\n" + "=" * 70)
    print("EXPERIMENT 11: SHACL Baseline Comparison")
    print("=" * 70)

    from trkg.baselines import ShaclBaseline
    baseline = ShaclBaseline()
    per_scale = {}
    for scale in SCALE_POINTS:
        violations, times = [], []
        for seed in EXPERIMENT_SEEDS:
            store = generate_store(scale, seed=seed)
            res = baseline.detect_all_conflicts(store.records, store.matters)
            violations.append(res.total_violations)
            times.append(res.detection_time_ms)
        per_scale[scale] = {
            "violations_per_seed": violations,
            "detection_ms_per_seed": times,
        }
        print(f"  {scale:>6d}: violations={mean_std_int(violations)}, "
              f"ms={statistics.mean(times):.1f}±{statistics.stdev(times) if len(times)>1 else 0:.1f}")

    return {
        "per_scale": per_scale,
        "expressible_rule_count": baseline.expressible_rule_count,
        "skipped_rule_families": baseline.skipped_rule_families,
    }


def experiment_6_regulation_analysis():
    """Per-regulation record coverage at 10K."""
    print("\n" + "=" * 70)
    print("EXPERIMENT 6: Regulation Applicability Analysis")
    print("=" * 70)

    detector = ConflictDetector()
    store = generate_store(10000, seed=42)

    result = detector.detect_all_conflicts(store.records)

    print("\n  Regulation applicability (10K dataset):")
    total = len(store.records)
    rows = []
    for reg, count in sorted(result.regulation_applicability.items(), key=lambda x: -x[1]):
        pct = count / total * 100
        rows.append([reg, str(count), f"{pct:.1f}%"])
        print(f"    {reg:10s}: {count:5d} records ({pct:.1f}%)")

    print(f"\n  Records with 0 regulations: "
          f"{total - sum(1 for r in store.records.values() if detector.infer_applicable_regulations(r))}")
    print(f"  Records with 1+ regulation: "
          f"{sum(1 for r in store.records.values() if detector.infer_applicable_regulations(r))}")
    print(f"  Records with 2+ regulations: "
          f"{sum(1 for r in store.records.values() if len(detector.infer_applicable_regulations(r)) >= 2)}")

    return dict(result.regulation_applicability)


# =============================================================================
# MAIN
# =============================================================================

def _runtime_environment():
    """Capture CPU/OS/Python details for the results JSON."""
    import platform, sys
    env = {
        "python":      sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "system":      platform.system(),
        "release":     platform.release(),
        "machine":     platform.machine(),
        "processor":   platform.processor(),
        "cpu_count":   os.cpu_count(),
    }
    try:
        import subprocess
        if platform.system() == "Linux":
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if line.startswith("model name"):
                        env["cpu_model"] = line.split(":", 1)[1].strip()
                        break
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal"):
                        env["mem_total_kb"] = int(line.split()[1])
                        break
        elif platform.system() == "Darwin":
            env["cpu_model"] = subprocess.check_output(
                ["sysctl", "-n", "machdep.cpu.brand_string"]
            ).decode().strip()
    except Exception:
        pass
    return env


def main():
    print("=" * 70)
    print("T-RKG: Complete Experiment Suite for KBS Paper")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Seeds: {EXPERIMENT_SEEDS}")
    print(f"Scales: {SCALE_POINTS}")
    env = _runtime_environment()
    print(f"Environment: {env.get('cpu_model', env.get('processor','?'))} "
          f"× {env.get('cpu_count','?')} cores, "
          f"{env.get('system','?')} {env.get('release','?')}, "
          f"Python {env.get('python','?')}")
    print("=" * 70)

    all_results = {"timestamp": datetime.now().isoformat(), "environment": env}

    all_results["e1_conflicts"] = experiment_1_conflict_detection()
    all_results["e2_propagation"] = experiment_2_hold_propagation()
    all_results["e3_scalability"] = experiment_3_scalability()
    all_results["e4_scenarios"] = experiment_4_scenarios()
    all_results["e5_ablation"] = experiment_5_ablation()
    all_results["e6_regulations"] = experiment_6_regulation_analysis()
    all_results["e7_pr_f1"] = experiment_7_applicability_pr_f1()
    all_results["e8_large_seed_propagation"] = experiment_8_large_seed_propagation()
    all_results["e9_robustness_sweep"] = experiment_9_robustness_sweep()
    all_results["e10_exemption_impact"] = experiment_10_exemption_impact()
    all_results["e11_shacl_baseline"] = experiment_11_shacl_baseline()
    all_results["e12_noise_sweep"] = experiment_12_noise_sweep()
    all_results["e13_block_noise"] = experiment_13_block_noise()

    output_path = os.path.join(os.path.dirname(__file__), "results.json")
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nResults saved to {output_path}")

    print("\n" + "=" * 70)
    print("ALL EXPERIMENTS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
