"""SHACL Core baseline for conflict detection.

Only the rules expressible in SHACL Core are encoded; temporal, defeasible,
and recursive rules are out of scope and listed in shacl_limitations.json.
pyshacl runs with inference='none' and advanced=False to stay inside SHACL
Core. Latency is measured around pyshacl.validate only (RDF construction
excluded) for a fair comparison against the detector loop.
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pyshacl
from rdflib import Graph, Namespace

from trkg.schema import Record, Matter
from trkg.baselines.abox_to_rdf import build_abox, TRKG, INSTANCE


SHAPES_TTL = r"""
@prefix sh:   <http://www.w3.org/ns/shacl#> .
@prefix trkg: <http://example.org/trkg#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

# SHACL semantics note: a NodeShape describes what a *conforming* focus
# node looks like, so a violation is encoded by sh:not over the pattern we
# want to flag. This inversion is load-bearing for reading the shapes.

# Static surface of Hold-Deletion: a record marked DELETED that still
# carries an active hold. SHACL cannot reason about the temporal aspect.
trkg:NoActiveHoldOnDeletedShape a sh:NodeShape ;
    sh:targetClass trkg:Email, trkg:Document, trkg:FinancialRecord,
                   trkg:Invoice, trkg:TaxRecord, trkg:AuditWorkpaper,
                   trkg:Chat, trkg:Ticket, trkg:Contract, trkg:MedicalRecord,
                   trkg:Spreadsheet ;
    sh:not [
        sh:and (
            [ sh:path trkg:hasGovernanceState ; sh:hasValue "DELETED" ]
            [ sh:path trkg:onHoldFor ; sh:minCount 1 ]
        )
    ] ;
    sh:severity sh:Violation ;
    sh:message "Record is DELETED while still carrying an active hold (static aspect of Hold-Deletion conflict)." .

# Static surface of GDPR-vs-SOX Retention-Deletion: PII + public-company +
# EU jurisdiction on the same focus node. SHACL can flag the conjunction
# but cannot resolve the conflict; emitted as sh:Info.
trkg:GdprSoxStaticConflictShape a sh:NodeShape ;
    sh:targetClass trkg:FinancialRecord, trkg:Invoice, trkg:AuditWorkpaper, trkg:TaxRecord ;
    sh:not [
        sh:and (
            [ sh:path trkg:containsPii ; sh:hasValue true ]
            [ sh:path trkg:isPublicCompany ; sh:hasValue true ]
            [ sh:path trkg:hasJurisdiction ;
              sh:in ("EU" "EU_DE" "EU_ES" "EU_FR") ]
        )
    ] ;
    sh:severity sh:Info ;
    sh:message "Static attribute conjunction matches GDPR-vs-SOX Retention-Deletion conflict (temporal and priority dimensions out of scope for SHACL Core)." .
"""


@dataclass
class ShaclConflictResult:
    total_violations: int = 0
    violations_by_severity: Dict[str, int] = field(default_factory=dict)
    violations_by_message: Dict[str, int] = field(default_factory=dict)
    detection_time_ms: float = 0.0
    expressible_rule_count: int = 0
    skipped_rule_families: List[str] = field(default_factory=list)
    abox_triples: int = 0


class ShaclBaseline:
    """SHACL Core baseline. Out-of-scope rule families are reported in
    `skipped_rule_families`."""

    LIMITATIONS_FILE = Path(__file__).parent / "shacl_limitations.json"

    def __init__(self, shapes_ttl: Optional[str] = None):
        self.shapes_graph = Graph()
        self.shapes_graph.parse(data=shapes_ttl or SHAPES_TTL, format="turtle")
        with open(self.LIMITATIONS_FILE) as f:
            self.limitations = json.load(f)
        self.expressible_rule_count = len(self.limitations["expressible_in_shacl"])
        self.skipped_rule_families = [
            entry["rule"] for entry in self.limitations["not_expressible_in_shacl"]
        ]

    def detect_all_conflicts(
        self,
        records: Dict[str, Record],
        matters: Optional[Dict[str, Matter]] = None,
    ) -> ShaclConflictResult:
        data_graph = build_abox(records, matters)
        abox_triples = len(data_graph)

        start = time.perf_counter()
        conforms, report_graph, _ = pyshacl.validate(
            data_graph,
            shacl_graph=self.shapes_graph,
            inference="none",
            advanced=False,
            abort_on_first=False,
            meta_shacl=False,
            debug=False,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        SH = Namespace("http://www.w3.org/ns/shacl#")
        violations = list(report_graph.subjects(predicate=SH.resultSeverity))
        by_sev: Dict[str, int] = {}
        by_msg: Dict[str, int] = {}
        for v in violations:
            sev = next(report_graph.objects(v, SH.resultSeverity), None)
            msg = next(report_graph.objects(v, SH.resultMessage), None)
            sev_name = sev.split("#")[-1] if sev else "Unknown"
            by_sev[sev_name] = by_sev.get(sev_name, 0) + 1
            if msg:
                key = str(msg)[:80]
                by_msg[key] = by_msg.get(key, 0) + 1

        return ShaclConflictResult(
            total_violations=len(violations),
            violations_by_severity=by_sev,
            violations_by_message=by_msg,
            detection_time_ms=elapsed_ms,
            expressible_rule_count=self.expressible_rule_count,
            skipped_rule_families=self.skipped_rule_families,
            abox_triples=abox_triples,
        )
