#!/usr/bin/env python3
"""E5 — Cross-system composition ablation.

T-RKG's central claim is that a single governance decision is driven by
attributes that, in a real enterprise, live in *different* source systems. E5
makes that claim falsifiable by turning composition into a switch:

  * COMPOSED   — the full record, every attribute visible (what T-RKG sees).
  * DECOMPOSED — the siloed view (trkg.composition.siloed_view): every attribute
                 whose home source system differs from the record's own system
                 is masked, so no cross-system attribute pair can co-occur.

The detector and the dataset are held identical; only the visibility of
cross-system attributes changes. If composition is the source of T-RKG's
cross-domain conflicts, the decomposed view must lose them.

Three paired measurements per seed (canonical 10-seed set):
  1. total conflicts                (composed vs. decomposed)
  2. cross-domain conflicts         (RETENTION_DELETION + JURISDICTION
                                     + HOLD_DELETION) — the headline
  3. applicability F1               (per-record regulation set vs. an
                                     independently-constructed ground truth
                                     keyed on the composed clean labels)

Headline comparisons report mean ± σ, a paired permutation test
(10,000 sign-flips, exact enumeration for n ≤ 14) and Cohen's d on the
per-seed differences.

Writes experiments/results/e5.json (isolated; merged later) and prints a
paper-ready summary. Deterministic from the seed; no external dependencies.
"""

import os
import sys
import json
import statistics
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trkg import (
    SyntheticDataGenerator, GeneratorConfig, ConflictDetector,
)
from trkg.composition import (
    decompose_records, siloed_view, assert_no_cross_system_triggers,
)
from experiments.stats_utils import (
    SEEDS, paired_permutation_test, cohens_d_paired,
)

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
DATASET_SIZE = 10000


def _cross_domain(by_type) -> int:
    return (by_type.get("RETENTION_DELETION", 0)
            + by_type.get("JURISDICTION", 0)
            + by_type.get("HOLD_DELETION", 0))


def _make_config(num_records: int) -> GeneratorConfig:
    scale = num_records / 10000
    return GeneratorConfig(
        num_emails=int(4000 * scale), num_documents=int(3000 * scale),
        num_chats=int(1500 * scale), num_tickets=int(500 * scale),
        num_contracts=int(500 * scale), num_financial=int(500 * scale),
        num_custodians=max(20, int(100 * scale)), num_matters=5,
    )


def _pr_f1(pred_fn, truth_fn, records):
    tp = fp = fn = 0
    for rec in records:
        pred = pred_fn(rec)
        truth = truth_fn(rec)
        tp += len(pred & truth)
        fp += len(pred - truth)
        fn += len(truth - pred)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)
    return precision, recall, f1


def _agg(values):
    """mean, std (sample), formatted as 'mean ± std'."""
    m = statistics.mean(values)
    s = statistics.stdev(values) if len(values) > 1 else 0.0
    return {"mean": m, "std": s, "values": list(values)}


def _fmt(agg, prec=1):
    return f"{agg['mean']:.{prec}f} ± {agg['std']:.{prec}f}"


def run(seeds=SEEDS, num_records=DATASET_SIZE):
    detector = ConflictDetector()
    profiles = detector.profiles

    per_seed = {
        "composed_total": [], "decomposed_total": [],
        "composed_xdom": [], "decomposed_xdom": [],
        "composed_f1": [], "decomposed_f1": [],
        "composed_recall": [], "decomposed_recall": [],
    }

    for seed in seeds:
        gen = SyntheticDataGenerator(_make_config(num_records), seed=seed)
        store = gen.generate()
        composed = store.records
        decomposed = decompose_records(composed)

        # Validity gate: the decomposed view must carry no foreign trigger.
        for view in decomposed.values():
            assert_no_cross_system_triggers(view)

        c_res = detector.detect_all_conflicts(composed)
        d_res = detector.detect_all_conflicts(decomposed)
        per_seed["composed_total"].append(c_res.total_conflicts)
        per_seed["decomposed_total"].append(d_res.total_conflicts)
        per_seed["composed_xdom"].append(_cross_domain(c_res.conflicts_by_type))
        per_seed["decomposed_xdom"].append(_cross_domain(d_res.conflicts_by_type))

        # Applicability F1 against the composed clean-label ground truth. The
        # truth is the same for both views (it is the *correct* answer); the
        # decomposed predictor is handicapped because it reasons over a masked
        # record, so its recall on cross-system regulations should drop.
        from trkg.schema import Record

        def truth_for(rec, _gen=gen):
            clean = _gen.clean_labels.get(rec.id)
            if clean is None:
                return detector.infer_applicable_regulations(rec)
            clean_rec = Record(
                id=rec.id, type=rec.type, title=rec.title,
                created=rec.created, modified=rec.modified,
                custodian_id=rec.custodian_id, system_id=rec.system_id,
                jurisdiction=clean["jurisdiction"],
                contains_pii=clean["contains_pii"],
                contains_phi=clean["contains_phi"],
                metadata={**rec.metadata,
                          "is_public_company": clean["is_public_company"]},
            )
            return {reg for reg, p in profiles.items() if p.applies_to(clean_rec)}

        composed_records = list(composed.values())
        decomposed_records = [decomposed[r.id] for r in composed_records]

        c_p, c_r, c_f1 = _pr_f1(detector.infer_applicable_regulations,
                                truth_for, composed_records)
        # Decomposed predictor: infer on the masked view, score against the
        # truth for the *same* record id.
        d_truth = {r.id: truth_for(r) for r in composed_records}

        def d_pred(view):
            return detector.infer_applicable_regulations(view)

        def d_truth_fn(view, _d=d_truth):
            return _d[view.id]

        d_p, d_r, d_f1 = _pr_f1(d_pred, d_truth_fn, decomposed_records)

        per_seed["composed_f1"].append(c_f1)
        per_seed["decomposed_f1"].append(d_f1)
        per_seed["composed_recall"].append(c_r)
        per_seed["decomposed_recall"].append(d_r)

    aggregates = {k: _agg(v) for k, v in per_seed.items()}

    def paired(a_key, b_key):
        a, b = per_seed[a_key], per_seed[b_key]
        obs, p = paired_permutation_test(a, b)
        return {
            "observed_mean_diff": obs,
            "p_value": p,
            "cohens_d": cohens_d_paired(a, b),
        }

    stats = {
        "total_conflicts": paired("composed_total", "decomposed_total"),
        "cross_domain": paired("composed_xdom", "decomposed_xdom"),
        "applicability_f1": paired("composed_f1", "decomposed_f1"),
    }

    return {
        "experiment": "E5",
        "title": "Cross-system composition ablation (composed vs. decomposed)",
        "dataset_size": num_records,
        "seeds": list(seeds),
        "n_seeds": len(seeds),
        "per_seed": per_seed,
        "aggregates": aggregates,
        "paired_tests": stats,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }


def _print_summary(out):
    a = out["aggregates"]
    s = out["paired_tests"]
    print("\n" + "=" * 70)
    print("E5: Cross-system composition ablation")
    print("=" * 70)
    print(f"  Dataset: {out['dataset_size']:,} records, {out['n_seeds']} seeds\n")
    print(f"  {'Metric':24s} | {'Composed':>16s} | {'Decomposed':>16s}")
    print("  " + "-" * 62)
    print(f"  {'Total conflicts':24s} | {_fmt(a['composed_total'],0):>16s} | "
          f"{_fmt(a['decomposed_total'],0):>16s}")
    print(f"  {'Cross-domain conflicts':24s} | {_fmt(a['composed_xdom'],0):>16s} | "
          f"{_fmt(a['decomposed_xdom'],0):>16s}")
    print(f"  {'Applicability F1':24s} | {_fmt(a['composed_f1'],3):>16s} | "
          f"{_fmt(a['decomposed_f1'],3):>16s}")
    print(f"  {'Applicability recall':24s} | {_fmt(a['composed_recall'],3):>16s} | "
          f"{_fmt(a['decomposed_recall'],3):>16s}")
    print("\n  Paired tests (composed - decomposed):")
    for name, key in [("cross-domain", "cross_domain"),
                      ("total", "total_conflicts"),
                      ("applicability F1", "applicability_f1")]:
        t = s[key]
        print(f"    {name:18s}: Δ={t['observed_mean_diff']:.3f}  "
              f"p={t['p_value']:.4g}  d={t['cohens_d']:.3f}")


def write_results(out):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, "e5.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n  Wrote {path}")
    return path


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    seeds = SEEDS[:2] if quick else SEEDS
    out = run(seeds=seeds)
    _print_summary(out)
    write_results(out)
