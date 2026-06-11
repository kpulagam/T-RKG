"""E4 Step 3 — generate the hidden ground truth for the labeling experiment.

Runs T-RKG's applicability predicate (`ConflictDetector.infer_applicable_regulations`,
the SAME evaluator the paper's experiments use) over every row of
`E4_labeling_sheet.csv`, keyed by record_id, and writes the per-record verdict to
`ground_truth_hidden.json`.

This is NOT scored against `E4_reference_key.csv` here; the reference key is an
externally-computed answer, NOT ground truth. Step 4 diffs the two so a human can
review where the sheet, the reference rules, and T-RKG's encoding disagree.

--- Attribute mapping (sheet -> internal Record) ---
The sheet carries descriptive record-type names; the predicate keys on the
`RecordType` enum. The mapping below is a deliberate modeling choice. Records with
no dedicated enum member (BenefitsEnrollment, BillingAddress, AdoptionRecord,
BiometricData) fall back to RecordType.OTHER — a judgment call that will surface
as disagreements in the Step 4 diff (e.g. they then match only PII/PHI-gated,
type-agnostic regulations). PatientInvoice maps to INVOICE; any clinical aspect is
carried by contains_phi (HIPAA is type-agnostic, requires_phi). Other attributes:
  jurisdiction string  -> Jurisdiction[<name>]
  PII   TRUE/FALSE      -> Record.contains_pii
  PHI   TRUE/FALSE      -> Record.contains_phi
  public_company T/F    -> Record.metadata["is_public_company"]
"""

import csv
import json
from datetime import datetime
from pathlib import Path

from trkg.schema import Record, RecordType, Jurisdiction
from trkg.conflict import ConflictDetector

HERE = Path(__file__).resolve().parent
SHEET = HERE / "E4_labeling_sheet.csv"
OUT = HERE / "ground_truth_hidden.json"

# Descriptive sheet record_type -> internal RecordType enum.
RECORD_TYPE_MAP = {
    "PatientInvoice": RecordType.INVOICE,
    "Invoice": RecordType.INVOICE,
    "Email": RecordType.EMAIL,
    "Chat": RecordType.CHAT,
    "Ticket": RecordType.TICKET,
    "Contract": RecordType.CONTRACT,
    "TaxRecord": RecordType.TAX,
    "BankStatement": RecordType.FINANCIAL,
    "FinancialStatement": RecordType.FINANCIAL,
    "AuditWorkpaper": RecordType.AUDIT,
    "MedicalRecord": RecordType.MEDICAL,
    "AllergyRecord": RecordType.MEDICAL,
    "AutopsyReport": RecordType.MEDICAL,
    # No dedicated enum member -> OTHER (judgment call; see module docstring).
    "BenefitsEnrollment": RecordType.OTHER,
    "BillingAddress": RecordType.OTHER,
    "AdoptionRecord": RecordType.OTHER,
    "BiometricData": RecordType.OTHER,
}


def _bool(s: str) -> bool:
    return s.strip().upper() == "TRUE"


def row_to_record(row: dict) -> Record:
    rtype = RECORD_TYPE_MAP[row["record_type"]]
    jur = Jurisdiction[row["jurisdiction"].strip()]
    now = datetime(2024, 1, 1)
    return Record(
        id=row["record_id"],
        type=rtype,
        title=row["record_id"],
        created=now,
        modified=now,
        contains_pii=_bool(row["PII"]),
        contains_phi=_bool(row["PHI"]),
        jurisdiction=jur,
        metadata={"is_public_company": _bool(row["public_company"])},
    )


def main() -> None:
    detector = ConflictDetector()
    out = {}
    with SHEET.open(newline="") as f:
        for row in csv.DictReader(f):
            rec = row_to_record(row)
            regs = sorted(r.value for r in detector.infer_applicable_regulations(rec))
            out[row["record_id"]] = {
                "record_type": row["record_type"],
                "jurisdiction": row["jurisdiction"],
                "PII": _bool(row["PII"]),
                "PHI": _bool(row["PHI"]),
                "public_company": _bool(row["public_company"]),
                "mapped_record_type": rec.type.value,
                "trkg_regulations": regs,
            }
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    print(f"Wrote {len(out)} records -> {OUT}")


if __name__ == "__main__":
    main()
