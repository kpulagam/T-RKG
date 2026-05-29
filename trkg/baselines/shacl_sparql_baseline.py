"""SHACL-SPARQL baseline (E6).

The SHACL Core baseline (shacl_baseline.py) can only express per-node static
attribute conjunctions. SHACL-SPARQL (sh:sparql constraint components, W3C SHACL
§5) lifts that ceiling: a SPARQL SELECT can join across nodes and use
FILTER NOT EXISTS, so three conflict families that Core cannot reach become
expressible:

  * RETENTION_DELETION — a deletion-bearing record (PII in an EU jurisdiction)
    that is also a SOX-retained public-company financial record.
  * HOLD_DELETION with GDPR Art. 17(3) defeasibility — a deletion-eligible
    record on a legal hold, *unless* one of its holding matters carries a
    legal_obligation / legal_claim basis. The exemption is the cross-record
    join + negation that Core cannot do (documented in shacl_limitations.json,
    family "GDPR Article 17(3) exemption suppression").
  * JURISDICTION — a PII record subject to two privacy regimes at once
    (EU + California, or EU + Canada), using the additional-jurisdiction
    triples this module adds to the ABox.

What SHACL-SPARQL STILL cannot do, and is therefore *not* claimed here
(reported in `skipped_rule_families`):

  * PRIORITY / defeasible max-retention resolution — non-monotonic, no priority
    semantics in SHACL (limitations file: "Defeasible priority resolution").
  * Hold-propagation closure across typed relationships — a fixed-point /
    transitive-closure operator; recursion across a single sh:sparql constraint
    is not supported with portable semantics (limitations file: "Cross-record
    propagation closure").

Latency is measured around pyshacl.validate only (ABox construction excluded),
matching the SHACL Core baseline so the two are directly comparable.

Pinned engine versions (recorded in the result for reproducibility):
pyshacl 0.31.0, rdflib 7.6.0. sh:sparql requires advanced=True.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

import pyshacl
import rdflib
from rdflib import Graph, Namespace, Literal, URIRef, XSD

from trkg.schema import Record, Matter
from trkg.baselines.abox_to_rdf import build_abox, TRKG, INSTANCE


# Families this baseline encodes, mapped to the IRI of the shape that emits
# them so validation results can be grouped back into families.
SH = Namespace("http://www.w3.org/ns/shacl#")

SHAPES_TTL = r"""
@prefix sh:   <http://www.w3.org/ns/shacl#> .
@prefix trkg: <http://example.org/trkg#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

# Every record instance is additionally typed trkg:Record by this baseline so a
# single targetClass covers all record kinds (added in Python before validate).
# SPARQL bodies use Turtle ''' long-strings so the embedded "..." literals and
# newlines are preserved verbatim.

trkg:RetentionDeletionSparqlShape a sh:NodeShape ;
    sh:targetClass trkg:Record ;
    sh:sparql [
        sh:message "RETENTION_DELETION: EU PII record that is also a SOX-retained public-company financial record." ;
        sh:select '''
            PREFIX trkg: <http://example.org/trkg#>
            SELECT $this WHERE {
                $this trkg:containsPii true .
                $this trkg:isPublicCompany true .
                $this trkg:hasJurisdiction ?j .
                FILTER(?j IN ("EU", "EU_DE", "EU_ES", "EU_FR"))
            }
        ''' ;
    ] ;
    sh:severity sh:Violation .

trkg:HoldDeletionDefeasibleSparqlShape a sh:NodeShape ;
    sh:targetClass trkg:Record ;
    sh:sparql [
        sh:message "HOLD_DELETION: deletion-eligible record on hold with no Art. 17(3) legal-obligation/claim exemption among its holding matters." ;
        sh:select '''
            PREFIX trkg: <http://example.org/trkg#>
            SELECT $this WHERE {
                $this trkg:containsPii true .
                $this trkg:hasJurisdiction ?j .
                FILTER(?j IN ("EU", "EU_DE", "EU_ES", "EU_FR", "US_CA", "CA"))
                $this trkg:onHoldFor ?m .
                FILTER NOT EXISTS {
                    $this trkg:onHoldFor ?m2 .
                    { ?m2 trkg:legalObligationFlag true }
                    UNION
                    { ?m2 trkg:legalClaimFlag true }
                }
            }
        ''' ;
    ] ;
    sh:severity sh:Violation .

trkg:JurisdictionSparqlShape a sh:NodeShape ;
    sh:targetClass trkg:Record ;
    sh:sparql [
        sh:message "JURISDICTION: PII record subject to two privacy regimes (EU + California, or EU + Canada)." ;
        sh:select '''
            PREFIX trkg: <http://example.org/trkg#>
            SELECT DISTINCT $this WHERE {
                $this trkg:containsPii true .
                { $this trkg:hasJurisdiction ?ja } UNION { $this trkg:additionalJurisdiction ?ja }
                FILTER(?ja IN ("EU", "EU_DE", "EU_ES", "EU_FR"))
                { $this trkg:hasJurisdiction ?jb } UNION { $this trkg:additionalJurisdiction ?jb }
                FILTER(?jb IN ("US_CA", "CA"))
            }
        ''' ;
    ] ;
    sh:severity sh:Violation .
"""


SHAPE_FAMILY = {
    "http://example.org/trkg#RetentionDeletionSparqlShape": "RETENTION_DELETION",
    "http://example.org/trkg#HoldDeletionDefeasibleSparqlShape": "HOLD_DELETION",
    "http://example.org/trkg#JurisdictionSparqlShape": "JURISDICTION",
}

# Families T-RKG covers that SHACL-SPARQL still cannot express, with the
# governing SHACL limitation. Surfaced in the result for honest reporting.
SKIPPED_RULE_FAMILIES = [
    {
        "rule": "PRIORITY (defeasible max-retention resolution)",
        "missing_feature": "SHACL has no priority/non-monotonic semantics; "
        "SOX>SEC>IRS max-retention selection cannot be expressed.",
    },
    {
        "rule": "Hold-propagation closure across typed relationships",
        "missing_feature": "Fixed-point / transitive closure; recursion across "
        "a single sh:sparql constraint has no portable semantics.",
    },
]


@dataclass
class ShaclSparqlResult:
    total_violations: int = 0
    flagged_by_family: Dict[str, Set[str]] = field(default_factory=dict)
    counts_by_family: Dict[str, int] = field(default_factory=dict)
    detection_time_ms: float = 0.0
    abox_triples: int = 0
    skipped_rule_families: List[Dict[str, str]] = field(default_factory=list)
    engine: Dict[str, str] = field(default_factory=dict)


def _augment_abox(records: Dict[str, Record], matters: Optional[Dict[str, Matter]]) -> Graph:
    """build_abox + two additions E6 needs: a common trkg:Record type on every
    record instance (single targetClass), and additionalJurisdiction triples
    for multi-jurisdiction records. Both are local to this baseline; the SHACL
    Core baseline and its ABox are untouched."""
    g = build_abox(records, matters)
    from rdflib import RDF
    for rid, r in records.items():
        riri = INSTANCE[rid]
        g.add((riri, RDF.type, TRKG.Record))
        for extra in getattr(r, "additional_jurisdictions", None) or []:
            g.add((riri, TRKG.additionalJurisdiction, Literal(extra.value)))
    return g


class ShaclSparqlBaseline:
    """SHACL-SPARQL baseline. advanced=True enables sh:sparql constraints."""

    def __init__(self, shapes_ttl: Optional[str] = None):
        self.shapes_graph = Graph()
        self.shapes_graph.parse(data=shapes_ttl or SHAPES_TTL, format="turtle")
        self.engine = {"pyshacl": pyshacl.__version__, "rdflib": rdflib.__version__}

    def detect_all_conflicts(
        self,
        records: Dict[str, Record],
        matters: Optional[Dict[str, Matter]] = None,
    ) -> ShaclSparqlResult:
        data_graph = _augment_abox(records, matters)
        abox_triples = len(data_graph)

        start = time.perf_counter()
        _conforms, report_graph, _ = pyshacl.validate(
            data_graph,
            shacl_graph=self.shapes_graph,
            inference="none",
            advanced=True,        # required for sh:sparql
            abort_on_first=False,
            meta_shacl=False,
            debug=False,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        flagged: Dict[str, Set[str]] = {fam: set() for fam in SHAPE_FAMILY.values()}
        total = 0
        for result in report_graph.subjects(predicate=SH.resultSeverity):
            total += 1
            source = next(report_graph.objects(result, SH.sourceShape), None)
            focus = next(report_graph.objects(result, SH.focusNode), None)
            family = SHAPE_FAMILY.get(str(source))
            if family is None or focus is None:
                continue
            rid = str(focus).rsplit("/", 1)[-1]
            flagged[family].add(rid)

        return ShaclSparqlResult(
            total_violations=total,
            flagged_by_family=flagged,
            counts_by_family={k: len(v) for k, v in flagged.items()},
            detection_time_ms=elapsed_ms,
            abox_triples=abox_triples,
            skipped_rule_families=SKIPPED_RULE_FAMILIES,
            engine=self.engine,
        )
