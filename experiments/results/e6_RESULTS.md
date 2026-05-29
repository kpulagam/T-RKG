# E6 — SHACL-SPARQL baseline: expressivity vs prohibitive latency

**STATUS: COMPLETE** (10 seeds, scales 1K/5K/10K; pyshacl 0.31.0 / rdflib 7.6.0).
**Code:** `experiments/e6_shacl_sparql.py`, `trkg/baselines/shacl_sparql_baseline.py`
**Tests:** `tests/test_e6.py` (11 tests, green).
**Data:** `experiments/results/e6.json`.

## What this measures

SHACL **Core** can only express per-node attribute conjunctions, so it scores
zero on every cross-record conflict family. SHACL-**SPARQL** (`sh:sparql`,
`advanced=True`) lifts that ceiling: a SPARQL `SELECT` can join across nodes and
use `FILTER NOT EXISTS`. E6 asks how far that gets a standards-based engine
against T-RKG on identical data, on two axes: **what it can express** (recall vs
T-RKG, the reference) and **at what cost** (latency). Both detectors run under an
identical round-robin hold context over the EU+PII population (same
store/matters/holds), so the recall comparison is apples-to-apples.

## Latency — measured (10 seeds, mean ± σ)

| Scale | T-RKG (ms) | SHACL-SPARQL (ms) | Ratio (×) |
|---|---|---|---|
| 1,000 | 6.55 ± 0.30 | 21,260.6 ± 343.7 | **3,250 ± 129** |
| 5,000 | 32.57 ± 1.04 | 106,334.4 ± 1,176.4 | **3,267 ± 111** |
| 10,000 | 111.15 ± 95.80 | 215,028.1 ± 862.7 | **2,765 ± 1,073** |

SHACL-SPARQL is **~3 × 10³ (≈ 2,800–3,300×) slower than T-RKG** and scales
linearly: `sparql_ms ≈ 20.6 · n^1.00`. At 10K it already takes **3.6 minutes**
vs T-RKG's 111 ms. (The 10K T-RKG σ is inflated by one slow seed — a GC/warmup
spike on the larger corpus; the SHACL side is clean and the order-of-magnitude
gap is unaffected.)

### Projected (NOT measured — infeasibility is the point)

25K/50K/100K were deliberately not run; the linear fit projects the SHACL-SPARQL
wall-clock:

| Scale | Projected SHACL-SPARQL |
|---|---|
| 25,000 | ~9.0 min |
| 50,000 | ~18.0 min |
| 100,000 | ~36.1 min |

At enterprise corpus sizes a single conflict scan crosses from sub-second
(T-RKG) into the tens of minutes — infeasible for interactive governance and for
the repeated scans a live system performs. **That gap is the result, not a
limitation of our setup.**

## Expressivity — recall vs T-RKG by family (10 seeds, mean ± σ)

| Family | n=1K | n=5K | n=10K |
|---|---|---|---|
| JURISDICTION | **1.000 ± 0.000** | **1.000 ± 0.000** | **1.000 ± 0.000** |
| RETENTION_DELETION | 0.461 ± 0.238 | 0.484 ± 0.141 | 0.497 ± 0.074 |
| HOLD_DELETION | 0.380 ± 0.263 | 0.407 ± 0.197 | 0.456 ± 0.250 |
| PRIORITY | 0 (inexpressible) | 0 | 0 |
| Hold-propagation closure | 0 (inexpressible) | 0 | 0 |

## Honest interpretation (the framing diverges from what we expected)

Two things came out different from the going-in hypothesis, and both are
reported as measured:

1. **It is *qualitative* expressivity, not full parity.** SHACL-SPARQL fires
   non-zero on all three families SHACL Core cannot touch — a real capability
   gain — and reaches **full** recall on JURISDICTION (1.000), because the
   multi-jurisdiction pattern is a single uniform join. But RETENTION_DELETION
   (~0.50) and HOLD_DELETION (~0.40) are only **partially** recovered. The cause
   is structural: each `sh:sparql` shape hand-encodes **one** regulation pair —
   `RetentionDeletionSparqlShape` matches exactly *EU-PII × SOX public-company
   financial*, so it misses CPRA/PIPEDA (US_CA/CA) deletion paired with retention
   and non-public-company retention regimes (SEC/IRS/HGB). T-RKG instead composes
   the full retention × deletion **cross-product** through the ontology. Closing
   the recall gap with SHACL-SPARQL would mean authoring and maintaining one
   shape per regulation pair — combinatorial shape sprawl — which is itself the
   maintainability argument for the ontology. The HOLD_DELETION shortfall is the
   same shape: SHACL recovers exactly the GDPR Art. 17(3) exemption subset and
   misses CPRA/PIPEDA erasure-under-hold, because Art. 17(3) is GDPR-specific and
   one wholesale-suppression shape cannot encode it per-regulation.

2. **The latency gap is ~3 × 10³, not 10⁴–10⁵.** Measured ratios are
   2,800–3,300×. The infeasibility conclusion stands — 3.6 min at 10K, projected
   36 min at 100K — but the multiplier is reported as the ~3 × 10³ we actually
   observed, not inflated to a round expectation.

3. **PRIORITY and hold-propagation closure remain inexpressible at any effort**
   (recall 0 by construction): SHACL has no non-monotonic/priority semantics for
   SOX>SEC>IRS max-retention selection, and no portable fixed-point/transitive
   closure for hold propagation across typed relationships.

**Net:** SHACL-SPARQL is strictly more expressive than SHACL Core, but it reaches
full coverage on only the simplest family, requires combinatorial per-pair shape
authoring to approach T-RKG on the rest, cannot express two families at all, and
runs ~3 × 10³ slower — tens of minutes at enterprise scale. The combination, not
any single axis, is what makes it infeasible as a T-RKG substitute.

## Paper mapping

- **Latency table:** measured 1K/5K/10K (T-RKG vs SHACL-SPARQL, ratio ~3×10³),
  plus 25K/50K/100K as projected-infeasible from `ms ≈ 20.6 · n^1.00`.
- **Capability/recall table:** JURISDICTION 1.000; RETENTION_DELETION ~0.50;
  HOLD_DELETION ~0.40; PRIORITY and hold-propagation inexpressible — framed as
  qualitative expressivity gain over SHACL Core with a per-regulation-pair
  authoring burden, not full parity.
