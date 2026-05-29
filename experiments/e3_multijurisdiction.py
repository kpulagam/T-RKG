#!/usr/bin/env python3
"""E3 — Multi-jurisdiction balanced preset.

The paper's §VIII-E limitations section anticipates a multi-jurisdiction
extension: a record subject to more than one privacy regime. The default
generator never produces such records (it is single-jurisdiction by
construction), so the JURISDICTION conflict family — GDPR vs. CPRA, GDPR vs.
PIPEDA — is exercised by the ontology but starved of data. E3 closes that
limitation with a *named, additive* generator preset (trkg.synthetic.
balanced_config) that overlays a second privacy regime on a fraction of
records, without touching the default generator or any existing dataset.

This experiment demonstrates, across the canonical 10-seed set, that under the
balanced preset:

  1. the multi-jurisdiction overlay populates (count of dual-regime records),
  2. ALL FOUR conflict families are non-empty in one dataset
     (RETENTION_DELETION, JURISDICTION, HOLD_DELETION, PRIORITY),
  3. the JURISDICTION family is *verified, not just enabled*: both GDPR-CPRA
     and GDPR-PIPEDA fire,
  4. the GDPR Art. 17(3) defeasibility (Axiom 4) measurably suppresses
     HOLD_DELETION conflicts (paired permutation test + Cohen's d on the
     per-seed suppression).

Writes experiments/results/e3.json (isolated; merged later). Deterministic
from the seed; no external dependencies.
"""

import os
import sys
import json
import random
import statistics
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trkg import SyntheticDataGenerator, ConflictDetector
from trkg.synthetic import balanced_config
from trkg.schema import Jurisdiction
from experiments.stats_utils import (
    SEEDS, paired_permutation_test, cohens_d_paired,
)

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
DATASET_SIZE = 10000

EU_JURISDICTIONS = {
    Jurisdiction.EU, Jurisdiction.EU_DE, Jurisdiction.EU_ES, Jurisdiction.EU_FR,
}
FAMILIES = ["RETENTION_DELETION", "JURISDICTION", "HOLD_DELETION", "PRIORITY"]


def _agg(values):
    m = statistics.mean(values)
    s = statistics.stdev(values) if len(values) > 1 else 0.0
    return {"mean": m, "std": s, "values": list(values)}


def _fmt(agg, prec=1):
    return f"{agg['mean']:.{prec}f} ± {agg['std']:.{prec}f}"


def run(seeds=SEEDS, num_records=DATASET_SIZE):
    per_seed = {
        "multi_juris_records": [],
        "gdpr_cpra": [], "gdpr_pipeda": [],
        "hold_deletion_without_suppression": [],
        "hold_deletion_with_suppression": [],
        "suppressed_by_exemption": [],
    }
    for fam in FAMILIES:
        per_seed[f"family_{fam}"] = []

    for seed in seeds:
        gen = SyntheticDataGenerator(balanced_config(num_records), seed=seed)
        store = gen.generate()

        per_seed["multi_juris_records"].append(
            sum(1 for r in store.records.values() if r.additional_jurisdictions))

        # Distribute holds round-robin across matters over the EU+PII
        # population, exactly as the Art. 17(3) impact experiment does, so the
        # HOLD_DELETION family and the Axiom-4 suppression are well populated.
        matters = list(store.matters.values())
        targets = [r.id for r in store.records.values()
                   if r.contains_pii and r.jurisdiction in EU_JURISDICTIONS]
        rng = random.Random(seed)
        for tid in targets:
            m = rng.choice(matters)
            store.apply_hold(m.id, [tid], assignment_type="DIRECT")
        active = {m.id for m in matters}

        # Suppression OFF (no matters dict): the raw HOLD_DELETION count.
        det_no = ConflictDetector()
        res_no = det_no.detect_all_conflicts(store.records, active_hold_matters=active)
        # Suppression ON (matters dict): Art. 17(3) exemptions applied.
        det = ConflictDetector(matters=store.matters)
        res = det.detect_all_conflicts(store.records, active_hold_matters=active)

        by_type = res.conflicts_by_type
        for fam in FAMILIES:
            per_seed[f"family_{fam}"].append(by_type.get(fam, 0))

        by_pair = res.conflicts_by_regulation_pair
        per_seed["gdpr_cpra"].append(by_pair.get("GDPR-CPRA", 0))
        per_seed["gdpr_pipeda"].append(by_pair.get("GDPR-PIPEDA", 0))

        per_seed["hold_deletion_without_suppression"].append(
            res_no.conflicts_by_type.get("HOLD_DELETION", 0))
        per_seed["hold_deletion_with_suppression"].append(
            by_type.get("HOLD_DELETION", 0))
        per_seed["suppressed_by_exemption"].append(det.suppressed_exemption_count)

    aggregates = {k: _agg(v) for k, v in per_seed.items()}

    obs, p = paired_permutation_test(
        per_seed["hold_deletion_without_suppression"],
        per_seed["hold_deletion_with_suppression"])
    axiom4 = {
        "observed_mean_diff": obs,
        "p_value": p,
        "cohens_d": cohens_d_paired(
            per_seed["hold_deletion_without_suppression"],
            per_seed["hold_deletion_with_suppression"]),
    }

    # Validity assertions baked into the result so a regression is visible.
    all_families_nonempty = all(
        all(v > 0 for v in per_seed[f"family_{fam}"]) for fam in FAMILIES)
    jurisdiction_family_verified = (
        all(v > 0 for v in per_seed["gdpr_cpra"])
        and all(v > 0 for v in per_seed["gdpr_pipeda"]))

    return {
        "experiment": "E3",
        "title": "Multi-jurisdiction balanced preset (closes §VIII-E limitation)",
        "dataset_size": num_records,
        "preset": "balanced_config",
        "seeds": list(seeds),
        "n_seeds": len(seeds),
        "per_seed": per_seed,
        "aggregates": aggregates,
        "axiom4_suppression": axiom4,
        "all_four_families_nonempty": all_families_nonempty,
        "jurisdiction_family_verified": jurisdiction_family_verified,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }


def _print_summary(out):
    a = out["aggregates"]
    print("\n" + "=" * 70)
    print("E3: Multi-jurisdiction balanced preset")
    print("=" * 70)
    print(f"  Dataset: {out['dataset_size']:,} records, {out['n_seeds']} seeds, "
          f"preset={out['preset']}\n")
    print(f"  Multi-jurisdiction records: {_fmt(a['multi_juris_records'],0)}")
    print("\n  Conflict families (suppression active):")
    for fam in FAMILIES:
        print(f"    {fam:20s}: {_fmt(a['family_'+fam],0):>14s}")
    print("\n  JURISDICTION family breakdown (the closed limitation):")
    print(f"    {'GDPR-CPRA':20s}: {_fmt(a['gdpr_cpra'],0):>14s}")
    print(f"    {'GDPR-PIPEDA':20s}: {_fmt(a['gdpr_pipeda'],0):>14s}")
    print("\n  Axiom 4 (GDPR Art. 17(3)) HOLD_DELETION suppression:")
    print(f"    without suppression: {_fmt(a['hold_deletion_without_suppression'],0)}")
    print(f"    with suppression   : {_fmt(a['hold_deletion_with_suppression'],0)}")
    print(f"    suppressed         : {_fmt(a['suppressed_by_exemption'],0)}")
    s = out["axiom4_suppression"]
    print(f"    paired test: Δ={s['observed_mean_diff']:.2f}  "
          f"p={s['p_value']:.4g}  d={s['cohens_d']:.3f}")
    print(f"\n  All four families non-empty (every seed): "
          f"{out['all_four_families_nonempty']}")
    print(f"  JURISDICTION family verified (GDPR-CPRA & GDPR-PIPEDA, every seed): "
          f"{out['jurisdiction_family_verified']}")


def write_results(out):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, "e3.json")
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
