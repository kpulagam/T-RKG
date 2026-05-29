# E3 — Multi-jurisdiction balanced preset

**Status:** COMPLETE. Deterministic from seed; no external dependencies.
**Code:** `experiments/e3_multijurisdiction.py`, `trkg/synthetic.py::balanced_config`
**Tests:** `tests/test_e3.py` (7 tests)
**Data:** `experiments/results/e3.json`
**Config:** balanced preset, 10,000 records/seed, canonical 10-seed set.

## What this closes

The paper's §VIII-E limitations section anticipates a multi-jurisdiction
extension — a record subject to more than one privacy regime. The default
generator is single-jurisdiction by construction, so the JURISDICTION conflict
family (GDPR vs. CPRA, GDPR vs. PIPEDA) is *expressible by the ontology but
starved of data*. E3 is the realization of that extension, delivered as an
**additive, opt-in** generator preset (`balanced_config`). The default
generator is untouched: it still emits **zero** records with a non-empty
`additional_jurisdictions` (verified by `tests/test_e3.py`), so all prior
datasets and results are byte-identical. This should be reported as *the
limitation being closed*, not as behavior that worked out of the box.

## Results (mean ± σ over 10 seeds)

| Quantity | Value |
|---|---|
| Multi-jurisdiction records / dataset | 1505 ± 29 |
| RETENTION_DELETION conflicts | 320 ± 33 |
| JURISDICTION conflicts | 2013 ± 43 |
| HOLD_DELETION conflicts (suppression active) | 2876 ± 541 |
| PRIORITY conflicts | 249 ± 79 |

**All four conflict families are non-empty on every seed.**

### JURISDICTION family — verified, not merely enabled

| Regulation pair | Conflicts |
|---|---|
| GDPR–CPRA  | 1010 ± 28 |
| GDPR–PIPEDA | 1003 ± 21 |

Both pairs fire on every seed. A unit test (`test_e3.py::
test_gdpr_cpra_and_pipeda_fire_on_dual_jurisdiction`) confirms that on a single
EU+PII record carrying `additional_jurisdictions=[US_CA, CA]`, GDPR, CPRA and
PIPEDA all become applicable and the two JURISDICTION conflicts are emitted.

### Axiom 4 — GDPR Art. 17(3) defeasibility on HOLD_DELETION

| Condition | HOLD_DELETION conflicts |
|---|---|
| Suppression OFF (no matter context) | 4291 ± 178 |
| Suppression ON (Art. 17(3) exemptions) | 2876 ± 541 |
| Suppressed by exemption | 1415 ± 552 |

Paired permutation test (10,000 sign-flips; exact for n=10), suppression OFF
minus ON: **Δ = 1415.0, p = 0.00195, Cohen's d = 2.56**. The p-value is the
exact-enumeration floor for 10 seeds (2/2¹⁰) because the suppression sign is
constant across every seed — i.e. the exemption *always* reduces the count, the
strongest result the test can express.

## Interpretation (2–3 sentences)

Under the balanced preset a single 10K dataset simultaneously populates all
four conflict families, including the previously data-starved JURISDICTION
family, which fires on genuine dual-privacy-regime (EU + California / Canada)
records. The GDPR Art. 17(3) defeasibility measurably and consistently
suppresses HOLD_DELETION conflicts (≈1415 per dataset, p = 0.00195), confirming
Axiom 4 is operative on realistic data rather than only in the unit fixture.

## Caveats

- The balanced preset is a *named experimental config*, not the default. Its
  jurisdiction mix, PII rate, and matter exemption-flag rates are raised so the
  families are densely populated; absolute counts are preset-specific and should
  not be compared against default-generator numbers.
- The multi-jurisdiction overlay forces selected records to EU + PII + a second
  privacy jurisdiction. This is a *modeling* of the dual-regime population, not
  an empirically sampled distribution; the paper should state the construction.
- The Axiom-4 paired test attains its exact-enumeration p floor because the
  effect sign never flips; with 10 seeds 0.00195 is the smallest reportable
  p-value, not a coincidence of magnitude.
- HOLD_DELETION variance is high (±541) because holds are distributed
  round-robin over the per-seed EU+PII population, whose size varies with the
  seed.

## Paper mapping

- **§VIII-E (Limitations → multi-jurisdiction):** present E3 as this limitation
  closed; cite the additive preset and the zero-impact-on-default test.
- **JURISDICTION family table:** GDPR–CPRA and GDPR–PIPEDA counts above.
- **Axiom 4 / GDPR Art. 17(3) defeasibility table:** the suppression OFF/ON/Δ
  numbers and the paired test. NOTE: the manuscript's table numbering has
  diverged from the code labels (cf. the set-ordering fix discussion); key these
  rows by *content* (multi-jurisdiction; Art. 17(3) suppression) when slotting
  them into the manuscript, not by a code table number.
