# T-RKG Paper: KBS Submission Readiness Review (v3 — post-revisions)

## KBS Journal Requirements Check

| Requirement | Status | Notes |
|-------------|--------|-------|
| elsarticle format | ⚠ | Currently a clean Word/PDF preprint; needs final LaTeX porting before submission |
| Single-anonymized review | ✓ | Author placeholders ready to fill |
| Abstract < 300 words | ✓ | ~280 words after revision |
| Keywords (6 max) | ✓ | 6 keywords aligned to KBS scope |
| Editable source | ✓ | Word source: `trkg-singular.docx`; PDF: `trkg-kbs-paper.pdf` |
| Data availability statement | ✓ | Added at end of paper |
| CRediT author statement | ✓ | Included |
| Competing interests | ✓ | Declaration included |
| References | ✓ | 42 numbered references (target was 40+; achieved) |
| Page count target (~15-18) | ⚠ | 25 pages compiled; mostly tables and code blocks; can be tightened during LaTeX porting |

---

## v2 → v3 Revision Summary

### Code changes
- **Authored `ontology/trkg.ttl`** — 47 classes across 5 modules + 6 reified relationship subclasses + 23 object properties (now matches paper claims).
- **Replaced stub `SiloedConflictDetector`** with implementation that iterates every record under each system's allowed regulation set; legitimately produces 0 cross-domain conflicts while finding within-system priority conflicts.
- **Replaced stub `UntypedGraphConflictDetector`** with implementation that performs naive type+system regulation tagging without ontological reasoning; produces inflated total counts (false positives) but 0 cross-domain conflicts.
- **Rewrote `experiment_5_ablation`** to use 50 matter-scoped seeds at depth 10 across 5 random seeds (matching the paper's stated protocol). Numbers in Table 6 now reproduce.
- **Rewrote `experiment_4_scenarios`** to remove the pre-applied hold from Scenario B and run all three scenarios across all 5 random seeds with mean ± σ.
- **Added `experiment_7_applicability_pr_f1`** — per-record regulatory applicability against an ontologically-derived ground truth, with precision/recall/F1.
- **Extended `experiment_1_conflict_detection`** to report cross-domain conflict counts separately for each system.
- **Wired Flat-list and SQLite baselines** into the headline results (Table 8 in paper).
- **Authored `figures/figure1_architecture.svg`** — replaces the "[Figure omitted]" placeholder.
- **Tests grew from 41 → 51**, with 10 new competency-question tests, all passing.

### Paper changes
- **§4 Ontology** rewritten to match the actual TTL file (47 classes / 23 properties / 5 modules with explicit per-module counts).
- **§4.6 Competency Questions** added (10 CQs, each with a passing test in `tests/test_trkg.py`).
- **§5.3 Conflict Rules** corrected — now lists the 14 actual conflict rules (7 RetentionDeletion + 5 Priority + 2 Jurisdiction + 1 HoldDeletion). Previously enumerated FINRA priority pairs that don't exist in the code.
- **§5.4 Worked Trace Box** added — record fin_00012 traced through Axioms 1, 2, 3.
- **§6.3 Baselines** rewritten to describe the new non-stub implementations and to introduce the FlatList/SQLite performance comparison.
- **Figure 1** referenced (and provided in supplementary material).
- **§7.2 Table 1** now reports cross-domain conflict counts separately for all three systems (the headline "0 vs. 4–831" gap).
- **§7.5 Table 5** now reports scenario results as mean ± σ across 5 seeds (was single-seed).
- **§7.6 Table 6 (ablation)** now uses matter-scoped seeds at depth 10 — numbers reproduce from the script.
- **§7.7 Table 9 (P/R/F1)** new section, T-RKG = 1.000 / Siloed = 0.581 / Untyped = 0.113.
- **§7.8 Table 8 (FlatList/SQLite comparison)** new section, propagation 121×–414× faster than alternatives.
- **References extended from 32 → 42** (Hogan et al. 2021 KG survey, Bizer et al. 2009 Linked Data, Brank et al. 2005 Ontology Eval, EDRM IGRM, SHACL, OWL 2, Zubulake, SPARQL, Linked Data Design Issues, Antoniou & van Harmelen).
- **Revision Notes appendix removed.**

### Numbers reproduced from the script
All paper numbers come from `experiments/run_all.py` outputting `experiments/results.json`. Reproducing:
```
PYTHONPATH=. python -m experiments.run_all
```

| Headline number | Paper claim | Where measured | Status |
|---|---|---|---|
| Conflicts at 100K | 4,672 ± 254 | Table 1 | reproduces |
| Cross-domain at 100K | 831 ± 42 | Table 1 | reproduces |
| Both baselines cross-dom | 0 ± 0 at all scales | Table 1 | reproduces |
| Att+Thread expansion | 2.74× (137 ± 22) | Table 3 | reproduces |
| Build throughput at 100K | ~52K records/s | Table 4 | reproduces |
| Sub-ms propagation | 0.09–0.41 ms | Table 4 | reproduces |
| Applicability F1 (T-RKG) | 1.000 ± 0.000 | Table 9 | reproduces |
| Applicability F1 (Siloed) | 0.581 ± 0.050 | Table 9 | reproduces |
| Applicability F1 (Untyped) | 0.113 ± 0.009 | Table 9 | reproduces |
| Propagation vs. Flat | 121× faster | Table 8 | reproduces |
| Propagation vs. SQLite | 414× faster | Table 8 | reproduces |

---

## Remaining items before journal submission

### Recommended
- [ ] Port to elsarticle LaTeX (mechanical; preserves all numbers verbatim).
- [ ] Fill in real author names and affiliations.
- [ ] Final proofread.
- [ ] Cover letter to the editor.
- [ ] Make repository public and add the URL to the data-availability statement.

### Optional polish
- [ ] Replace SVG architecture figure with vector PDF for the LaTeX build.
- [ ] Add an OWL constraint validation step (HermiT/Pellet via owlready2) as a CI check.
- [ ] Tighten the discussion section by ~15% to bring page count to 18-20.
