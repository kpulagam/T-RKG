# E5 — Cross-system composition ablation

**Status:** COMPLETE. Deterministic from seed; no external dependencies.
**Code:** `experiments/e5_composition.py`, `trkg/composition.py`
**Tests:** `tests/test_e5.py` (6 tests)
**Data:** `experiments/results/e5.json`
**Config:** default generator, 10,000 records/seed, canonical 10-seed set.

## The claim under test

T-RKG's central thesis is that a single governance decision is driven by
attributes that, in a real enterprise, live in *different* source systems
(e.g. a record's content system says "PII", a separate matter system says
"on hold"). E5 turns composition into a switch and measures what is lost when
it is removed:

- **COMPOSED** — the full record, every attribute visible (what T-RKG sees).
- **DECOMPOSED** — the siloed view (`trkg.composition.siloed_view`): every
  attribute whose home source system differs from the record's own system is
  masked, so no cross-system attribute pair can co-occur.

The detector and dataset are held identical; only cross-system attribute
visibility changes. If composition is the source of T-RKG's cross-domain
conflicts, the decomposed view must lose them.

## Results (mean ± σ over 10 seeds)

| Metric | Composed | Decomposed | Δ (paired) | p | Cohen's d |
|---|---|---|---|---|---|
| Total conflicts | 445 ± 57 | 347 ± 55 | 98.3 | 0.00195 | 3.69 |
| Cross-domain conflicts | 98 ± 27 | **0 ± 0** | 98.3 | 0.00195 | 3.69 |
| Applicability F1 | 1.000 ± 0.000 | 0.702 ± 0.040 | 0.298 | 0.00195 | 7.39 |
| Applicability recall | 1.000 ± 0.000 | 0.542 ± 0.048 | — | — | — |

Decomposed cross-domain conflicts are **exactly 0 on every seed**
(`[0,0,0,0,0,0,0,0,0,0]`), enforced as a validity invariant by
`assert_no_cross_system_triggers` and by `tests/test_e5.py`. Composed
cross-domain per seed: `[115, 93, 106, 136, 47, 63, 121, 91, 101, 110]`.

Paired permutation test: 10,000 sign-flips, exact enumeration for n=10. All
three p-values hit the exact floor (2/2¹⁰ = 0.00195) because the composed view
dominates the decomposed view on every single seed — the strongest result the
test can express.

## Interpretation (2–3 sentences)

Removing cross-system composition eliminates **100%** of T-RKG's cross-domain
conflicts (98 ± 27 → 0) and drops per-record applicability recall from perfect
to 0.54, because a siloed view cannot see the foreign attribute that makes a
second regulation apply. This isolates composition — not the rule base or the
dataset — as the mechanism behind the cross-domain detections, which is exactly
the novelty the paper claims. The effect is large (d = 3.7 for conflicts, 7.4
for F1) and unanimous across seeds.

## Caveats

- "Cross-domain" is defined as RETENTION_DELETION + JURISDICTION +
  HOLD_DELETION (the families whose triggers can span systems); PRIORITY is
  intra-financial and excluded by construction.
- The decomposed F1 is scored against the *composed* clean-label ground truth
  (the correct answer), so the decomposed predictor is deliberately handicapped
  — that handicap is the quantity of interest, not a bug.
- Applicability F1 = 1.000 ± 0.000 on the composed view reflects that, with
  zero label noise in this preset, the inferred regulation set exactly matches
  the clean-label truth; noise-driven recovery accuracy is a separate
  experiment.

## Paper mapping

- Cross-system composition novelty / ablation table: the composed-vs-decomposed
  rows above.
- The decomposed-recall ≈ 0 cross-domain result is the falsifiable validity
  invariant; cite the unit test that pins it.
- Manuscript table numbering has diverged from code labels; key these rows by
  *content* (composition ablation) rather than a code table number.
