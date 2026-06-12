# T-RKG Final Verification Manifest

_Single regeneration run under frozen encoding (commit 49b9af8). results.json timestamp: 2026-06-12T17:21:00.366135._
_Canonical seeds: [42, 123, 456, 789, 1024, 2026, 31415, 65537, 1729, 2718]. All mean ± σ over 10 seeds unless noted._

## 1. Conflict counts by scale (tab:conflicts)

| Scale | T-RKG total | T-RKG cross-domain | Siloed total | No-Ontology total |
|---|---|---|---|---|
| 1,000 | 84.3 ± 16.8 | 7.2 ± 10.5 | 75.0 ± 25.8 | 150.0 ± 0.0 |
| 5,000 | 373.4 ± 70.0 | 66.4 ± 29.0 | 292.9 ± 78.8 | 750.0 ± 0.0 |
| 10,000 | 739.9 ± 89.2 | 122.2 ± 33.1 | 572.7 ± 106.4 | 1500.0 ± 0.0 |
| 25,000 | 1782.8 ± 235.9 | 258.3 ± 61.1 | 1456.1 ± 256.3 | 3750.0 ± 0.0 |
| 50,000 | 3730.5 ± 347.4 | 513.2 ± 56.8 | 3061.5 ± 354.6 | 7500.0 ± 0.0 |
| 100,000 | 7609.9 ± 319.9 | 994.5 ± 50.7 | 6358.8 ± 322.4 | 15000.0 ± 0.0 |

## 2. Type/severity at 10K (tab:typesev)

Total conflicts (10K): **739.9 ± 89.2**  |  cross-domain (RD+Jur+Hold): **122.2 ± 33.1**

| Conflict type | Count (mean ± σ) | % of total | Family |
|---|---|---|---|
| Retention-Deletion | 122.2 ± 33.1 | 16.5% | cross-domain |
| Priority | 617.7 ± 93.0 | 83.5% | intra-domain |
| Jurisdiction | 0.0 ± 0.0 | 0.0% | cross-domain |
| Hold-Deletion | 0.0 ± 0.0 | 0.0% | cross-domain |

| Severity | Count (mean ± σ) | % of total |
|---|---|---|
| Critical | 49.2 ± 24.6 | 6.6% |
| High | 73.0 ± 22.8 | 9.9% |
| Medium | 45.0 ± 35.0 | 6.1% |
| Low | 572.7 ± 106.4 | 77.4% |

_Confirm: Jurisdiction=0, Hold-Deletion=0 (both expected 0 in default config)._

## 3. SHACL Core (tab:shacl)

| Scale | SHACL violations | T-RKG total | Recall % | SHACL latency (ms)* | T-RKG latency (ms)* |
|---|---|---|---|---|---|
| 1,000 | 1.5 ± 3.1 | 84.3 ± 16.8 | 1.8% | 197.7 ± 3.7 | 4.2 ± 0.1 |
| 5,000 | 16.6 ± 19.0 | 373.4 ± 70.0 | 4.4% | 1006.3 ± 19.6 | 21.2 ± 0.3 |
| 10,000 | 35.7 ± 27.4 | 739.9 ± 89.2 | 4.8% | 2070.4 ± 105.3 | 42.8 ± 0.5 |
| 25,000 | 79.8 ± 40.2 | 1782.8 ± 235.9 | 4.5% | 5142.9 ± 122.3 | 107.4 ± 1.4 |
| 50,000 | 165.3 ± 52.6 | 3730.5 ± 347.4 | 4.4% | 10121.1 ± 109.8 | 220.1 ± 13.6 |
| 100,000 | 279.9 ± 37.6 | 7609.9 ± 319.9 | 3.7% | 20300.0 ± 375.4 | 432.9 ± 4.8 |

*Latency columns are fresh measurement — NOT for manuscript (manuscript keeps published latencies).*

Recall @ 100K: **3.7%**  |  pooled (all scales): **4.0%**

SHACL Core expresses 2 rule families; skipped: ['Temporal interval intersection (Allen-style)', 'Defeasible priority resolution', 'Cross-record propagation closure', 'GDPR Article 17(3) exemption suppression (T9)']

## 4. SHACL-SPARQL (tab:shaclsparql)

| Scale | T-RKG latency (ms) | SHACL-SPARQL latency (ms) | Ratio (×) |
|---|---|---|---|
| 1,000 | 6.65 ± 0.26 | 21983.1 ± 326.0 | 3308 ± 128 |
| 5,000 | 34.81 ± 5.24 | 112089.7 ± 1452.9 | 3269 ± 367 |
| 10,000 | 77.84 ± 24.98 | 224361.6 ± 3025.2 | 3060 ± 623 |

Per-family recall (SHACL-SPARQL vs T-RKG):

| Family | Recall |
|---|---|
| Jurisdiction | 1.000 ± 0.000 |
| Retention-Deletion | 0.526 ± 0.075 |
| Hold-Deletion | 0.456 ± 0.250 |
| Priority | 0.000 (inexpressible in SPARQL) |

## 5. Applicability P/R/F1 (tab:f1noise)

**Clean**

| Detector | Precision | Recall | F1 |
|---|---|---|---|
| T-RKG | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 |
| Siloed | 1.000 ± 0.000 | 0.491 ± 0.045 | 0.657 ± 0.040 |
| No-Ontology | 0.083 ± 0.007 | 0.491 ± 0.045 | 0.141 ± 0.012 |

**Noised**

| Detector | Precision | Recall | F1 |
|---|---|---|---|
| T-RKG | 0.790 ± 0.018 | 0.864 ± 0.006 | 0.826 ± 0.012 |
| Siloed | 0.991 ± 0.006 | 0.435 ± 0.038 | 0.604 ± 0.037 |
| No-Ontology | 0.083 ± 0.007 | 0.491 ± 0.045 | 0.141 ± 0.012 |

## 6. Relationship-type ablation (tab:ablation)

| Arm | Conflict count (mean ± σ) |
|---|---|
| Full T-RKG | 739.9 ± 89.2 |
| No-Ontology | 1500.0 ± 0.0 |
| No-Typed-Rels | 739.9 ± 89.2 |
| No-Propagation | 739.9 ± 89.2 |
| Siloed | 572.7 ± 106.4 |

_Hold-set column is propagation-only (unaffected by encoding); not reproduced here._

## 7. E1 LLM baseline

api_calls = **0** (off cache), cache_hits = 8000, status = COMPLETE

| Regime | Composed micro-F1 | Composed macro-F1 | Siloed x-dom recall | Gap Δ | p | d |
|---|---|---|---|---|---|---|
| clean | 0.970 | 0.794 | 0.000 | 0.721 | 0.001953 | 26.36 |
| noised | 0.872 | 0.742 | 0.000 | 0.641 | 0.001953 | 19.37 |

Per-regulation composed F1 (clean):

| Reg | GDPR | SOX | HIPAA | SEC | FINRA | CPRA | PIPEDA | IRS | HGB |
|---|---|---|---|---|---|---|---|---|---|
| clean F1 | 1.000 | 0.840 | 0.886 | 0.731 | 0.000 | 0.995 | 1.000 | 0.696 | 1.000 |
| noised F1 | 0.864 | 0.808 | 0.840 | 0.741 | 0.000 | 0.910 | 0.907 | 0.708 | 0.900 |

## 8. E5 composition ablation

| Quantity | Composed | Decomposed |
|---|---|---|
| Total conflicts | 739.9 ± 89.2 | 617.7 ± 93.0 |
| Cross-domain | 122.2 ± 33.1 | 0.0 ± 0.0 |
| Applicability F1 | 1.000 ± 0.000 | 0.733 ± 0.038 |

Paired tests (composed − decomposed):

| Metric | Δ | p | d |
|---|---|---|---|
| Total | 122.200 | 0.001953 | 3.688 |
| Cross-domain | 122.200 | 0.001953 | 3.688 |
| Applicability F1 | 0.267 | 0.001953 | 7.056 |

## 9. E6 SHACL-SPARQL (latency ratio + family recall)

Latency ratio SPARQL/T-RKG: 1K=3308×, 5K=3269×, 10K=3060× (~3,000× confirmed).

Projected SHACL-SPARQL runtime: 25K≈9.5 min, 50K≈19.0 min, 100K≈38.3 min.

Per-family recall (10K): RETENTION_DELETION=0.526, HOLD_DELETION=0.456, JURISDICTION=1.000, PRIORITY=0.000 (inexpressible).

## 10. Noise sweep (e12) — F1

| Rate | T-RKG F1 | Siloed F1 | No-Ontology F1 |
|---|---|---|---|
| 0.02 | 0.965 ± 0.005 | 0.647 ± 0.039 | 0.141 ± 0.012 |
| 0.05 | 0.912 ± 0.008 | 0.630 ± 0.039 | 0.141 ± 0.012 |
| 0.10 | 0.826 ± 0.012 | 0.604 ± 0.037 | 0.141 ± 0.012 |
| 0.15 | 0.744 ± 0.015 | 0.576 ± 0.038 | 0.141 ± 0.012 |
| 0.20 | 0.672 ± 0.018 | 0.554 ± 0.040 | 0.141 ± 0.012 |

## 11. Block noise (e13) — P/R/F1

| Detector | Precision | Recall | F1 |
|---|---|---|---|
| T-RKG | 0.952 ± 0.028 | 0.955 ± 0.022 | 0.954 ± 0.018 |
| Siloed | 0.991 ± 0.019 | 0.483 ± 0.047 | 0.648 ± 0.041 |

## 12. Per-regulation firing counts (e6, seed 42, 10K)

| Regulation | Applicability count |
|---|---|
| GDPR | 334 |
| CPRA | 254 |
| PIPEDA | 80 |
| HIPAA | 150 |
| SOX | 500 |
| SEC | 263 |
| FINRA | 0 (absent) |
| IRS | 174 |
| HGB | 109 |

_FINRA confirmed: **absent → 0** — no EMAIL/CHAT record carries is_public_company=True in this dataset, so FINRA (narrowed to broker-dealer comms) never fires here._

## 13. Statistics — Cohen's d (noised F1)

| Comparison | Δ F1 | Cohen's d | p |
|---|---|---|---|
| T-RKG vs Siloed | 0.222 | 7.120 | 0.001953 |
| T-RKG vs No-Ontology | 0.684 | 73.998 | 0.001953 |

## 14. Worked trace — fin_00112 (seed 42, 10K)

- Type: INVOICE, title "Invoice - Q3 2021"
- Jurisdiction: EU_DE; contains_pii=True; is_public_company=True; fiscal_year=2021
- Applicable regulations: **{GDPR, HGB, SOX}**
- Conflicts (**3**):
  - GDPR–HGB · RETENTION_DELETION · HIGH
  - GDPR–SOX · RETENTION_DELETION · CRITICAL
  - SOX–HGB · PRIORITY · MEDIUM

_Confirmed unchanged: {GDPR, SOX, HGB}, 3 conflicts._

## 15. Hold propagation (tab:perf / propagation)

Hold-propagation and timing/throughput figures are propagation- and machine-timing-only; the encoding fix touches applicability inference, not relationship traversal or hold sets. These are **unchanged from published values** — manuscript keeps published timings (per pre-settled decision).

## Internal consistency self-check

| Check | Values | Pass |
|---|---|---|
| (a) type counts sum to 10K total | 739.9 vs 739.9 | ✅ |
| (b) RD+Jur+Hold = cross-domain count | 122.2 vs 122.2 | ✅ |
| (c) severity sum to total | 739.9 vs 739.9 | ✅ |
| (c) RD = Critical+High | 122.2 vs 122.2 | ✅ |
| (c) Priority = Medium+Low | 617.7 vs 617.7 | ✅ |
| (d) ablation Full = tab:conflicts 10K | 739.9 vs 739.9 | ✅ |
| (e) E5 composed_total = ablation Full | 739.9 vs 739.9 | ✅ |
