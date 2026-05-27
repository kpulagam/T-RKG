"""Convert a dict of Records (and optional Matters) into an rdflib Graph
suitable for SHACL validation. Kept separate so the core code has no
rdflib dependency.
"""

from datetime import datetime
from typing import Dict, Optional

from rdflib import Graph, Namespace, Literal, URIRef, RDF, RDFS, XSD

from trkg.schema import Record, Matter


TRKG = Namespace("http://example.org/trkg#")
INSTANCE = Namespace("http://example.org/trkg/instance/")


def _record_type_iri(rt) -> URIRef:
    name_map = {
        "EMAIL": "Email",
        "DOCUMENT": "Document",
        "MEDICAL": "MedicalRecord",
        "SPREADSHEET": "Spreadsheet",
        "CHAT": "Chat",
        "TICKET": "Ticket",
        "CONTRACT": "Contract",
        "FINANCIAL": "FinancialRecord",
        "AUDIT": "AuditWorkpaper",
        "INVOICE": "Invoice",
        "TAX": "TaxRecord",
    }
    return TRKG[name_map.get(rt.name, "Record")]


def build_abox(
    records: Dict[str, Record],
    matters: Optional[Dict[str, Matter]] = None,
) -> Graph:
    """Build the minimal ABox needed by the SHACL shapes."""
    g = Graph()
    g.bind("trkg", TRKG)
    g.bind("inst", INSTANCE)

    matters = matters or {}
    for mid, m in matters.items():
        miri = INSTANCE[mid]
        g.add((miri, RDF.type, TRKG.Matter))
        g.add((miri, TRKG.legalObligationFlag,
               Literal(bool(m.legal_obligation_flag), datatype=XSD.boolean)))
        g.add((miri, TRKG.legalClaimFlag,
               Literal(bool(m.legal_claim_flag), datatype=XSD.boolean)))

    for rid, r in records.items():
        riri = INSTANCE[rid]
        g.add((riri, RDF.type, _record_type_iri(r.type)))
        g.add((riri, RDFS.label, Literal(r.title or rid)))
        g.add((riri, TRKG.hasJurisdiction, Literal(r.jurisdiction.value)))
        g.add((riri, TRKG.containsPii,
               Literal(bool(r.contains_pii), datatype=XSD.boolean)))
        g.add((riri, TRKG.containsPhi,
               Literal(bool(r.contains_phi), datatype=XSD.boolean)))
        g.add((riri, TRKG.hasGovernanceState, Literal(r.governance_state.value)))
        if r.metadata.get("is_public_company"):
            g.add((riri, TRKG.isPublicCompany, Literal(True, datatype=XSD.boolean)))
        for mid in r.hold_matters:
            g.add((riri, TRKG.onHoldFor, INSTANCE[mid]))
    return g
