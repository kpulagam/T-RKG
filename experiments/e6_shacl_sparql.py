#!/usr/bin/env python3
"""E6 — SHACL-SPARQL baseline: expressivity parity at prohibitive cost.

SHACL Core can only express per-node static attribute conjunctions. SHACL-SPARQL
(sh:sparql) can join across nodes and use FILTER NOT EXISTS, so it reaches three
families Core cannot: RETENTION_DELETION, HOLD_DELETION (with the GDPR Art. 17(3)
defeasible exemption), and JURISDICTION. E6's finding is NOT that SHACL-SPARQL
fails to express these — it succeeds (expressivity parity on those three). The
finding is the *cost*: SHACL-SPARQL runs at roughly 10^4-10^5x the latency of
T-RKG's native detector, which makes it infeasible at enterprise scale. That
latency gap is the result.

Apples-to-apples discipline: for each (scale, seed) a single hold context is
built (round-robin holds over the EU+PII population, exactly as E3) and applied
to the store BEFORE either detector runs, so T-RKG and SHACL-SPARQL see the
*same* records, the same holds, and the same matters. Recall is then T-RKG-as-
reference: of the records T-RKG flags in a family, what fraction does
SHACL-SPARQL also flag.

Measured scales: 1K, 5K, 10K, canonical 10-seed set. Larger scales (25K/50K/
100K) are NOT run; they are projected from the measured points and reported as
infeasible with a runtime estimate — the infeasibility is itself the finding.

Writes experiments/results/e6.json (isolated; merged later).
"""

import os
import sys
import json
import time
import random
import statistics
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trkg import SyntheticDataGenerator, ConflictDetector
from trkg.synthetic import balanced_config
from trkg.schema import Jurisdiction
from trkg.baselines.shacl_sparql_baseline import (
    ShaclSparqlBaseline, SHAPE_FAMILY, SKIPPED_RULE_FAMILIES,
)
from experiments.stats_utils import SEEDS

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
MEASURED_SCALES = [1000, 5000, 10000]
PROJECTED_SCALES = [25000, 50000, 100000]
EXPRESSIBLE_FAMILIES = list(SHAPE_FAMILY.values())  # RET_DEL, HOLD_DEL, JURIS
EU_JURISDICTIONS = {
    Jurisdiction.EU, Jurisdiction.EU_DE, Jurisdiction.EU_ES, Jurisdiction.EU_FR,
}


def _agg(values):
    m = statistics.mean(values)
    s = statistics.stdev(values) if len(values) > 1 else 0.0
    return {"mean": m, "std": s, "values": list(values)}


def _apply_hold_context(store, seed):
    """Round-robin holds over the EU+PII population (identical to E3). Returns
    the active-matter set. Applied once, then shared by both detectors."""
    matters = list(store.matters.values())
    targets = [r.id for r in store.records.values()
               if r.contains_pii and r.jurisdiction in EU_JURISDICTIONS]
    rng = random.Random(seed)
    for tid in targets:
        store.apply_hold(rng.choice(matters).id, [tid], assignment_type="DIRECT")
    return {m.id for m in matters}


def _trkg_family_sets(result):
    """record-id sets per family from a T-RKG ConflictDetectionResult."""
    fam = {f: set() for f in EXPRESSIBLE_FAMILIES}
    for c in result.conflicts:
        t = c.conflict_type.value
        if t in fam:
            fam[t].add(c.record_id)
    return fam


def run(seeds=SEEDS, scales=MEASURED_SCALES):
    sparql = ShaclSparqlBaseline()
    engine = sparql.engine

    per_scale = {}
    for n in scales:
        trkg_ms, sparql_ms, ratio = [], [], []
        recall = {f: [] for f in EXPRESSIBLE_FAMILIES}
        trkg_counts = {f: [] for f in EXPRESSIBLE_FAMILIES}
        sparql_counts = {f: [] for f in EXPRESSIBLE_FAMILIES}

        for seed in seeds:
            gen = SyntheticDataGenerator(balanced_config(n), seed=seed)
            store = gen.generate()
            active = _apply_hold_context(store, seed)

            # T-RKG reference, with the same matters + hold context.
            det = ConflictDetector(matters=store.matters)
            tres = det.detect_all_conflicts(store.records, active_hold_matters=active)
            tfam = _trkg_family_sets(tres)
            trkg_ms.append(tres.detection_time_ms)

            # SHACL-SPARQL over the identical store/matters.
            sres = sparql.detect_all_conflicts(store.records, store.matters)
            sparql_ms.append(sres.detection_time_ms)
            ratio.append(sres.detection_time_ms / tres.detection_time_ms
                         if tres.detection_time_ms > 0 else float("nan"))

            for f in EXPRESSIBLE_FAMILIES:
                ref = tfam[f]
                got = sres.flagged_by_family.get(f, set())
                trkg_counts[f].append(len(ref))
                sparql_counts[f].append(len(got))
                recall[f].append(len(got & ref) / len(ref) if ref else float("nan"))

        per_scale[n] = {
            "trkg_detection_ms": _agg(trkg_ms),
            "sparql_detection_ms": _agg(sparql_ms),
            "latency_ratio_sparql_over_trkg": _agg(ratio),
            "recall_by_family": {
                f: _agg([v for v in recall[f] if v == v]) for f in EXPRESSIBLE_FAMILIES
            },
            "trkg_flagged_by_family": {f: _agg(trkg_counts[f]) for f in EXPRESSIBLE_FAMILIES},
            "sparql_flagged_by_family": {f: _agg(sparql_counts[f]) for f in EXPRESSIBLE_FAMILIES},
        }

    projection = _project_infeasible(per_scale, scales)

    return {
        "experiment": "E6",
        "title": "SHACL-SPARQL baseline: expressivity parity at prohibitive latency",
        "preset": "balanced_config",
        "measured_scales": list(scales),
        "projected_scales": PROJECTED_SCALES,
        "seeds": list(seeds),
        "n_seeds": len(seeds),
        "expressible_families": EXPRESSIBLE_FAMILIES,
        "skipped_rule_families": SKIPPED_RULE_FAMILIES,
        "engine": engine,
        "per_scale": {str(k): v for k, v in per_scale.items()},
        "projection": projection,
        "hold_context": "round-robin holds over EU+PII population; identical "
                        "store/matters/holds for both detectors (apples-to-apples)",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }


def _project_infeasible(per_scale, scales):
    """Fit a power law sparql_ms ~ a * n^b on the measured points and project
    runtime at the unmeasured scales. Reported as an estimate, not a measurement."""
    import math
    if len(scales) < 2:
        return {"power_law": None,
                "estimates": {},
                "note": "Projection requires >= 2 measured scales; skipped."}
    xs = [math.log(n) for n in scales]
    ys = [math.log(per_scale[n]["sparql_detection_ms"]["mean"]) for n in scales]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    a = math.exp(my - b * mx)
    proj = {}
    for s in PROJECTED_SCALES:
        est_ms = a * (s ** b)
        proj[str(s)] = {
            "projected_sparql_ms": est_ms,
            "projected_sparql_seconds": est_ms / 1000.0,
            "projected_sparql_minutes": est_ms / 60000.0,
        }
    return {
        "power_law": {"a": a, "b": b,
                      "model": "sparql_ms ≈ a * n^b (fit on measured scales)"},
        "estimates": proj,
        "note": "Projected, NOT measured. 25K/50K/100K were deliberately not run; "
                "the projected runtimes establish infeasibility at enterprise scale.",
    }


def _print_summary(out):
    print("\n" + "=" * 74)
    print("E6: SHACL-SPARQL baseline — expressivity parity at prohibitive latency")
    print("=" * 74)
    print(f"  Preset={out['preset']}, {out['n_seeds']} seeds, "
          f"engine pyshacl {out['engine'].get('pyshacl')} / rdflib {out['engine'].get('rdflib')}\n")
    print(f"  {'Scale':>7s} | {'T-RKG ms':>14s} | {'SHACL-SPARQL ms':>18s} | {'ratio (×)':>14s}")
    print("  " + "-" * 62)
    for n in out["measured_scales"]:
        s = out["per_scale"][str(n)]
        t = s["trkg_detection_ms"]; q = s["sparql_detection_ms"]; r = s["latency_ratio_sparql_over_trkg"]
        print(f"  {n:7d} | {t['mean']:8.2f}±{t['std']:5.2f} | "
              f"{q['mean']:10.1f}±{q['std']:6.1f} | {r['mean']:8.0f}±{r['std']:5.0f}")
    print("\n  Recall vs T-RKG (reference) by family, per scale:")
    for n in out["measured_scales"]:
        s = out["per_scale"][str(n)]
        print(f"    n={n}:")
        for f in out["expressible_families"]:
            rc = s["recall_by_family"][f]
            tc = s["trkg_flagged_by_family"][f]; qc = s["sparql_flagged_by_family"][f]
            print(f"      {f:20s} recall={rc['mean']:.3f}±{rc['std']:.3f}  "
                  f"(T-RKG {tc['mean']:.0f}, SHACL {qc['mean']:.0f})")
    print("\n  Families SHACL-SPARQL still cannot express (recall = 0 by construction):")
    for sk in out["skipped_rule_families"]:
        print(f"    - {sk['rule']}")
    print("\n  Projected (NOT measured) SHACL-SPARQL runtime at larger scales:")
    for s, est in out["projection"]["estimates"].items():
        print(f"    n={s:>7s}: ~{est['projected_sparql_seconds']:.1f}s "
              f"({est['projected_sparql_minutes']:.1f} min)")
    pl = out["projection"]["power_law"]
    print(f"    power-law fit: ms ≈ {pl['a']:.3g} · n^{pl['b']:.2f}")


def write_results(out):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, "e6.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n  Wrote {path}")
    return path


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    seeds = SEEDS[:2] if quick else SEEDS
    scales = [1000, 5000] if quick else MEASURED_SCALES
    out = run(seeds=seeds, scales=scales)
    _print_summary(out)
    write_results(out)
