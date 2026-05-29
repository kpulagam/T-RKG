#!/usr/bin/env python3
"""E1 — LLM applicability baseline.

Compares an LLM's regulation-applicability predictions against T-RKG's ontology
(the reference) on a deterministic sample of records, reporting micro
precision/recall/F1 and per-regulation F1.

HONESTY / BLOCKED behaviour: this experiment calls a paid API. It runs only if
either (a) an ANTHROPIC_API_KEY is present, or (b) every sampled record already
has a cached response on disk. Otherwise it writes a results file with
status="BLOCKED" and fabricates NO metrics. Responses are cached so a later run
with a key resumes without re-billing.

Sampling: to bound cost, a fixed number of records per seed is scored (sorted by
record id, first N — deterministic), NOT the full 10K. The sample size is
recorded in the output.

Usage:
  python experiments/e1_llm_baseline.py            # real run iff key/cache
  python experiments/e1_llm_baseline.py --quick    # 2 seeds, tiny sample
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
from trkg.composition import (
    siloed_view, assert_no_cross_system_triggers, ATTRIBUTE_HOME_SYSTEM,
)
from trkg.baselines.llm_baseline import (
    LLMApplicabilityBaseline, LLMUnavailable, make_anthropic_client,
    REGULATION_CODES, DEFAULT_MODEL,
)
from experiments.stats_utils import SEEDS, paired_permutation_test, cohens_d_paired

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
DATASET_SIZE = 10000
SAMPLE_PER_SEED = 200

# PII-triggered deletion regulations. PII is owned by the CRM system
# (trkg.composition.ATTRIBUTE_HOME_SYSTEM), so for any non-CRM record the
# applicability of these regs is a CROSS-SYSTEM decision: it hinges on an
# attribute the record's home system does not own. The siloed view masks that
# attribute, so siloed cross-domain recall must collapse to ~0 (validity
# invariant). A non-zero siloed cross-domain recall under the leak gate would
# mean the partition leaked and the result is invalid.
DELETION_REGS = {"GDPR", "CPRA", "PIPEDA"}
CRM_HOME = "sys_crm"
NOISE_RATE = 0.10


def _ground_truth_factory(detector, clean_labels):
    """True (composed, PRE-noise) applicability for a record, restricted to the
    predictable universe. Mirrors experiments.run_all._ground_truth_factory so
    the LLM is scored against the same reference the paper uses for its other
    baselines: the labels are keyed on pre-noise attributes, independent of any
    noise the classifier sees."""
    from trkg.schema import Record
    profiles = detector.profiles

    def truth_for(rec):
        clean = clean_labels.get(rec.id)
        if clean is None:
            regs = {r.value for r in detector.infer_applicable_regulations(rec)}
        else:
            clean_rec = Record(
                id=rec.id, type=rec.type, title=rec.title,
                created=rec.created, modified=rec.modified,
                custodian_id=rec.custodian_id, system_id=rec.system_id,
                jurisdiction=clean["jurisdiction"],
                additional_jurisdictions=list(getattr(rec, "additional_jurisdictions", []) or []),
                contains_pii=clean["contains_pii"],
                contains_phi=clean["contains_phi"],
                metadata={**rec.metadata, "is_public_company": clean["is_public_company"]},
            )
            regs = {reg.value for reg, prof in profiles.items() if prof.applies_to(clean_rec)}
        return regs & set(REGULATION_CODES)

    return truth_for


def _prf1(tp, fp, fn):
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f


def _agg(values):
    m = statistics.mean(values) if values else 0.0
    s = statistics.stdev(values) if len(values) > 1 else 0.0
    return {"mean": m, "std": s, "values": list(values)}


def _macro_f1(per_reg):
    """Unweighted mean of per-regulation F1 — gives every regulation equal voice,
    unlike micro (support-weighted), so it surfaces the weak regs (IRS/HIPAA)."""
    return statistics.mean(
        _prf1(d["tp"], d["fp"], d["fn"])[2] for d in per_reg.values()
    )


def _classify_sample(sample, view_fn, truth_fn, baseline, leak_gate):
    """Score one seed's sample under a view. Returns (micro_counts,
    per_reg_counts, (cd_hit, cd_total)). `view_fn` maps a record to the view the
    LLM sees (identity for composed, siloed_view for siloed). When `leak_gate`,
    every siloed view is asserted free of foreign trigger attributes (boundary
    #1) so a leaking partition fails loudly. Cross-domain pairs are the PII-
    triggered deletion regs in the TRUE applicability of non-CRM records."""
    micro = {"tp": 0, "fp": 0, "fn": 0}
    per_reg = {c: {"tp": 0, "fp": 0, "fn": 0} for c in REGULATION_CODES}
    cd_hit = cd_total = 0
    for rec in sample:
        view = view_fn(rec)
        if leak_gate:
            assert_no_cross_system_triggers(view)
        pred = baseline.classify(view)               # may raise LLMUnavailable
        truth = truth_fn(rec)
        micro["tp"] += len(pred & truth)
        micro["fp"] += len(pred - truth)
        micro["fn"] += len(truth - pred)
        for c in REGULATION_CODES:
            per_reg[c]["tp"] += (c in pred and c in truth)
            per_reg[c]["fp"] += (c in pred and c not in truth)
            per_reg[c]["fn"] += (c not in pred and c in truth)
        if rec.system_id != CRM_HOME:
            cd = DELETION_REGS & truth
            cd_total += len(cd)
            cd_hit += len(cd & pred)
    return micro, per_reg, (cd_hit, cd_total)


def _ontology_siloed_cross_domain_recall(sample, detector, truth_fn):
    """Validity invariant (independent of the LLM): run the ONTOLOGY on the
    siloed view and measure cross-domain recall. The partition removes the PII
    trigger from every non-CRM record, so this must be ~0 by construction. With
    the leak gate passing, a non-zero value would prove the partition map wrong."""
    cd_hit = cd_total = 0
    for rec in sample:
        view = siloed_view(rec)
        assert_no_cross_system_triggers(view)
        pred = ({r.value for r in detector.infer_applicable_regulations(view)}
                & set(REGULATION_CODES))
        if rec.system_id != CRM_HOME:
            truth = truth_fn(rec)
            cd = DELETION_REGS & truth
            cd_total += len(cd)
            cd_hit += len(cd & pred)
    return cd_hit / cd_total if cd_total else 0.0


def _view_block(micro, per_reg, f1_seed, cd_seed):
    p, r, f = _prf1(micro["tp"], micro["fp"], micro["fn"])
    return {
        "micro": {"precision": p, "recall": r, "f1": f, **micro},
        "macro_f1": _macro_f1(per_reg),
        "per_regulation_f1": {
            c: _prf1(per_reg[c]["tp"], per_reg[c]["fp"], per_reg[c]["fn"])[2]
            for c in REGULATION_CODES
        },
        "per_seed_f1": _agg(f1_seed),
        "cross_domain_recall": _agg(cd_seed),
    }


def run(seeds=SEEDS, num_records=DATASET_SIZE, sample_per_seed=SAMPLE_PER_SEED,
        model=DEFAULT_MODEL, baseline=None, regimes=("clean", "noised")):
    """Score the LLM's applicability predictions against the ontology in two
    views (COMPOSED = full record; SILOED = only home-system attributes per the
    partition map) and, optionally, two data regimes (clean / noised). The
    headline is the composed-minus-siloed F1 gap with a paired-permutation
    p-value and Cohen's d. If `baseline` is injected (mock client in tests) it
    is used; otherwise a real client is created iff a key is present."""
    detector = ConflictDetector()
    if baseline is None:
        baseline = LLMApplicabilityBaseline(model=model, client=make_anthropic_client())

    regime_noise = {"clean": (0.0, 0.0, 0.0),
                    "noised": (NOISE_RATE, NOISE_RATE, NOISE_RATE)}

    out = {
        "experiment": "E1",
        "title": ("LLM regulation-applicability baseline vs T-RKG ontology "
                  "(composed vs siloed; clean vs noised)"),
        "model": model,
        "preset": "balanced_config",
        "dataset_size": num_records,
        "sample_per_seed": sample_per_seed,
        "seeds": list(seeds),
        "n_seeds": len(seeds),
        "regulation_universe": REGULATION_CODES,
        "partition_attribute_home": dict(ATTRIBUTE_HOME_SYSTEM),
        "cross_domain_regs": sorted(DELETION_REGS),
        "noise_rate": NOISE_RATE,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }

    results = {}
    blocked_reason = None
    try:
        for regime in regimes:
            nj, npi, nm = regime_noise[regime]
            comp_micro = {"tp": 0, "fp": 0, "fn": 0}
            silo_micro = {"tp": 0, "fp": 0, "fn": 0}
            comp_per_reg = {c: {"tp": 0, "fp": 0, "fn": 0} for c in REGULATION_CODES}
            silo_per_reg = {c: {"tp": 0, "fp": 0, "fn": 0} for c in REGULATION_CODES}
            comp_f1_seed, silo_f1_seed = [], []
            comp_cd_seed, silo_cd_seed, ont_silo_cd_seed = [], [], []

            for seed in seeds:
                cfg = balanced_config(num_records)
                cfg.noise_jurisdiction_flip = nj
                cfg.noise_pii_flip = npi
                cfg.noise_metadata_flip = nm
                gen = SyntheticDataGenerator(cfg, seed=seed)
                store = gen.generate()
                truth_fn = _ground_truth_factory(detector, gen.clean_labels)
                # Deterministic REPRESENTATIVE sample: record ids are "{type}_{n}",
                # so the first-N-by-id shortcut yields a single record type (all
                # CHAT), starving 6 of 9 regs of support. A seeded random sample
                # over the id-sorted records is reproducible (no PYTHONHASHSEED
                # reliance) and spans all record types. The SAME records are
                # scored composed and siloed, so the gap is a paired comparison.
                ordered = sorted(store.records.values(), key=lambda r: r.id)
                sample = random.Random(seed).sample(ordered, min(sample_per_seed, len(ordered)))

                cm, cpr, (chit, ctot) = _classify_sample(
                    sample, lambda r: r, truth_fn, baseline, leak_gate=False)
                sm, spr, (shit, stot) = _classify_sample(
                    sample, siloed_view, truth_fn, baseline, leak_gate=True)

                for c in REGULATION_CODES:
                    for k in ("tp", "fp", "fn"):
                        comp_per_reg[c][k] += cpr[c][k]
                        silo_per_reg[c][k] += spr[c][k]
                for k in ("tp", "fp", "fn"):
                    comp_micro[k] += cm[k]
                    silo_micro[k] += sm[k]
                comp_f1_seed.append(_prf1(cm["tp"], cm["fp"], cm["fn"])[2])
                silo_f1_seed.append(_prf1(sm["tp"], sm["fp"], sm["fn"])[2])
                comp_cd_seed.append(chit / ctot if ctot else 0.0)
                silo_cd_seed.append(shit / stot if stot else 0.0)
                ont_silo_cd_seed.append(
                    _ontology_siloed_cross_domain_recall(sample, detector, truth_fn))

            observed, pval = paired_permutation_test(comp_f1_seed, silo_f1_seed)
            d = cohens_d_paired(comp_f1_seed, silo_f1_seed)
            results[regime] = {
                "composed": _view_block(comp_micro, comp_per_reg, comp_f1_seed, comp_cd_seed),
                "siloed": _view_block(silo_micro, silo_per_reg, silo_f1_seed, silo_cd_seed),
                "ontology_siloed_cross_domain_recall": _agg(ont_silo_cd_seed),
                "composed_minus_siloed_f1": {
                    "per_seed_composed_f1": comp_f1_seed,
                    "per_seed_siloed_f1": silo_f1_seed,
                    "observed_mean_delta": observed,
                    "p_value": pval,
                    "cohens_d": d,
                },
            }
    except LLMUnavailable as e:
        blocked_reason = str(e)

    out["cache_hits"] = baseline.stats.cache_hits
    out["api_calls"] = baseline.stats.api_calls
    if blocked_reason is not None:
        out["status"] = "BLOCKED"
        out["blocked_reason"] = blocked_reason
        out["note"] = ("No ANTHROPIC_API_KEY and not all sampled records are "
                       "cached. Scaffold + cache are ready; no metrics fabricated.")
        return out

    out["status"] = "COMPLETE"
    out["regimes"] = results
    return out


def _print_summary(out):
    print("\n" + "=" * 70)
    print("E1: LLM applicability baseline -- composed vs siloed, clean vs noised")
    print("=" * 70)
    print(f"  Model={out['model']}  preset={out['preset']}  "
          f"sample/seed={out['sample_per_seed']}  seeds={out['n_seeds']}")
    print(f"  cache_hits={out['cache_hits']}  api_calls={out['api_calls']}")
    if out.get("status") == "BLOCKED":
        print("\n  STATUS: BLOCKED")
        print(f"  {out['blocked_reason']}")
        print(f"  {out['note']}")
        return
    for regime, blk in out["regimes"].items():
        print(f"\n  --- regime: {regime} ---")
        for view in ("composed", "siloed"):
            v = blk[view]
            m = v["micro"]
            print(f"    {view:8s}  microF1={m['f1']:.3f}  macroF1={v['macro_f1']:.3f}  "
                  f"per-seedF1={v['per_seed_f1']['mean']:.3f}±{v['per_seed_f1']['std']:.3f}  "
                  f"cross-domain recall={v['cross_domain_recall']['mean']:.3f}"
                  f"±{v['cross_domain_recall']['std']:.3f}")
        g = blk["composed_minus_siloed_f1"]
        print(f"    GAP composed-siloed F1: Δ={g['observed_mean_delta']:.3f}  "
              f"p={g['p_value']:.5f}  d={g['cohens_d']:.2f}")
        osr = blk["ontology_siloed_cross_domain_recall"]
        print(f"    VALIDITY  ontology-siloed cross-domain recall = "
              f"{osr['mean']:.3f}±{osr['std']:.3f}  (must be ~0)")
        print("    composed per-regulation F1:")
        for c, f1 in blk["composed"]["per_regulation_f1"].items():
            print(f"      {c:8s} {f1:.3f}")


def write_results(out):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, "e1.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n  Wrote {path}")
    return path


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    seeds = SEEDS[:2] if quick else SEEDS
    sample = 10 if quick else SAMPLE_PER_SEED
    out = run(seeds=seeds, sample_per_seed=sample)
    _print_summary(out)
    write_results(out)
