# E1 — LLM applicability baseline: composed vs siloed

**STATUS: COMPLETE** (`claude-opus-4-7`, 10 seeds × 200-record representative
sample, two views × two data regimes).
**Code:** `trkg/baselines/llm_baseline.py`, `experiments/e1_llm_baseline.py`
**Tests:** `tests/test_e1.py` (13 tests, green — mock client, no network).
**Data:** `experiments/results/e1.json` (`status="COMPLETE"`).

## What this measures

Regulation **applicability** — given a record's attributes, which of the nine
profiled regulations govern it — is a precise, checkable classification that
T-RKG's ontology answers deterministically
(`ConflictDetector.infer_applicable_regulations`). E1 asks an LLM the same
question, handed the same nine scope rules, and scores it against the ontology
(the reference). The headline is **not** the absolute LLM score; it is the
**composed − siloed gap**:

- **Composed view:** the LLM sees the full record (all governance-relevant
  attributes, which in a real enterprise live in different source systems).
- **Siloed view:** the LLM sees only the attributes whose *home source system*
  equals the record's own (`trkg/composition.siloed_view`, per the partition map
  in `ATTRIBUTE_HOME_SYSTEM`: PII/PHI → CRM, public-company status → ERP). Every
  foreign trigger attribute is masked, exactly as a single system reasoning in
  isolation would see it.

Each view is run in a **clean** regime and a **noised** regime (10 % per-attribute
label flips on jurisdiction/PII/public-company; ground truth keyed on the
*pre-noise* labels, identical to the paper's other applicability baselines).

## Headline — composed vs siloed (micro F1, per-seed, 10 seeds)

| Regime | View | Micro F1 | Macro F1 | Cross-domain recall |
|---|---|---|---|---|
| clean  | **composed** | **0.988** | 0.940 | 0.997 ± 0.008 |
| clean  | **siloed**   | **0.266** | 0.572 | **0.000 ± 0.000** |
| noised | composed | 0.889 | 0.897 | 0.875 ± 0.044 |
| noised | siloed   | 0.247 | 0.547 | **0.000 ± 0.000** |

**Composed − siloed F1 gap (paired permutation, 10 seeds; Cohen's d on per-seed diffs):**

| Regime | Δ F1 | p | Cohen's d |
|---|---|---|---|
| clean  | **0.724** | **0.00195** | 24.5 |
| noised | 0.644 | 0.00195 | 19.7 |

p = 0.00195 is the exact two-sided floor for n = 10 (2 / 2¹⁰); the per-seed gaps
are uniform in sign, so the test is maximally significant.

### Validity invariant (the result is only valid if this holds)

Cross-domain recall is recall on the PII-triggered deletion regs (GDPR/CPRA/PIPEDA)
in the *true* applicability of **non-CRM** records — precisely the applicabilities
that depend on an attribute the record's home system does not own. Under the
siloed view that attribute is masked, so this recall **must** collapse to ≈ 0;
a non-zero value would mean the partition leaked. As an LLM-independent check we
also run the **ontology** on the siloed views:

> **ontology-siloed cross-domain recall = 0.000 ± 0.000** (both regimes)

Every siloed view additionally passes the boundary-#1 leak gate
(`assert_no_cross_system_triggers`, `trkg/composition.py:83`) before
classification, so a leaking partition would fail loudly rather than inflate
recall. The invariant holds: the partition genuinely destroys cross-system
applicability rather than the LLM merely guessing it away.

## Per-regulation F1 (composed)

| Regulation | clean | noised |
|---|---|---|
| GDPR | 1.000 | 0.864 |
| SOX | 1.000 | 0.967 |
| HIPAA | 0.886 | 0.840 |
| SEC | 0.974 | 0.976 |
| FINRA | 0.909 | 1.000 |
| CPRA | 0.995 | 0.910 |
| PIPEDA | 1.000 | 0.907 |
| IRS | **0.696** | 0.708 |
| HGB | 1.000 | 0.900 |

## Interpretation

The 0.988 is the **clean, composed** number — the LLM's best case, with every
attribute visible and no data noise. It is impressive in aggregate but (a)
**macro F1 is only 0.940**, because micro F1 is support-weighted and hides the
LLM's weakness on the overlapping US financial regimes (**IRS 0.696**, HIPAA
0.886, FINRA 0.909), and (b) it is **not robust to data noise** — composed F1
falls to 0.889 under 10 % label noise, while the deterministic ontology's gap is
structural, not stochastic.

The headline, though, is the **collapse under siloing**: deny the model the
cross-system attributes and applicability F1 falls from 0.988 to **0.266**
(Δ = 0.724, p = 0.00195, d = 24.5), with **cross-domain recall going to exactly
zero**. This is the paper's core claim made measurable on the *easiest* sub-task:
a strong LLM cannot recover a governance decision whose evidence is split across
systems, no matter how capable it is, because the information is simply not in
its input. Composition is not a modeling nicety — it is a prerequisite, and
T-RKG supplies it by construction while the siloed baseline (and any system that
reasons within one source) cannot.

## Cost and reproducibility

- **Representative sampling:** `random.Random(seed).sample(...)` over the
  id-sorted records (200/seed). Record ids are `"{type}_{n}"`, so the earlier
  *first-N-by-id* shortcut returned 200 CHAT records only and starved six of
  nine regs of support; the seeded random sample spans all record types and is
  fully reproducible (no `PYTHONHASHSEED` reliance). The same records are scored
  composed and siloed, so the gap is a genuine paired comparison.
- **Disk cache** (`experiments/cache/llm/`): keyed by sha256(model + prompt).
  The full 2-view × 2-regime run is 8,000 classifications that dedupe (masking
  lowers feature cardinality) to **232 unique prompts = 232 API calls total**;
  every subsequent run is fully cache-served (`api_calls=0`).
- **Honesty contract intact:** with no key and no cache, `classify()` raises
  `LLMUnavailable` and the driver writes `status="BLOCKED"` with no fabricated
  metrics.

```bash
export ANTHROPIC_API_KEY=sk-...
python experiments/e1_llm_baseline.py        # 232 calls first run, then cached
```

## Note on a stats bug found and fixed

The clean-regime gap initially reported `p = 0.0`, which is impossible for a
two-sided permutation test (floor 2/2ⁿ). Cause: in
`stats_utils.paired_permutation_test`, `observed = sum(diffs)/n` (builtin `sum`)
and the per-mask statistic (repeated `+=`) accumulate in different float orders,
so for a large, clean separation the identity/all-flip permutations fell ~1e-16
below `|observed|` and were wrongly excluded. Fixed by comparing against
`|observed| − tol`. Experiments already reporting the 0.00195 floor (E3, E5, E6)
are unaffected — they had already counted the boundary permutations.

## Paper mapping

- **Headline table:** composed vs siloed micro F1 (0.988 → 0.266), with the gap's
  p and Cohen's d. This is the LLM analogue of the E5 composition ablation.
- **Macro F1 (0.940)** reported alongside micro to expose per-regulation weakness.
- **Validity row:** ontology-siloed cross-domain recall = 0.000 (the partition is
  sound, not leaking).
- **Robustness row:** composed F1 0.988 (clean) → 0.889 (noised).
