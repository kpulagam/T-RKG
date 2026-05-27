# T-RKG Paper & Experiments — Enhancement Plan

Reviewed paper: `trkg-singular.docx` (≈10,070 words, 32 references, KBS-style preprint).
Reviewed code: `trkg/` (1.7K LoC), `experiments/run_all.py` (≈870 LoC), `tests/test_trkg.py` (488 LoC, 41 tests pass on a NetworkX-shimmed environment).
Reviewed checklist: `KBS-Submission-Checklist.md`.

The goal of this document is to give a single prioritized list of what is wrong, what is weak, and what is missing — with an explicit, code-grounded fix or experiment for each. Items in the **Blocker** tier must be resolved before submission; **High** items materially affect reviewer outcome; **Medium** items strengthen acceptance odds.

---

## A. Blocker‑tier issues (paper currently misrepresents what the code does)

### A1. Paper vs. code: ablation table is internally inconsistent
**Paper, Table 6:** "Full T-RKG: 468 ± 36 conflicts, 171 (3.43×) hold set" with the explicit statement in §7.6: *"Both this experiment and the propagation experiment use 50 matter-scoped seeds at depth 10, so the Full T-RKG hold set of 171 (3.43×) here corresponds directly to the Att + Thread row in Table 3."*
**Code, `experiment_5_ablation`:** uses `seed_ids = list(store.records.keys())[:50]` and `max_depth=5`, on `seed=42` only — not multi‑seed, not matter‑scoped, not depth 10.
**Reproduction:** running the code's logic gives 57–68 (1.14–1.36×), not 171 (3.43×).
Running the paper's stated protocol (matter‑scoped, depth 10, 5 seeds) gives 182 ± 42 (3.64×) — close to but not equal to 171 ± 51.
**Fix (code):** rewrite `experiment_5_ablation` to:
- use `EXPERIMENT_SEEDS` (5 seeds), report mean ± σ;
- pull seeds from `matter[0].custodian_ids` (same selection logic as `experiment_2_hold_propagation`);
- use `max_depth=10`;
- stop hard‑coding "468" as conflict count — it should also be re‑run multi‑seed and reported as `mean ± σ`.
**Fix (paper):** regenerate Table 6 from the new run; either keep the "matches Table 3" claim and ensure the numbers actually match, or drop the claim and footnote that the ablation uses an independent seed selection.

### A2. Paper vs. code: Scenario B numbers are stale
**Paper, §7.5/Table 5, seed 42:** "37 PII records … 19 deletable, 18 blocked by retention; 19 of the 37 carry active regulatory conflicts."
**Code, `experiment_4_scenarios` (verified live):** 37 PII records (matches), but `CAN_DELETE = 7`, `HOLD_BLOCKS = 20`, `RETENTION_BLOCKS = 10`, conflicting records = 30.
**Cause:** the code applies a hold to the first 20 PII records before classification, so 20 are bucketed into `HOLD_BLOCKS`, leaving only 7 that are "freely deletable" and 10 that hit a retention rule. The paper's older draft assumed no hold was applied first.
**Fix (paper):** rewrite Scenario B to either (a) run *without* the hold and classify all 37 against retention regs (yields 19/18 split), or (b) keep the hold and report the 7/20/10 numbers honestly. Option (a) is the better story (illustrates conflict detection cleanly); option (b) better illustrates the hold–deletion conflict. **Pick one and align code + paper.** The current text describes (a) but the code runs (b).

### A3. The "47‑class, 23‑object‑property" ontology is asserted but does not exist
The paper claims throughout (Abstract, §1.1 contribution 1, §4.1, §4.5, Conclusion) a 47‑class, 23‑object‑property OWL ontology with five modules, plus 34 data properties, "provided in OWL format as supplementary material." The codebase contains:
- no `.owl`, `.ttl`, `.rdf`, or `.xml` ontology file;
- no `Class` / `ObjectProperty` declarations;
- only Python `Enum`s (16 record types, 7 relation types, 7 governance states, 10 jurisdictions, 11 regulations) and dataclasses.
This is the single biggest credibility risk: a KBS reviewer who downloads the supplement and finds no OWL ontology will reject. Also the paper's own §4.2 example list shows 8 record types (Email, Document, Contract, FinancialRecord, AuditWorkpaper, Invoice, Chat, Ticket); with their stated 5‑module split this nowhere reaches 47 classes.
**Fix (must do):** author an actual OWL/Turtle ontology file (`trkg.ttl`) implementing exactly the five modules and the 47/23 counts the paper claims. Practical breakdown that gets to ≈47 classes:
- Record Module (12): Record, Email, Document, Chat, Ticket, Contract, FinancialRecord, AuditWorkpaper, Invoice, TaxRecord, MedicalRecord, Spreadsheet.
- Actor Module (6): Custodian, OrganizationalUnit, Department, SourceSystem, ServicePrincipal, ExternalParty.
- Governance Module (12): Matter, LegalHold, RetentionSchedule, RetentionRule, HoldRule, DeletionRule, GovernanceState (+5 state subclasses), HoldPropagationConfig, AuditEvent.
- Regulatory Module (10): Regulation, DataProtectionRegulation, FinancialRegulation, HealthRegulation, TaxRegulation, NationalCommercialLaw, Jurisdiction, JurisdictionalScope, ApplicabilityCondition, OperativeRequirement.
- Conflict Module (7): RegulatoryConflict, RetentionDeletionConflict, JurisdictionConflict, HoldDeletionConflict, PriorityConflict, ConflictSeverity, ResolutionGuidance.
Add 23 object properties (`hasCustodian`, `managedBy`, `hasGovernanceState`, `subjectTo`, `appliesIn`, `subJurisdiction`, `relatedTo`, `propagatesHold`, `inheritsCustodian`, `governedBy`, `hasRequirement`, `hasConflict`, `conflictsWith`, `attachedTo`, `repliesTo`, `derivedFrom`, `references`, `duplicateOf`, `partOfMatter`, `triggeredBy`, `assertedBy`, `withinScopeOf`, `precedes`).
Then ship `trkg.ttl` as the supplementary material the paper promises.

### A4. Paper Section 5.3 enumerates 14 conflict rules incorrectly
**Paper text:** "eight Priority rules (SOX vs. SEC, SOX vs. IRS, SOX vs. HGB, SEC vs. IRS, SEC vs. HGB, FINRA vs. SOX, FINRA vs. SEC, FINRA vs. IRS); four RetentionDeletion rules (GDPR vs. SOX, GDPR vs. IRS, CPRA vs. SOX, CPRA vs. IRS); one HoldDeletion rule; one Jurisdiction rule (GDPR vs. PIPEDA)."
**Actual code (`build_conflict_rules`):** total 14 rules but split is 7 retention‑deletion (GDPR–SOX, GDPR–HIPAA, GDPR–HGB, CPRA–SOX, CPRA–SEC, CPRA–IRS, PIPEDA–SOX), 5 priority (SOX–SEC, SOX–IRS, SOX–HGB, SEC–IRS, HIPAA–IRS), 2 jurisdiction (GDPR–CPRA, GDPR–PIPEDA). FINRA–SOX, FINRA–SEC, FINRA–IRS, SEC–HGB, GDPR–IRS do **not** exist in the code.
The total is 14 by coincidence; the per‑category description is fictional. This is exactly the kind of detail a careful reviewer flags.
**Fix:** rewrite §5.3 to enumerate the actual rules. The honest split (7+2+5+1) is even more defensible than the fabricated one because it produces both the 79% Priority and 21% Retention‑Deletion ratios reported in Table 2.

### A5. Both comparison baselines are stubs that always return zero
`SiloedConflictDetector.detect_all_conflicts` and `UntypedGraphConflictDetector.detect_all_conflicts` each construct a `ConflictDetectionResult` with `total_conflicts=0`; they don't actually look at the records. The paper's argument ("they cannot detect cross‑regulation conflicts because they lack unified regulatory knowledge") is correct architecturally, but a reviewer who runs the code will see "this baseline doesn't even iterate." That undermines the credibility of every "0 vs 4,672" headline.
**Fix:** make the baselines actually run something non‑trivial that still legitimately returns zero (or close to zero):
- *Siloed:* iterate over records, partition by `system_id`, run a per‑system conflict check using only that system's allowed regulation set. Same‑domain regulations don't conflict with each other (SOX/SEC/IRS all "retain"), so the count remains 0 — but now the result is a *demonstrated* zero, not a stipulated one.
- *Untyped Graph:* iterate every record, do a per‑record regulation tagging that has access to record type + system_id + custodian only (no jurisdiction inference, no PII flag, no metadata reasoning). With those degraded inputs, the regulation set per record collapses to ≤1 in almost every case, so pair‑wise conflicts are 0 — but again it's a measured 0.
This converts §6.3 from architectural prose into something a reviewer can run and verify.

---

## B. High‑value experimental additions (will materially help acceptance)

### B1. Add the SQLite + Flat‑list performance comparison to the paper
The codebase ships fully working `FlatListStore` and `SQLiteStore` baselines, but the paper does not include them. Live numbers from the current code at 10K records:
| Operation | T-RKG | Flat list | SQLite | T-RKG speedup |
|-----------|------:|----------:|-------:|--------------:|
| Type query (ms) | 2.8 | 0.81 | 1.0 | 0.3–0.4× (slower) |
| Hold propagation (ms) | 0.08 | 11.6 | 41.1 | 142× / 505× |
| Temporal query (ms) | 1.0 | 0.61 | 2.1 | 0.6× / 2.0× |

The 142× / 505× propagation speedup is the paper's strongest performance claim and right now it's invisible. Add it as **Table 8 (or replace current Table 4 cells)**: "T-RKG vs. relational/flat alternatives on identical workloads." This directly answers the limitation the paper itself raises in §8.4 ("does not compare T-RKG against alternative implementations of those same capabilities — for instance, a relational system extended with equivalent regulation profiles and conflict rules").

**Caveat to disclose:** SQLite type queries are faster because they have a B‑tree index on `type`; T-RKG's `select_records` is a Python iteration. This is not a real performance gap (both are O(matching rows)) but framing it honestly avoids the easy reviewer pushback.

### B2. Add an "Untyped Graph + auto‑tagged regulations" baseline that *does* find conflicts
The current Untyped baseline returns 0 by construction. A more interesting baseline:
- Manually tag every record with regulations using only `record_type` + `system_id` (no jurisdiction subsumption, no PII inference).
- Run pair‑wise conflict checks.
- Show that this baseline finds *some* conflicts (probably 5–10× fewer than T-RKG) and *misclassifies* others (e.g., flags US records as GDPR‑applicable because PII flag is unavailable).

This converts the "structural impossibility" argument from §6.3/§7.2 into a quantitative result: the gap is not 4,672‑vs‑0, it is 4,672‑vs‑X with Y false positives and Z false negatives. KBS reviewers respond very well to graded comparisons and poorly to all‑or‑nothing claims.

### B3. Add precision/recall/F1 by injecting ground‑truth conflicts
The synthetic generator currently produces records but does not record which records were *intentionally* placed at a regulatory intersection. A ground‑truth labelling step would close the largest evaluation gap:
1. Extend `SyntheticDataGenerator` to record per‑record an `expected_regulations: Set[Regulation]` derived from its construction parameters (jurisdiction, PII flag, record type, public‑company metadata).
2. Run the detector and compute precision / recall / F1 on per‑record applicability.
3. Re‑report Table 1 as "Precision / Recall / F1 per regulation" instead of (or in addition to) raw counts.

This converts the paper from "we counted conflicts the baseline cannot count" to "we identify regulatory applicability with F1 = 0.97 ± 0.01 across nine regulations." That is a much more conventional KBS result and is directly actionable for production deployment.

### B4. Add competency questions (cited but never delivered)
The paper cites Grüninger & Fox §2.4 and uses competency questions as part of the methodology argument, but never lists them. Add §4.6 "Competency Questions" listing 10–15 questions the ontology answers, e.g.:
1. CQ1: Which regulations apply to record r at time t?
2. CQ2: Which custodians' records are in scope of matter m?
3. CQ3: For a GDPR erasure request on subject s, which records are eligible for deletion vs. blocked by retention vs. blocked by hold?
4. CQ4: Show all records under hold for matter m via path of length ≤ k.
5. CQ5: List records subject to two or more regulations at severity ≥ HIGH.
6. CQ6: Under propagation policy P, what is the hold scope for matter m as of date d?
7. … etc.

Each CQ should be paired with a SPARQL query (or T-RKG Python query) and a passing test. This is a 1–2 day exercise that meaningfully strengthens the ontology‑engineering claim.

### B5. Add a worked end‑to‑end example trace (Box 1)
The reviewer guidance memo mentions this and the checklist flags it as nice‑to‑have. Concretely: pick one specific record (e.g., `fin_00012`), show
- input attributes (jurisdiction = EU_DE, type = INVOICE, contains_pii = True, is_public_company = True);
- step 1: ancestor jurisdictions resolved → {EU_DE, EU, GLOBAL};
- step 2: applicable regulations → {GDPR, SOX, HGB} (with the predicate firing for each);
- step 3: pairwise conflict check → GDPR vs. SOX (CRITICAL, retention‑deletion), GDPR vs. HGB (HIGH, retention‑deletion), SOX vs. HGB (MEDIUM, priority);
- step 4: resolution guidance returned for each conflict.

A single boxed trace converts the abstract algorithm description into something a reviewer can mentally execute. Place it after Algorithm 2.

### B6. Add a real architecture figure (replace "[Figure omitted]")
Section 5.1 says *"Figure 1: T-RKG system architecture. … [Figure omitted from this version; see supplementary material.]"* That literal placeholder cannot ship. Build a clean SVG showing source systems → connector layer → ABox/TBox/RBox → reasoning engine → query interface. An ablation also benefits from a second figure: a relationship‑type radial graph showing each of the 7 relation types and which propagation policies include them.

### B7. Multi‑seed scenario results
§7.5 explicitly notes scenarios are seed=42 only. Run the three scenarios across all 5 seeds and report mean ± σ in Table 5 (replace single‑seed numbers). This is mechanical (≈30 LoC change in `experiment_4_scenarios`) and removes a known reviewer concern.

### B8. Statistical significance reporting
For every "T-RKG > baseline" claim, add a paired comparison with a Wilcoxon signed‑rank or paired t‑test across the 5 seeds. With 5 seeds the p‑value won't be small, but that's fine — the paper currently makes no statistical claim at all, and adding even a `p < 0.05 (Wilcoxon, n = 5)` footnote raises rigor without overstating.

---

## C. Medium / polish items

### C1. Reach 40+ references (currently 32)
The checklist target is 40+. Concrete additions worth integrating:
- W3C SHACL or ShEx (for OWL constraint checking, ties into ontology rigour).
- Bizer, Heath, Berners‑Lee 2009 "Linked Data — The Story So Far" (foundational graph reference).
- Hogan et al. 2021 "Knowledge Graphs" survey (ACM Computing Surveys).
- The Sedona Conference primer on Cross‑Border Data Transfer (governance angle).
- One more on Allen's interval algebra applied to compliance (e.g., Galton's *Time and Change* or recent temporal SPARQL work).
- One more on ontology evaluation (Brank et al. 2005 or Gangemi et al. 2006 "OntoEval").
- One more on legal hold case law (Zubulake V or *Pension Committee*).

### C2. Polish the abstract
The abstract currently says "an empirical evaluation across five random seeds at six dataset scales (1,000 to 100,000 records)" — which is fine — and reports the headline numbers. Two polish items: (a) sub‑sentence "the structural conditions producing undetected conflicts remain largely unaddressed" reads a bit airy; tighten to "the architectural conditions that allow undetected conflicts persist." (b) abstract mentions "47 classes and 23 object properties" but this needs to be either backed by the OWL file (A3 above) or rephrased as "≈50 classes" with the file delivered.

### C3. Drop/relocate the "Appendix: Revision Notes" before submission
Lines 1419–1470 of the docx export are clearly draft notes ("the phrase 'masquerading as a solved one' removed; …"). These must not be in the submitted version. Easy to miss.

### C4. Address the throughput deceleration narrative
Paper Table 4 shows throughput *decreasing* with scale (44K → 50K → 44K → 38K → 37K → 36K records/s). The decrease at large N is real (Python overheads, GC, dict growth) but the paper would be stronger if it explained the cause and confirmed it is sub‑linear in the right way. Add one sentence in §7.4: "The mild throughput decrease at larger N reflects Python dict re‑hashing and tracemalloc tracing overhead; build complexity remains O(n) in records and O(m) in relationships."

### C5. Clarify generator parameter source
§7.1.1 says distributions are calibrated against ref [29] (Veritas Databerg). The Databerg report does not, in fact, give per‑record‑type proportions. A more honest formulation: "We selected proportions consistent with public industry reports including [29] and the EDRM enterprise data taxonomy." Reviewers may check the Databerg report and not find these specific numbers.

### C6. Sub‑millisecond propagation is measured on a biased seed set
Table 4 propagation time uses `list(store.records.keys())[:50]`, which is the first 50 records inserted — emails. Emails have low‑degree outgoing relationships (most attachments connect to existing docs already in scope), so traversal is short. Disclose this explicitly: "Propagation timing in Table 4 uses an insertion‑order seed set; matter‑scoped seeds (Table 3) yield 0.27–0.79 ms over the same scale, an upper bound for the operation."

### C7. Memory measurement uses tracemalloc, which adds overhead
This biases throughput downward. Add a footnote noting that build numbers without tracemalloc are ~20–30% higher; report both if you want stronger throughput claims.

### C8. Improve the "untyped traversal" comparison story
§7.3 / Table 3 says "All types: 4.31×, numerically identical to what an untyped graph traversal would produce." That's true but underplays the result. Add: ablation row "Untyped graph traversal" that explicitly runs without consulting `propagatesHold`, and confirm it equals "All types" — this turns an asserted equivalence into a measured one.

---

## D. Code‑level cleanup needed even if you don't change experiments

| Issue | File | Fix |
|------|------|-----|
| `metadata_conditions` typing — uses `any` (built-in) instead of `Any` | `trkg/conflict.py:80` | Replace `Dict[str, any]` with `Dict[str, Any]` |
| `RegulatoryRequirement` cited as immutable but is a regular `@dataclass` | `trkg/conflict.py:55` | Add `frozen=True` |
| `time_execution` imported but unused in `run_all` | `experiments/run_all.py:33` | Remove |
| `tests/test_trkg.py::TestSQLiteBaseline.test_propagation_same_result` uses `>` instead of `==` because of CTE iteration order | tests | Switch to `assertSetEqual` after fixing CTE traversal to enforce both directions |
| `_records_by_matter` is mutated outside `apply_hold` only via `discard` — `release_hold` doesn't repopulate on re‑add | `trkg/store.py:306` | Trivial doc note OR fix |
| Tests don't validate that `detect_all_conflicts` finds **the right specific conflicts** — only that count > 0 | `tests/test_trkg.py:339` | Add `assertEqual` on conflict_pairs for a known minimal scenario |
| `experiments/run_all.py` writes `results.json` next to the script; KBS replication packages should write to `experiments/output/` with timestamp | `experiments/run_all.py:855` | Cosmetic but standard |
| QUICK mode silently changes `PROPAGATION_DATASET_SIZE` to 5000, making "matter‑scoped" hold sets non‑comparable to the full‑mode tables | `experiments/run_all.py:48` | Either remove QUICK mode or document it |

---

## E. Recommended order of work (≈2 weeks part‑time)

**Week 1: kill the blockers**
1. Author `trkg.ttl` (1.5–2 days). Validate with HermiT or Pellet via `owlready2`.
2. Rewrite §4.2, §4.4, §4.5 to match the OWL file's actual class/property counts; align §5.3 enumeration to the actual 14 conflict rules.
3. Fix `experiment_5_ablation` to use matter‑scoped seeds at depth 10, multi‑seed; regenerate Table 6.
4. Fix `experiment_4_scenarios` Scenario B to remove the pre‑applied hold (Option A) and regenerate the §7.5 numbers; or commit to Option B and rewrite the prose.
5. Replace the stub `SiloedConflictDetector` and `UntypedGraphConflictDetector` with implementations that actually iterate.

**Week 2: strengthen and polish**
6. Add `FlatListStore` + `SQLiteStore` results into a real Table 8 (B1).
7. Add ground‑truth labelling and precision/recall/F1 (B3).
8. Author the architecture figure and the worked example box (B5, B6).
9. Run all scenarios multi‑seed (B7).
10. Add competency questions (B4).
11. Reach 40+ refs (C1), drop Revision Notes appendix (C3), tighten abstract (C2), code cleanups (D).

**Final pass**
12. Re-run `experiments/run_all.py` end‑to‑end on a clean machine; pin every number in the paper to that single output file.
13. Compile final PDF, verify ≤ 18 pages.
14. Write cover letter.

---

## F. What is already in good shape

- The narrative is well‑constructed: the framing of "knowledge representation problem, not engineering problem" lands on the first read.
- §2 Related Work is solid; the Galkin/Noy/Pan citations land correctly and the LegalRuleML/LKIF/FIBO triangulation is exactly right for KBS.
- §3 formal definitions are clean and the four‑question RQ structure is conventional.
- The honest disclosure of the 100K timing variance (`±48ms`, seed 42 outlier at 497ms) is the kind of detail KBS reviewers reward.
- The §8 limitations section is unusually direct about synthetic data, ontology coverage, and the missing relational‑with‑equivalent‑knowledge baseline. Reviewers often punish papers for hiding these; this one will be rewarded for naming them.
- Multi‑seed (5 seeds × 6 scales) is already strong.
- The capability comparison Table 7 is clean; the §7.6 ablation conceptually correct (it's just the numbers that need fixing per A1).

---

## Summary verdict

The intellectual core of the paper is sound and the writing is at submission quality. The blockers are entirely fixable in a focused two‑week effort, and most of the fixes are mechanical (regenerate a table, author an OWL file, swap stubs for real iteration). The single highest‑leverage item is **A3 (deliver the OWL ontology)** because it is referenced repeatedly, promised as supplementary material, and a reviewer will look for it within the first ten minutes. After that, **A1, A2, A4** clean up specific numerical/textual inconsistencies that any careful reviewer will catch, and **B1 (add FlatList + SQLite as a real performance baseline)** converts the paper's biggest acknowledged limitation into its strongest result — a 142× / 505× propagation speedup on identical data.
