"""Cross-system attribute partition: the shared "siloed / decomposed view".

The novelty T-RKG claims is *cross-system composition*: a single governance
decision is driven by attributes that, in a real enterprise, live in different
source systems. This module makes that composition an explicit, controllable
variable so experiments can switch it off.

Each governance-relevant attribute is assigned a *home source system*. A
record's home system is `record.system_id` (the σ(r) of the paper). The
**siloed view** of a record keeps only the attributes whose home system equals
the record's own home system; every *foreign* attribute is reset to the value a
system that never sees it would assume (absence / False). Reasoning over the
siloed view therefore cannot compose attributes that span systems.

Attribute → home-system map (documented and asserted):
  * contains_pii  → customer-data system (CRM). PII is identified where
                    customer/contact data is managed, not in the ERP ledger or
                    the mail store.
  * contains_phi  → customer-data system (CRM), same rationale.
  * is_public_company → ERP / financial system. Listing status is a property of
                    the financial system of record, so an ERP-resident financial
                    record keeps it (intra-domain SOX/SEC/IRS priority conflicts
                    still fire), but an email or chat never carries it.
  * jurisdiction  → travels with the record's home system (always visible).
  * record type   → intrinsic to the record (always visible).

Consequence (the validity invariant for E1-siloed and E5-decomposed): a
cross-domain conflict needs a *deletion* regulation (GDPR/CPRA/PIPEDA, all of
which require PII) on the same record as a *retention* regulation. PII is
CRM-owned, so any non-CRM record loses PII in the siloed view and can no longer
trigger a deletion regulation — driving cross-domain recall to ≈ 0. CRM records
keep PII but are tickets, which match no retention regulation's record-type
scope, so they cannot form a cross-domain pair either.
"""

import copy
from typing import Dict, List

from trkg.schema import Record


# Home source system for each cross-system trigger attribute.
ATTRIBUTE_HOME_SYSTEM: Dict[str, str] = {
    "contains_pii": "sys_crm",
    "contains_phi": "sys_crm",
    "is_public_company": "sys_erp",
}

# The attributes that can be *foreign* to a record's home system and are
# therefore masked in the siloed view. Jurisdiction and record type are
# intrinsic / home-resident and are never masked.
CROSS_SYSTEM_TRIGGER_ATTRS: List[str] = list(ATTRIBUTE_HOME_SYSTEM.keys())


def _attr_value(record: Record, attr: str):
    if attr == "is_public_company":
        return bool(record.metadata.get("is_public_company", False))
    return bool(getattr(record, attr, False))


def siloed_view(record: Record) -> Record:
    """Return a deep copy of `record` with every foreign trigger attribute reset.

    An attribute is *foreign* when its home system differs from the record's own
    `system_id`. Foreign booleans become False; a foreign `is_public_company`
    key is removed from metadata so `RegulationProfile.applies_to` sees its
    absence. Jurisdiction, `additional_jurisdictions`, and type are preserved.
    """
    view = copy.deepcopy(record)
    home = record.system_id
    for attr, owner in ATTRIBUTE_HOME_SYSTEM.items():
        if owner == home:
            continue
        if attr == "is_public_company":
            if "is_public_company" in view.metadata:
                view.metadata = {k: v for k, v in view.metadata.items()
                                 if k != "is_public_company"}
        else:
            setattr(view, attr, False)
    return view


def assert_no_cross_system_triggers(view: Record) -> None:
    """Hard validity check: a siloed view must carry no foreign trigger attribute.

    Raises AssertionError if a record's view still exposes an attribute whose
    home system differs from the record's own home system. Used as a gate before
    any siloed sweep so a leaking partition fails loudly instead of producing a
    misleadingly non-zero cross-domain recall.
    """
    home = view.system_id
    for attr, owner in ATTRIBUTE_HOME_SYSTEM.items():
        if owner == home:
            continue
        if _attr_value(view, attr):
            raise AssertionError(
                f"Siloed view of record {view.id!r} (home={home!r}) leaks foreign "
                f"attribute {attr!r} owned by {owner!r}; partition is invalid."
            )


def decompose_records(records: Dict[str, Record]) -> Dict[str, Record]:
    """Map a record dict to its siloed/decomposed equivalent (no mutation)."""
    return {rid: siloed_view(rec) for rid, rec in records.items()}
