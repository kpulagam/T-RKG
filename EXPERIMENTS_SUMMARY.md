# T-RKG Experiments — Summary & Status

This document tracks the six experiments (E1–E6) strengthening the T-RKG paper.
Each completed experiment writes an isolated `experiments/results/<id>.json` and a
paper-ready `experiments/results/<id>_RESULTS.md`.

## STATUS (as of 2026-05-29)

### Finished — code, tests, data, and RESULTS.md all complete

- **E3 — Multi-jurisdiction balanced preset.**
  `experiments/e3_multijurisdiction.py`, `trkg/synthetic.py::balanced_config`,
  `tests/test_e3.py` (7 tests, green). Data: `results/e3.json` +
  `results/e3_RESULTS.md` (10 seeds, 10K records). All four conflict families
  populated; GDPR-CPRA and GDPR-PIPEDA verified to fire; Axiom-4 (Art. 17(3))
  suppression Δ=1415, p=0.00195, d=2.56. The default generator still emits
  **zero** records with a non-empty `additional_jurisdictions` (verified by
  test), so existing datasets/results are byte-identical — this closes the
  §VIII-E limitation additively.

- **E5 — Cross-system composition ablation.**
  `experiments/e5_composition.py`, `trkg/composition.py`, `tests/test_e5.py`
  (6 tests, green) and `tests/test_composition.py`. Data: `results/e5.json` +
  `results/e5_RESULTS.md` (10 seeds, 10K records). Composed 445±57 vs
  decomposed 347±55 total conflicts; cross-domain 98±27 → **0 on every seed**;
  applicability F1 1.000 → 0.702. All paired tests p=0.00195.

- **E1 — LLM applicability baseline, composed vs siloed.**
  `trkg/baselines/llm_baseline.py`, `experiments/e1_llm_baseline.py`,
  `tests/test_e1.py` (13 tests, green; mock client, no network). Run with a real
  key (`claude-opus-4-7`), 10 seeds × 200-record representative sample, two views
  × two regimes. Headline = **composed − siloed F1 gap**: clean composed micro F1
  **0.988** (macro 0.940, cross-domain recall 0.997) → siloed **0.266**
  (cross-domain recall **0.000**), Δ=0.724, p=0.00195, d=24.5. Noised regime
  composed 0.889 → siloed 0.247. **Validity invariant** ontology-siloed
  cross-domain recall = 0.000 (partition sound; leak gate
  `assert_no_cross_system_triggers` passes on every view). `results/e1.json`
  `status="COMPLETE"`; full run is 232 unique cached API calls (then
  `api_calls=0`). See `results/e1_RESULTS.md`.
  - **Two bugs caught before reporting:** (1) the original first-200-by-id sample
    returned only CHAT records, starving 6 of 9 regs to F1=0 — fixed with a seeded
    representative sample; (2) `paired_permutation_test` reported an impossible
    p=0.0 on the clean gap (float-order boundary issue) — fixed with a tolerance
    so the two-sided floor 2/2ⁿ holds. E3/E5/E6 (already at the 0.00195 floor) are
    unaffected.

- **E6 — SHACL-SPARQL baseline.**
  `experiments/e6_shacl_sparql.py`, `trkg/baselines/shacl_sparql_baseline.py`,
  `tests/test_e6.py` (11 tests, green). Full **10-seed** sweep at 1K/5K/10K done;
  `results/e6.json` + `results/e6_RESULTS.md` written. Both detectors run under
  an identical round-robin hold context (apples-to-apples).
  - **Latency:** SHACL-SPARQL is **~3×10³ slower** (2,800–3,300×), linear
    `ms ≈ 20.6·n^1.00`: 21.3 s / 106 s / 215 s at 1K/5K/10K vs T-RKG 6.6/33/111 ms.
    Projected 25K/50K/100K ≈ 9 / 18 / 36 min → infeasible at enterprise scale.
  - **Expressivity is QUALITATIVE, not full parity (honest divergence from the
    going-in framing):** recall vs T-RKG is JURISDICTION **1.000**,
    RETENTION_DELETION **~0.50**, HOLD_DELETION **~0.40**; PRIORITY and
    hold-propagation closure are inexpressible (0). The partials are structural:
    each `sh:sparql` shape hand-encodes ONE regulation pair (RETENTION shape =
    EU-PII × SOX public-company), so it misses CPRA/PIPEDA deletion and
    non-public retention; T-RKG composes the full cross-product. Closing the gap
    = combinatorial per-pair shape authoring → the maintainability argument.
  - **Two reporting corrections vs the original framing:** the latency multiplier
    is **~3×10³, not 10⁴–10⁵** (measured), and it is **expressivity gain over
    SHACL Core, not parity** (RETENTION/HOLD only ~0.4–0.5 recall). Reported as
    measured per the honesty contract.

### Descoped — deliberately not pursued

- **E2 — Enron loader. DESCOPED (not blocked).** Enron was evaluated in prior
  work and not pursued; the synthetic-only limitation is already stated honestly
  in the paper, and **E4 covers the ground-truth-circularity concern better** (an
  independent human labeler scores T-RKG's own applicability verdicts). No Enron
  loader is scaffolded.

### Pending — E4 label-then-score kit (prep only; human labels then scoring)

- **E4 — Independent-expert applicability labeling.** A *label-then-score*
  experiment, not a run experiment. Dataset is **provided** (not generated here):
  `experiments/labeling/E4_labeling_sheet.csv` (146 records, attributes populated,
  nine regulation columns blank for a human labeler, plus `unsure`) and
  `experiments/labeling/E4_reference_key.csv` (an externally-computed reference
  answer — **NOT ground truth**). Hidden ground truth is T-RKG's own applicability
  predicate run over each row → `experiments/labeling/ground_truth_hidden.json`.
  Workflow: (Step 4) diff T-RKG verdicts vs the reference key for human review
  → (Step 5) scorer `experiments/labeling/score_labels.py` + `INSTRUCTIONS.md`
  for the labeler. **PREP ONLY — no label values are ever written by the agent.**

### Cross-cutting work completed earlier (committed with this batch)

- **Set-ordering determinism fix** in `experiments/run_all.py` (sorted set
  iteration at the seed-selection sites). The canonical `experiments/results.json`
  was regenerated; the propagation/hold-set family changed (intended), and every
  other deterministic number is bit-identical to the pre-fix backup. This
  deterministic version is now canonical.
- **`additional_jurisdictions`** field on `Record` (`trkg/schema.py`) and the
  multi-jurisdiction overlay (`trkg/synthetic.py`), proven inert by default.
- **Shared siloed/decomposed partition core** (`trkg/composition.py`), now also
  used by E1's siloed arm.
- **Permutation-test floor fix** in `experiments/stats_utils.py`: a float-order
  boundary issue let `paired_permutation_test` return an impossible p=0.0 on a
  large clean separation; a tolerance restores the two-sided floor 2/2ⁿ. Found
  via E1; E3/E5/E6 (already at the floor) are unchanged.

## Next steps (in order)

1. ~~Re-run the full E6 sweep~~ DONE — `results/e6.json` (10 seeds) +
   `results/e6_RESULTS.md` written.
2. ~~E1 scaffold + cache + tests~~ + ~~full composed-vs-siloed run~~ DONE
   (COMPLETE; see above).
3. ~~E2 Enron loader~~ DESCOPED (prior-work eval, not pursued; §VIII limitation
   stated; E4 covers ground-truth circularity better). E4 label-then-score kit:
   ground truth generated → diff for review (STOP) → scorer + INSTRUCTIONS (PREP
   ONLY; agent never writes labels).
4. Wave 2: merge `results/*.json` without clobbering existing entries.
5. Wave 3: data-driven figures, consistency check, `run_all` wiring
   (`--skip-external`), full suite green, finalize this summary.
6. Commit E1 (scaffold + cache + composed/siloed run), E6 (final 10-seed data +
   RESULTS), and the stats fix — not yet committed.
