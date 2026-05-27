# T-RKG Patent Assessment

**Caveat.** I am not a patent attorney. What follows is research-level analysis to inform a conversation with a registered patent attorney (and with PayPal IP counsel). Filing decisions, prior-art clearance opinions, and claim drafting must come from a licensed practitioner with access to the full PAIR / PatBase / Derwent corpora and deeper specialty expertise than a web search affords.

---

## 1. Is software like this even patentable in 2026?

Yes, but the bar is high and the framing matters more than the technology.

The current US standard for software patent eligibility is the two-step *Alice/Mayo* test enforced under 35 U.S.C. §101. Step 1 asks whether the claim is directed to a judicial exception, which for software almost always means an "abstract idea" (mathematical formulas, mental processes, methods of organizing human activity). Step 2 asks whether the claim recites "significantly more" — typically a specific technical improvement to computer functionality rather than a generic computer implementation of an abstract idea.

The empirical backdrop is sobering. Approximately 64% of software patents challenged on §101 grounds since *Alice* (2014) have been invalidated. In 2024, the Federal Circuit decided 22 patent cases on substantive §101 grounds and found claims eligible in **exactly one** of them. That is the bar.

There is one piece of good news for your category. The USPTO issued [revised guidance in late 2025 and a memo in August 2025](https://www.uspto.gov/sites/default/files/documents/memo-101-20250804.pdf) that explicitly cautions examiners against stretching the "mental process" rejection to limitations that cannot practically be performed in the human mind, and instructs them to issue §101 rejections only when ineligibility is more likely than not. The 2024 Guidance Update on AI eligibility was rescinded in November 2025 and the USPTO now treats AI-assisted inventions under the same standard as any other software, which is neither a tailwind nor a headwind specifically.

Net: yes, this category is patentable in principle; you have to claim it the right way; you should expect a §101 office action and you have to be ready to overcome it.

## 2. What is already in the prior-art space?

Three patent families matter for T-RKG. None of them blocks a properly drafted T-RKG claim, but each constrains it.

**SAP "Legal hold" family (US20090150866, US10692162B2 and related continuations).** [US20090150866A1](https://patents.google.com/patent/US20090150866) covers enforcing legal holds on heterogeneous objects (transactional data, documents, archives, source code) by associating each object with a "hold record" via a lookup table, and verifying the hold by walking parent/root object relationships. [US10692162B2](https://patents.google.com/patent/US10692162B2/en) covers managing legal holds on cloud documents through a legal-hold framework, legal-hold index, and legal-hold metadata. Both are SAP. Both predate T-RKG. The relevant differences are: SAP's framing is hold-as-flag-on-object plus parent/root lookup; T-RKG's framing is hold propagation as ontologically-typed graph traversal where each edge type carries a `propagatesHold` semantic property and propagation is governed by per-matter policies. SAP does not claim ontological reasoning over regulatory applicability and does not claim conflict detection. The 2009 application's term runs ~2028; the 2014-filed grant runs until ~2034. **Implication: avoid claiming "associating an object with a legal hold record via a lookup" or "preserving cloud documents through a legal-hold index" as core elements. Claim the typed-relationship semantic propagation instead.**

**OneTrust privacy-management family (US10,997,542; US11,195,134; US11,410,106; US10,614,246; ~27 issued patents total).** OneTrust holds an active portfolio on privacy-rights automation: data subject access request (DSAR) processing, privacy-impact-assessment generation, vendor-compliance scanning, and consent management. These claims are oriented around **single-regulation workflows** (typically GDPR, CCPA, or LGPD individually) and around **process automation** (form generation, ticket routing). They do **not** reach into the multi-regulation conflict detection space. **Implication: the multi-regulation cross-domain conflict story is open territory; the per-regulation DSAR-fulfillment story is fenced.**

**Policy / rule conflict detection.** [US8327414B2](https://patents.google.com/patent/US8327414) (IBM, "Performing policy conflict detection and resolution using semantic analysis") covers detecting conflicts between two policies by semantic equivalence of policy targets. That is closer to T-RKG's conflict-detection mechanism than the SAP patents are. The differentiation is real but narrower: IBM's claims are framed around policy *targets* and semantic equivalence between policies; T-RKG's claims would be framed around *applicability inference for individual records* under jurisdictional subsumption, with conflict triggered by pairwise applicability of two regulations on the same record. Different inference structure, different claim scope. **Implication: cite IBM's patent in the application; differentiate on (i) jurisdictional subsumption as a substantive predicate, (ii) record-level rather than policy-level conflict, (iii) the composite-record attribute aggregation.**

**Knowledge graph / ontology generic patents.** Many exist (US20120158633A1 KG-based search, US20100280989A1 ontology creation by reference to a corpus, US7099885B2 collaborative ontology modeling). These are upstream and not directly blocking. They might be cited for novelty rejections; they are not anticipations.

**Things I did NOT find.** I found no patent that combines (a) ontological applicability inference over multi-attribute composite records, (b) typed-relationship hold propagation governed by per-matter semantic policies, and (c) cross-domain regulatory conflict detection across privacy and financial regulations. That gap is consistent with the academic-literature gap T-RKG also fills (the construction-industry frontier paper I found in the search literally says "the analysis of regulatory overlaps and conflicts across multiple documents remains a largely unexplored area"). The combination is genuinely novel.

## 3. Is T-RKG patentable? My honest read.

**Yes, with three caveats.**

Caveat one: not the whole system at once. A monolithic claim "a knowledge-based system for governance" will be rejected as abstract under Alice. The right strategy is a portfolio of narrower claims, each tied to a specific technical mechanism with measurable computational improvement.

Caveat two: the mathematics in §5.6 of the paper (the formal complexity bounds and the recall-ceiling theorem) is exactly the right kind of evidence for §101 rebuttal. "Improvement to computer functionality" arguments are stronger when you can point to a measured technical effect (the 121×–406× propagation speedup, the F1 = 0.823 robustness number, the linear-versus-nothing applicability gap). Keep the paper's empirical rigor close at hand; it directly supports the patent.

Caveat three: PayPal will own this if you file as an employee under standard IP-assignment terms, which is what you want anyway. PayPal has a pre-existing interest in records governance (financial-services compliance is core to their business). They are likely to support filing for that reason. The patent attorney conversation should start with PayPal IP counsel, not external counsel.

## 4. Specific claims I would draft (for the patent attorney to refine)

These are sketches. The actual claim language has to be drafted by counsel. They are organized as a "main claim plus dependent claims plus separable independent claims" structure.

**Independent Claim A — composite-record applicability inference.**
A computer-implemented method for determining the regulatory applicability of an enterprise record, comprising:
- assembling, by a connector layer, a composite record entity comprising attributes drawn from at least two different source systems, where the attributes include at least one of (i) a personally-identifiable-information indicator, (ii) a jurisdictional classification, and (iii) an organizational-metadata flag;
- evaluating, by an applicability-inference engine, an ontologically-defined applicability predicate for each of a plurality of regulatory frameworks against the assembled composite record, wherein the predicate evaluation includes resolution of the record's jurisdiction against a hierarchical jurisdiction subsumption structure;
- producing an applicability set identifying the subset of regulatory frameworks for which the predicate evaluates true.

This is the "composite record" claim. It captures the structural distinction from content-centric vendors (Microsoft Purview, OpenText, IBM FileNet, Veritas). It survives §101 by tying applicability inference to a specific multi-source aggregation step that no human reviewer practically performs at scale and that produces a measurable accuracy improvement (the F1 = 1.000 vs. 0.113 vs. 0.581 result quantifies the benefit).

**Independent Claim B — typed-relationship semantic hold propagation.**
A computer-implemented method for propagating a legal hold across an enterprise records knowledge graph, comprising:
- maintaining a directed graph in which each edge is associated with a relationship type drawn from a typed ontology, and each relationship type is associated with at least one Boolean propagation property and an ordinal strength property;
- receiving a propagation policy associated with a legal matter, wherein the propagation policy specifies a subset of relationship types that propagate the hold;
- performing a depth-bounded breadth-first traversal from a seed set of records, wherein at each candidate edge the traversal consults the relationship type's propagation property and the matter's policy before extending the hold set;
- producing a hold set in which each included record is associated with a typed-edge witness path identifying the relationship sequence by which it was reached.

The auditable witness path is the differentiator from SAP US20090150866 and US10692162B2. SAP claims hold-as-record and parent/root walking; T-RKG claims typed-edge policy-governed traversal with semantic justification per included record. The legal-defensibility argument from the paper (litigation counsel can articulate why each record is in scope) maps directly to the patent value proposition (an auditable governance decision is a different functional outcome than an unauditable one).

**Independent Claim C — cross-domain regulatory conflict detection.**
A computer-implemented method for detecting cross-domain regulatory conflicts on records distributed across heterogeneous source systems, comprising:
- inferring, for each record in a corpus, an applicability set of regulatory frameworks via the method of Claim A;
- for each record whose applicability set contains two or more frameworks, evaluating a pairwise conflict predicate from a precomputed rule table indexed by ordered framework pairs;
- classifying detected conflicts into one of: a retention-deletion class indicating mutually-exclusive operative requirements between a retention regulation and a deletion regulation; a jurisdiction class indicating overlapping jurisdictional scope with incompatible mandates; a hold-deletion class indicating an active legal hold versus a deletion-on-request requirement; or a priority class indicating two retention mandates with inconsistent durations and no statutory precedence;
- emitting a structured conflict record for each detection, comprising the regulation pair, classification, severity assessment derived from the ontology, and ontology-attached resolution guidance.

This is the cross-domain claim. It differentiates from IBM US8327414 (which is policy-target semantic equivalence, not record-level multi-regulation pairwise application) and from OneTrust's per-regulation workflow patents.

**Dependent claims** would specialize each independent claim with: (i) the bitemporal valid-time / transaction-time indexing for point-in-time reconstruction; (ii) the OWL/Turtle ontology serialization with specific class and property counts; (iii) the four-policy propagation taxonomy (Conservative / Standard / Comprehensive / Custom); (iv) the noise-tolerance behavior under perturbed inputs (the F1 = 0.823 result); (v) the specific connector-layer architecture with O(1) governance-operation lookup indices.

## 5. Strategic recommendations

**Do file.** The combination of (composite record + typed-relationship semantic propagation + cross-domain conflict detection) is genuinely novel and the prior-art landscape leaves room. The math in §5.6 of the paper is unusually well-suited to a §101 rebuttal because it states the system's behavior as theorems with measurable empirical backing.

**File through PayPal IP counsel, not external counsel directly.** Two reasons. First, the assignment terms in your employment contract almost certainly route this through PayPal's filing pipeline anyway. Second, PayPal's existing patent counsel are well-versed in financial-services compliance prior art and will have access to internal disclosures and FTO opinions you do not. Talk to your manager and to PayPal IP counsel before talking to external practitioners.

**Move quickly.** A peer-reviewed publication is a public disclosure under 35 U.S.C. §102. The US has a one-year grace period from your own publication for filing in the US, but most foreign jurisdictions (EU, Japan, China) have no grace period at all. If you publish the IEEE Access paper before filing, you forfeit foreign rights. The right sequence is: (1) file at least a US provisional application before submitting to IEEE Access, then (2) submit to IEEE Access, then (3) within 12 months of the provisional, file a non-provisional (and PCT for foreign rights). A provisional is cheap to file (a few thousand dollars in attorney time) and starts the priority clock without all the formalism of a non-provisional.

**Three independent claims, not one.** Treat the composite record, the typed-edge hold propagation, and the cross-domain conflict detection as separable inventions. If you file them as one application the examiner may issue a restriction requirement and force you to elect; if you file them as three closely-related applications (or as one application with three independent claims that you are prepared to divide later), you preserve flexibility.

**Don't oversell to PayPal.** A defensive patent (filed primarily to deter litigation and to satisfy customer "do you own the IP?" questions) is what this realistically is. It is not a Microsoft Purview-killer that PayPal will license to other Fortune 500s. Frame internally as "defensive IP that protects our governance architecture and creates an EB-1A-relevant publication record." That framing matches reality and avoids over-promising.

**The EB-1A angle.** A pending or issued patent is independently citeable evidence under the EB-1A "original contributions of major significance" criterion. The application receipt, the published application (18 months after filing), and the eventual grant are all separately useful as evidence at different points in the EB-1 timeline. Even if the patent is never granted, the act of filing creates a bibliographic record and a USPTO-issued application number that attorneys can cite in petition support letters.

## 6. Honest probability assessment

- Is the combination patentable in principle, given current §101 standards? **Yes, probably (60–70% confidence).**
- Will a properly drafted application clear examination on first action? **No (10–20%).** Expect a §101 rejection on first action; expect to win on the rebuttal armed with the §5.6 math and the empirical results.
- Will a granted patent be enforceable in litigation against a competitor? **Uncertain.** Software patents in this space are often invalidated under §101 in district court even after grant. A defensive value (deterrence + customer reassurance + EB-1 evidence) is more reliable than an offensive value.
- Will PayPal want to file? **Highly likely.** Records governance is core to their business. They have an interest in protecting their architecture. The marginal cost of a US provisional is small.
- Time to grant if filed today? **24 to 48 months for a non-provisional application; provisional has no grant, only a 12-month priority window.**

## 7. Concrete next steps

1. Identify PayPal's internal patent disclosure form (sometimes called an Invention Disclosure Form or IDF) and submit a description of the composite-record + typed-relationship + conflict-detection invention. Use Section 5 of this document as a starting outline.
2. Schedule a meeting with PayPal IP counsel. Bring the IEEE Access manuscript, the OWL ontology file, the experimental results (especially the F1 and robustness numbers), and the §5.6 mathematical results. The math is your strongest §101 rebuttal material.
3. **Do not submit to IEEE Access** until either (a) the provisional is filed, or (b) you are willing to forfeit non-US patent rights. If PayPal files a provisional, you can submit the same week.
4. Discuss with PayPal IP counsel whether to file the three independent claims as one application or three. There are legitimate arguments either way.
5. Once the provisional is filed, the EB-1A evidence value of the patent application is immediate. The application receipt and (later) the published application can be cited by your immigration attorney.

## 8. A note on what this patent is *not*

It is not a foundational patent that will block competitors from doing records governance. The space is already mature, the prior art is dense, and even a granted patent in this area faces ongoing §101 risk. It is a defensive IP asset that protects a specific architectural approach (composite records + ontological applicability + typed semantic propagation + cross-domain conflict detection) and serves as bibliographic evidence of original contribution. Under both of those framings it is worth filing. As a strategic offensive weapon it would be ambitious.

Sources used in this analysis:
- [USPTO MPEP §2106 — Patent Subject Matter Eligibility](https://www.uspto.gov/web/offices/pac/mpep/s2106.html)
- [USPTO §101 Memo, August 2025](https://www.uspto.gov/sites/default/files/documents/memo-101-20250804.pdf)
- [USPTO 2024 AI Eligibility Guidance Update (later rescinded)](https://www.federalregister.gov/documents/2024/07/17/2024-15377/2024-guidance-update-on-patent-subject-matter-eligibility-including-on-artificial-intelligence)
- [Venable LLP, "The §101 Reset for 2026: New USPTO Guidance on AI Eligibility"](https://www.venable.com/insights/publications/2025/12/the-101-reset-for-2026)
- [Foley & Lardner, "Alice Patent Eligibility Analysis Divergence Before USPTO and District Court"](https://www.foley.com/insights/publications/2024/09/alice-patent-eligibility-analysis-divergance-before-uspto-and-district-court/)
- [Dykema, "USPTO Raises Bar for §101 Rejections in AI Patents"](https://www.dykema.com/news-insights/uspto-raises-bar-for-101-rejections-in-ai-patents.html)
- [SAP US20090150866A1 — Enforcing legal holds of heterogeneous objects](https://patents.google.com/patent/US20090150866)
- [SAP US10692162B2 — Managing a legal hold on cloud documents](https://patents.google.com/patent/US10692162B2/en)
- [IBM US8327414B2 — Performing policy conflict detection using semantic analysis](https://patents.google.com/patent/US8327414)
- [OneTrust patent portfolio (Justia)](https://patents.justia.com/assignee/onetrust-llc)
- [OneTrust US10,997,542 — Privacy management systems](https://uspto.report/patent/grant/10,997,542)
- [OneTrust US10,614,246 — Auditing data request compliance](https://uspto.report/patent/grant/10,614,246)
