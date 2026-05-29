# T-RKG Experiments — Summary & Status

This document tracks the six experiments (E1–E6) strengthening the T-RKG paper.
Each completed experiment writes an isolated `experiments/results/<id>.json` and a
paper-ready `experiments/results/<id>_RESULTS.md`.

## STATUS (as of 2026-05-28)

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

### Partially run — code & tests complete, full data run NOT finished

- **E6 — SHACL-SPARQL baseline.**
  `experiments/e6_shacl_sparql.py`, `trkg/baselines/shacl_sparql_baseline.py`,
  `tests/test_e6.py` (11 tests, green). The baseline expresses the three
  families SHACL Core cannot (RETENTION_DELETION, HOLD_DELETION with Art. 17(3)
  defeasibility, JURISDICTION) and declares the two it still cannot (PRIORITY,
  hold-propagation closure).
  - **Hold-context bug fixed:** the generator populates zero `hold_matters`;
    E6 now applies an identical round-robin hold context to the store BEFORE
    both detectors run, so T-RKG vs SHACL-SPARQL recall is apples-to-apples.
  - **HOLD_DELETION recall gap is a finding, not a bug:** SHACL recovers
    exactly the GDPR-exemption subset; it misses CPRA/PIPEDA erasure-under-hold
    that T-RKG fires, because Art. 17(3) is GDPR-specific and a single
    wholesale-suppression shape cannot encode it per-regulation.
  - **Preliminary (2-seed) numbers** from the quick run: T-RKG ~6 ms vs
    SHACL-SPARQL ~21 s at 1K (ratio ~3300×); JURISDICTION recall 1.00;
    HOLD_DELETION recall ~0.53; latency scales ~linearly (n^1.0). These are NOT
    committed as results.
  - **PENDING:** the full 1K/5K/10K × 10-seed sweep was launched but
    interrupted (laptop taken). `results/e6.json` currently on disk is the
    **2-seed quick run** and is intentionally NOT committed. Re-run with
    `python experiments/e6_shacl_sparql.py` (~55 min) to produce the final
    10-seed `e6.json`, then write `results/e6_RESULTS.md` framing the result as
    *expressivity parity at ~10³–10⁴× T-RKG latency → infeasible at enterprise
    scale*, with 25K/50K/100K reported as projected-infeasible.

### Pending — not started

- **E1 — LLM applicability baseline.** NOT STARTED this session. No module, no
  scaffold, and `experiments/cache/` is **empty** — there are no cached LLM
  responses because nothing was run. BLOCKED on `ANTHROPIC_API_KEY`. Plan:
  build scaffold + tests, cache every response to disk, write `STATUS: BLOCKED`
  until a key is available. Do not fabricate or estimate any number.
- **E2 — Enron loader.** NOT STARTED (per instruction). Must scaffold only;
  must NOT silently download ~1.7 GB or install dependencies. BLOCKED on
  data + NER.
- **E4 — Independent-expert labeling kit.** NOT STARTED (per instruction).
  PREP ONLY — do not fill in labels.

### Cross-cutting work completed earlier (committed with this batch)

- **Set-ordering determinism fix** in `experiments/run_all.py` (sorted set
  iteration at the seed-selection sites). The canonical `experiments/results.json`
  was regenerated; the propagation/hold-set family changed (intended), and every
  other deterministic number is bit-identical to the pre-fix backup. This
  deterministic version is now canonical.
- **`additional_jurisdictions`** field on `Record` (`trkg/schema.py`) and the
  multi-jurisdiction overlay (`trkg/synthetic.py`), proven inert by default.
- **Shared siloed/decomposed partition core** (`trkg/composition.py`).

## Next steps (in order)

1. Re-run the full E6 sweep → final `results/e6.json` + `results/e6_RESULTS.md`.
2. E1 scaffold + cache + tests (will report BLOCKED without an API key).
3. E2 Enron loader scaffold (BLOCKED) and E4 labeling kit (PREP ONLY).
4. Wave 2: merge `results/*.json` without clobbering existing entries.
5. Wave 3: data-driven figures, consistency check, `run_all` wiring
   (`--skip-external`), full suite green, finalize this summary.
