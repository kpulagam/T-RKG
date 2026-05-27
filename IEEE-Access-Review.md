# Venue selection and reviewer-style audit

## Part 1 — Venue selection

For an applied‑KBS / knowledge‑graph / decision‑support paper that is technically sound, fully reproducible, and not aimed at top‑tier theoretical novelty, the credible fast‑turnaround journals (mid‑2026) are:

| Journal | First decision | IF (2025) | APC | Notes |
|---|---|---|---|---|
| **IEEE Access** | **4–6 weeks** | 3.6 | $1,950 | Binary accept/reject; technical soundness as primary criterion; reproducibility heavily weighted; strong CS scope; SCI‑E indexed |
| PeerJ Computer Science | ~10 weeks | 2.5 | $1,395 | Open peer review; reasonable but lower IF |
| Heliyon (Cell Press) | ~16 weeks | 3.6 | $2,400 | Multidisciplinary; slower than the name suggests |
| Information Sciences (Elsevier) | 3–6 months | 8.1 | hybrid | Higher prestige but well outside the "fast" bracket |
| KBS (original target) | ~12 months | 7.2 | hybrid | Too slow for the user's timeline |

**Recommendation: IEEE Access.** It is the only credible, indexed, fast venue that matches this paper's *applied + reproducible + measurable* profile. The binary review model removes the "incremental contribution" rejection vector that hurts applied papers at higher‑tier journals; the trade is that reviewers will be brutal about technical correctness, statistical rigor, and reproducibility — which is what we should be optimizing for anyway.

A few practical implications of pivoting to IEEE Access:

1. **Format:** IEEE Access uses the standard IEEE double‑column LaTeX template (`bare_jrnl.tex` / `IEEEtran.cls`). Our current Word/PDF will need to be ported. This is mechanical.
2. **Reproducibility badge:** IEEE Access runs an opt‑in reproducibility pilot. The current code + ontology + tests qualify; we should opt in.
3. **Article type:** Submit as "Research Article" (not "Survey" or "Comments").
4. **Length:** No hard limit, but 10–14 double‑column pages is the sweet spot. Our current 25‑page single‑column will compress to ~15–18 double‑column.

---

## Part 2 — Reviewer report (IEEE Access perspective)

**Manuscript:** *T‑RKG: A Knowledge‑Based System for Cross‑System Regulatory Conflict Detection in Enterprise Records Governance*
**Reviewer:** Anonymous, IEEE Access
**Recommendation:** **Accept after Major Revision** (binary equivalent: Reject with strong encouragement to resubmit after addressing the items below)

### Summary
The paper proposes T‑RKG, an applied knowledge‑based system that uses an ontology of records, regulations, and jurisdictions to detect regulatory conflicts and propagate legal holds across siloed enterprise systems. Contributions are: a 47‑class OWL ontology, a typed temporal relationship model, a conflict detection algorithm, and an empirical evaluation across 5 seeds × 6 scales (1K–100K records). The supplementary repository, ontology file, and experiment runner are well‑organized and reproducible. The writing is clear and the limitations section is unusually direct.

### Strengths
1. **Reproducibility is excellent.** The single‑command experiment runner produces every number in the paper. The OWL/Turtle ontology is shipped. Tests pass. This satisfies IEEE Access's reproducibility criterion straightforwardly.
2. **Statistical rigor is appropriate.** 5 seeds × 6 scales with mean ± σ throughout.
3. **Ablation isolates each component cleanly.**
4. **The architectural argument is well‑constructed.** "Knowledge representation, not engineering" is a defensible thesis.
5. **Limitations are honestly disclosed.**

### Major concerns (block acceptance until addressed)

**M1. Table 9 (P/R/F1) is circular as currently presented.**
The paper acknowledges that T‑RKG achieves F1 = 1.000 "by construction" because T‑RKG's predicate *is* the ground‑truth predicate. This is a tautology, and presenting it as a result invites suspicion. Two acceptable fixes:
(a) Reframe Table 9 as a *baseline accuracy gap* table — drop T‑RKG row or relabel it "reference"; report only how much each baseline loses against the ontological reference.
(b) Add a second experiment where ground truth is *independently constructed* with stochastic noise (e.g., 5% of records receive an injected wrong jurisdiction label), so T‑RKG's F1 is genuinely < 1.0 and the metric quantifies *robustness*, not just baseline gap.
Best: do both.

**M2. Cross‑domain "0 ± 0" in both baselines is also tautological.**
The Siloed baseline cannot detect cross‑domain conflicts because no system has both privacy and financial regulations in its allowed set; the Untyped baseline cannot infer PII or jurisdiction. These are *definitional* limitations, not measured ones. Reviewers will recognize this. The fix: show that *if* the baselines were given the same regulation profiles as T‑RKG, they would still fail because they lack the ontological inference machinery. This converts the architectural argument into a controlled experiment.

**M3. Untyped baseline standard deviation = 0 across all 5 seeds.**
Tables 1, 6, and 9 all show "Untyped: 1500 ± 0" or similar. A reviewer's first thought is "did they actually run 5 seeds, or just one?" The answer is "yes, but the baseline's tagging logic is deterministic per record type, so it always finds exactly the same number of conflicts." This needs to be either (a) explicitly explained in the table caption, or (b) made non‑deterministic by adding seed‑dependent jitter. Otherwise it looks like a single‑seed result mislabelled.

**M4. Sub‑millisecond propagation is measured on tiny seed sets.**
Table 4 propagation timings use 50 seed records at depth 5. Real legal matters can have hundreds of custodians × thousands of records each. The paper implicitly extrapolates to "production scale" but doesn't measure it. Add at least one row showing propagation latency at, say, 500 and 5,000 seed records on the 100K corpus.

**M5. No production graph database baseline.**
The paper compares against flat Python list and SQLite recursive‑CTE (Table 8), and 121×–414× speedup over those is the headline performance result. But the natural production target is Neo4j / Neptune / TigerGraph, not SQLite. Without at least one production graph DB comparison, the speedup numbers are easily attributed to "you compared against the wrong thing." Either run Neo4j (best), or restate the claim as "vs. relational and naive‑list alternatives" and add an explicit caveat in the text.

**M6. Hardware specifications are missing.**
Throughput and latency numbers (Tables 1, 4, 8) are meaningless without the hardware they were measured on. Add a sentence in §7.1 specifying CPU, clock speed, RAM, OS, Python version. IEEE Access reviewers reliably flag missing compute environment specs.

**M7. Synthetic data only — no real‑world calibration check.**
This is the limitation the paper itself acknowledges most prominently, but no mitigation is offered. A defensible mitigation that doesn't require real enterprise data: parameter‑sweep evaluation showing T‑RKG behavior across plausible variation in PII rate (1%–30%), jurisdictional mix (US‑heavy vs EU‑heavy), and relationship density. If the system's behavior degrades smoothly, that defends the synthetic‑only approach.

### Minor concerns (fix during revision)

**m1. "Untyped Graph" baseline name is misleading.**
The actual omission is the regulatory ontology, not graph typing. Rename to "No‑Ontology Baseline" throughout.

**m2. Reference [39] (Zubulake) is malformed.**
"J. Pearson Lerum (US District Court...)" — Zubulake V was decided by Judge Shira Scheindlin, not "J. Pearson Lerum." Citation should read: *Zubulake v. UBS Warburg LLC*, 229 F.R.D. 422 (S.D.N.Y. 2004).

**m3. Memory measurement bias.**
Throughput numbers in Table 4 are measured under tracemalloc, which adds 20–30% overhead. Disclose this in the caption.

**m4. Scenario B has 65% relative variance.**
17 ± 11 PII records in Scenario B is too noisy to support per‑seed claims. Increase the dataset, or stratify the seed selection so each seed yields a comparable EU‑custodian count.

**m5. Competency Questions listed without answers.**
§4.6 lists 10 CQs but doesn't show what answers the system returns. Add an appendix showing one query result per CQ, or at minimum reference the test that exercises it.

**m6. Algorithm 1 line 12 ("H ← H ∪ next; …") is on a single line that wraps awkwardly in the rendered PDF.** Cosmetic but worth fixing during LaTeX porting.

**m7. The phrase "by construction" appears 5 times in §7.7 / §8.1.** Reviewers will notice the repetition and read it as defensiveness. Vary phrasing.

**m8. Throughput at 100K (52,553/s) differs from the v1 paper number (36,662/s) without explanation.** Either drop the v1 reference or footnote that hardware changed.

**m9. Add a "Reproduction" subsection at the end of §7** with explicit commands: `pip install -r requirements.txt && python -m experiments.run_all`, expected runtime, and where outputs land.

**m10. The OWL ontology is shipped but no validation step is shown.** Add `python -c "import owlready2; owlready2.get_ontology('ontology/trkg.ttl').load()"` to confirm it parses, ideally with HermiT/Pellet consistency check.

### Decision rationale
The paper is technically sound, well‑written, and reproducible. The blockers are concentrated in three places: (1) the F1 / cross‑domain metrics need to escape circularity (M1, M2, M3), (2) performance claims need stronger comparison and proper hardware disclosure (M4, M5, M6), and (3) synthetic‑data validity needs a mitigation (M7). All seven major items are addressable in a focused revision; none requires a fundamental redesign. An IEEE Access reviewer would expect resolution of these in the first round.
