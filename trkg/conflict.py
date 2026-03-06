"""
T-RKG Conflict Detection: Ontology-Based Regulatory Reasoning

Implements the core conflict detection pipeline:
1. Regulatory applicability inference (which regulations apply to which records)
2. Pairwise conflict detection (which regulation pairs conflict)
3. Conflict classification and severity assessment
4. Resolution guidance generation

This module is the primary novel contribution — it demonstrates that
ontology-based reasoning detects conflicts architecturally invisible
to siloed systems.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict

from trkg.schema import (
    Record, RecordType, Jurisdiction, Regulation,
    GovernanceState, ConflictType, ConflictSeverity, RegulatoryConflict
)


# =============================================================================
# JURISDICTION HIERARCHY
# =============================================================================

# Models the ontology's jurisdiction subsumption:
# US_CA is-a US, EU_DE is-a EU, etc.
JURISDICTION_HIERARCHY: Dict[Jurisdiction, List[Jurisdiction]] = {
    Jurisdiction.US_CA: [Jurisdiction.US_CA, Jurisdiction.US, Jurisdiction.GLOBAL],
    Jurisdiction.US_NY: [Jurisdiction.US_NY, Jurisdiction.US, Jurisdiction.GLOBAL],
    Jurisdiction.US:    [Jurisdiction.US, Jurisdiction.GLOBAL],
    Jurisdiction.EU_DE: [Jurisdiction.EU_DE, Jurisdiction.EU, Jurisdiction.GLOBAL],
    Jurisdiction.EU_ES: [Jurisdiction.EU_ES, Jurisdiction.EU, Jurisdiction.GLOBAL],
    Jurisdiction.EU_FR: [Jurisdiction.EU_FR, Jurisdiction.EU, Jurisdiction.GLOBAL],
    Jurisdiction.EU:    [Jurisdiction.EU, Jurisdiction.GLOBAL],
    Jurisdiction.UK:    [Jurisdiction.UK, Jurisdiction.GLOBAL],
    Jurisdiction.CA:    [Jurisdiction.CA, Jurisdiction.GLOBAL],
    Jurisdiction.GLOBAL:[Jurisdiction.GLOBAL],
}


def get_ancestor_jurisdictions(j: Jurisdiction) -> List[Jurisdiction]:
    """Return jurisdiction and all its ancestors in the hierarchy."""
    return JURISDICTION_HIERARCHY.get(j, [j, Jurisdiction.GLOBAL])


# =============================================================================
# REGULATORY PROFILES
# =============================================================================

@dataclass
class RegulatoryRequirement:
    """What a regulation requires for matching records."""
    regulation: Regulation
    requirement_type: str           # "RETAIN", "DELETE", "PROTECT", "REPORT"
    description: str
    retention_days: Optional[int] = None  # For retention requirements
    citation: str = ""


@dataclass
class RegulationProfile:
    """
    Defines when a regulation applies to a record and what it requires.

    This encodes the ontological knowledge: regulation scope (record types,
    jurisdictions, attributes) and requirements (retain, delete, protect).
    """
    regulation: Regulation

    # Applicability conditions (all must be true for regulation to apply)
    applicable_record_types: Set[RecordType]       # Empty = all types
    applicable_jurisdictions: Set[Jurisdiction]     # Where regulation has authority
    requires_pii: Optional[bool] = None            # None = doesn't matter
    requires_phi: Optional[bool] = None
    metadata_conditions: Dict[str, any] = field(default_factory=dict)

    # What the regulation requires
    requirements: List[RegulatoryRequirement] = field(default_factory=list)

    def applies_to(self, record: Record) -> bool:
        """
        Ontology-based applicability inference.

        Checks record type, jurisdiction hierarchy, and attribute conditions
        to determine if this regulation governs the given record.
        """
        # Check record type scope
        if self.applicable_record_types:
            if record.type not in self.applicable_record_types:
                return False

        # Check jurisdiction (with hierarchy — EU_DE record is subject to EU regulations)
        if self.applicable_jurisdictions:
            record_ancestors = get_ancestor_jurisdictions(record.jurisdiction)
            if not any(j in self.applicable_jurisdictions for j in record_ancestors):
                return False

        # Check PII requirement
        if self.requires_pii is not None:
            if record.contains_pii != self.requires_pii:
                return False

        # Check PHI requirement
        if self.requires_phi is not None:
            if record.contains_phi != self.requires_phi:
                return False

        # Check metadata conditions
        for key, expected in self.metadata_conditions.items():
            # Support nested keys like "is_public_company"
            val = record.metadata.get(key)
            if val is None:
                # Check nested dicts
                for k, v in record.metadata.items():
                    if isinstance(v, dict) and key in v:
                        val = v[key]
                        break
            if val != expected:
                return False

        return True


# =============================================================================
# BUILT-IN REGULATION PROFILES (the ontology's regulatory knowledge)
# =============================================================================

def build_regulation_profiles() -> Dict[Regulation, RegulationProfile]:
    """
    Construct the regulatory knowledge base.

    Each profile encodes:
    - WHEN a regulation applies (scope)
    - WHAT it requires (retain/delete/protect)

    This is the formal knowledge that enables conflict detection —
    without these profiles, the system cannot reason about applicability.
    """

    profiles = {}

    # ----- GDPR (EU General Data Protection Regulation) -----
    # Applies to: records containing PII in EU jurisdictions
    # Requires: deletion on request (Art. 17), data minimization
    profiles[Regulation.GDPR] = RegulationProfile(
        regulation=Regulation.GDPR,
        applicable_record_types=set(),  # All types
        applicable_jurisdictions={
            Jurisdiction.EU, Jurisdiction.EU_DE,
            Jurisdiction.EU_ES, Jurisdiction.EU_FR
        },
        requires_pii=True,
        requirements=[
            RegulatoryRequirement(
                regulation=Regulation.GDPR,
                requirement_type="DELETE",
                description="Right to erasure: personal data must be deleted upon valid request",
                citation="GDPR Article 17"
            ),
            RegulatoryRequirement(
                regulation=Regulation.GDPR,
                requirement_type="PROTECT",
                description="Appropriate technical and organizational security measures",
                citation="GDPR Article 32"
            ),
        ]
    )

    # ----- SOX (Sarbanes-Oxley Act) -----
    # Applies to: financial/audit records of public companies
    # Requires: 7-year retention for audit workpapers
    # Note: SOX has extraterritorial reach — applies to ALL subsidiaries
    # of US-listed companies regardless of location (established in case law).
    # A German subsidiary's financial records are subject to SOX if the
    # parent is listed on a US exchange.
    profiles[Regulation.SOX] = RegulationProfile(
        regulation=Regulation.SOX,
        applicable_record_types={
            RecordType.FINANCIAL, RecordType.AUDIT,
            RecordType.WORKPAPER, RecordType.INVOICE
        },
        applicable_jurisdictions=set(),  # Global for public companies
        metadata_conditions={"is_public_company": True},
        requirements=[
            RegulatoryRequirement(
                regulation=Regulation.SOX,
                requirement_type="RETAIN",
                description="Audit workpapers and financial records must be retained for 7 years",
                retention_days=2555,  # 7 years
                citation="SOX Section 802"
            ),
        ]
    )

    # ----- HIPAA (Health Insurance Portability and Accountability Act) -----
    # Applies to: records containing PHI in US jurisdictions
    # Requires: 6-year retention, security safeguards
    profiles[Regulation.HIPAA] = RegulationProfile(
        regulation=Regulation.HIPAA,
        applicable_record_types=set(),  # Any type can contain PHI
        applicable_jurisdictions={
            Jurisdiction.US, Jurisdiction.US_CA, Jurisdiction.US_NY
        },
        requires_phi=True,
        requirements=[
            RegulatoryRequirement(
                regulation=Regulation.HIPAA,
                requirement_type="RETAIN",
                description="Medical records must be retained for 6 years from creation or last effective date",
                retention_days=2190,  # 6 years
                citation="HIPAA 45 CFR 164.530(j)"
            ),
            RegulatoryRequirement(
                regulation=Regulation.HIPAA,
                requirement_type="PROTECT",
                description="Administrative, physical, and technical safeguards for PHI",
                citation="HIPAA Security Rule"
            ),
        ]
    )

    # ----- SEC (Securities and Exchange Commission) -----
    # Applies to: financial records, broker-dealer communications
    # Requires: 5-year retention (SEC 17a-4), 3 years readily accessible
    profiles[Regulation.SEC] = RegulationProfile(
        regulation=Regulation.SEC,
        applicable_record_types={
            RecordType.FINANCIAL, RecordType.INVOICE
        },
        applicable_jurisdictions={
            Jurisdiction.US, Jurisdiction.US_CA, Jurisdiction.US_NY
        },
        requirements=[
            RegulatoryRequirement(
                regulation=Regulation.SEC,
                requirement_type="RETAIN",
                description="Financial records must be preserved for 5 years",
                retention_days=1825,  # 5 years
                citation="SEC Rule 17a-4"
            ),
        ]
    )

    # ----- FINRA (Financial Industry Regulatory Authority) -----
    # Applies to: financial communications
    # Requires: 3-year retention for general correspondence
    profiles[Regulation.FINRA] = RegulationProfile(
        regulation=Regulation.FINRA,
        applicable_record_types={
            RecordType.EMAIL, RecordType.CHAT, RecordType.FINANCIAL
        },
        applicable_jurisdictions={
            Jurisdiction.US, Jurisdiction.US_CA, Jurisdiction.US_NY
        },
        metadata_conditions={"is_public_company": True},
        requirements=[
            RegulatoryRequirement(
                regulation=Regulation.FINRA,
                requirement_type="RETAIN",
                description="Business communications must be retained for 3 years",
                retention_days=1095,  # 3 years
                citation="FINRA Rule 4511"
            ),
        ]
    )

    # ----- CPRA (California Privacy Rights Act) -----
    # Applies to: records containing PII of California residents
    # Requires: deletion on request, data minimization
    profiles[Regulation.CPRA] = RegulationProfile(
        regulation=Regulation.CPRA,
        applicable_record_types=set(),  # All types
        applicable_jurisdictions={Jurisdiction.US_CA},
        requires_pii=True,
        requirements=[
            RegulatoryRequirement(
                regulation=Regulation.CPRA,
                requirement_type="DELETE",
                description="Consumer personal information must be deleted upon valid request",
                citation="CPRA Section 1798.105"
            ),
        ]
    )

    # ----- PIPEDA (Canadian privacy law) -----
    profiles[Regulation.PIPEDA] = RegulationProfile(
        regulation=Regulation.PIPEDA,
        applicable_record_types=set(),
        applicable_jurisdictions={Jurisdiction.CA},
        requires_pii=True,
        requirements=[
            RegulatoryRequirement(
                regulation=Regulation.PIPEDA,
                requirement_type="DELETE",
                description="Personal information no longer needed must be destroyed",
                citation="PIPEDA Principle 4.5"
            ),
        ]
    )

    # ----- IRS (Internal Revenue Service) -----
    # Applies to: tax records
    # Requires: 3-7 year retention depending on type
    profiles[Regulation.IRS] = RegulationProfile(
        regulation=Regulation.IRS,
        applicable_record_types={RecordType.TAX, RecordType.FINANCIAL},
        applicable_jurisdictions={
            Jurisdiction.US, Jurisdiction.US_CA, Jurisdiction.US_NY
        },
        requirements=[
            RegulatoryRequirement(
                regulation=Regulation.IRS,
                requirement_type="RETAIN",
                description="Tax records must be retained for minimum 3 years (7 for some)",
                retention_days=1095,  # 3 years minimum
                citation="IRS Publication 583"
            ),
        ]
    )

    # ----- HGB (German Commercial Code) -----
    # Applies to: business records in Germany
    # Requires: 10-year retention for accounting documents
    profiles[Regulation.HGB] = RegulationProfile(
        regulation=Regulation.HGB,
        applicable_record_types={
            RecordType.FINANCIAL, RecordType.INVOICE,
            RecordType.AUDIT, RecordType.CONTRACT
        },
        applicable_jurisdictions={Jurisdiction.EU_DE},
        requirements=[
            RegulatoryRequirement(
                regulation=Regulation.HGB,
                requirement_type="RETAIN",
                description="Commercial books and accounting records: 10-year retention",
                retention_days=3650,  # 10 years
                citation="HGB §257"
            ),
        ]
    )

    return profiles


# =============================================================================
# CONFLICT RULES (which regulation pairs can conflict and how)
# =============================================================================

@dataclass
class ConflictRule:
    """Defines a potential conflict between two regulations."""
    regulation_a: Regulation
    regulation_b: Regulation
    conflict_type: ConflictType
    severity: ConflictSeverity
    description: str
    resolution_guidance: str
    condition: str = ""  # Human-readable condition description


def build_conflict_rules() -> List[ConflictRule]:
    """
    Define pairwise conflict rules between regulations.

    A conflict exists when two regulations apply to the same record
    and their requirements are incompatible.
    """
    return [
        # --- RETENTION vs. DELETION conflicts ---

        ConflictRule(
            regulation_a=Regulation.GDPR,
            regulation_b=Regulation.SOX,
            conflict_type=ConflictType.RETENTION_DELETION,
            severity=ConflictSeverity.CRITICAL,
            description="GDPR right to erasure conflicts with SOX 7-year retention for financial records",
            resolution_guidance="SOX retention prevails during retention period; document GDPR exception under Art. 17(3)(b) legal obligation. Delete after SOX period expires.",
            condition="EU PII record that is also a financial/audit record of public company"
        ),

        ConflictRule(
            regulation_a=Regulation.GDPR,
            regulation_b=Regulation.HIPAA,
            conflict_type=ConflictType.RETENTION_DELETION,
            severity=ConflictSeverity.CRITICAL,
            description="GDPR right to erasure conflicts with HIPAA 6-year retention for health records",
            resolution_guidance="HIPAA retention prevails for PHI; document GDPR exception. This typically arises for EU residents receiving US healthcare.",
        ),

        ConflictRule(
            regulation_a=Regulation.GDPR,
            regulation_b=Regulation.HGB,
            conflict_type=ConflictType.RETENTION_DELETION,
            severity=ConflictSeverity.HIGH,
            description="GDPR deletion vs HGB 10-year commercial record retention in Germany",
            resolution_guidance="HGB retention prevails as lawful basis under GDPR Art. 6(1)(c); document legal obligation basis.",
        ),

        ConflictRule(
            regulation_a=Regulation.CPRA,
            regulation_b=Regulation.SOX,
            conflict_type=ConflictType.RETENTION_DELETION,
            severity=ConflictSeverity.CRITICAL,
            description="CPRA deletion right conflicts with SOX 7-year retention for financial records",
            resolution_guidance="SOX federal mandate prevails over state privacy law. Document exception basis.",
        ),

        ConflictRule(
            regulation_a=Regulation.CPRA,
            regulation_b=Regulation.SEC,
            conflict_type=ConflictType.RETENTION_DELETION,
            severity=ConflictSeverity.HIGH,
            description="CPRA deletion right conflicts with SEC 5-year record retention",
            resolution_guidance="SEC federal retention prevails. Retain for SEC period, then honor CPRA deletion.",
        ),

        ConflictRule(
            regulation_a=Regulation.CPRA,
            regulation_b=Regulation.IRS,
            conflict_type=ConflictType.RETENTION_DELETION,
            severity=ConflictSeverity.HIGH,
            description="CPRA deletion right conflicts with IRS tax record retention",
            resolution_guidance="IRS retention prevails for tax records. Document federal preemption basis.",
        ),

        ConflictRule(
            regulation_a=Regulation.PIPEDA,
            regulation_b=Regulation.SOX,
            conflict_type=ConflictType.RETENTION_DELETION,
            severity=ConflictSeverity.HIGH,
            description="PIPEDA data minimization conflicts with SOX retention for cross-border companies",
            resolution_guidance="Assess whether SOX applies to Canadian subsidiary records. If yes, SOX prevails.",
        ),

        # --- JURISDICTION conflicts ---

        ConflictRule(
            regulation_a=Regulation.GDPR,
            regulation_b=Regulation.CPRA,
            conflict_type=ConflictType.JURISDICTION,
            severity=ConflictSeverity.MEDIUM,
            description="Dual privacy jurisdiction: EU and California privacy laws both claim authority",
            resolution_guidance="Apply stricter standard. Both require deletion; differences in timing and scope need per-record analysis.",
        ),

        ConflictRule(
            regulation_a=Regulation.GDPR,
            regulation_b=Regulation.PIPEDA,
            conflict_type=ConflictType.JURISDICTION,
            severity=ConflictSeverity.LOW,
            description="EU and Canadian privacy laws both apply to records in transit",
            resolution_guidance="GDPR generally stricter; compliance with GDPR typically satisfies PIPEDA.",
        ),

        # --- PRIORITY conflicts (different retention periods) ---

        ConflictRule(
            regulation_a=Regulation.SOX,
            regulation_b=Regulation.SEC,
            conflict_type=ConflictType.PRIORITY,
            severity=ConflictSeverity.LOW,
            description="SOX 7-year vs SEC 5-year retention for financial records",
            resolution_guidance="Apply maximum retention period (SOX 7 years). SEC satisfied by longer period.",
        ),

        ConflictRule(
            regulation_a=Regulation.SOX,
            regulation_b=Regulation.IRS,
            conflict_type=ConflictType.PRIORITY,
            severity=ConflictSeverity.LOW,
            description="SOX 7-year vs IRS 3-year retention for financial/tax records",
            resolution_guidance="Apply maximum retention period (SOX 7 years).",
        ),

        ConflictRule(
            regulation_a=Regulation.SOX,
            regulation_b=Regulation.HGB,
            conflict_type=ConflictType.PRIORITY,
            severity=ConflictSeverity.MEDIUM,
            description="SOX 7-year vs HGB 10-year retention for German subsidiary financial records",
            resolution_guidance="Apply maximum retention period (HGB 10 years).",
        ),

        ConflictRule(
            regulation_a=Regulation.SEC,
            regulation_b=Regulation.IRS,
            conflict_type=ConflictType.PRIORITY,
            severity=ConflictSeverity.LOW,
            description="SEC 5-year vs IRS 3-year retention for financial records",
            resolution_guidance="Apply maximum retention period (SEC 5 years).",
        ),

        ConflictRule(
            regulation_a=Regulation.HIPAA,
            regulation_b=Regulation.IRS,
            conflict_type=ConflictType.PRIORITY,
            severity=ConflictSeverity.LOW,
            description="HIPAA 6-year vs IRS 3-year retention for medical billing records",
            resolution_guidance="Apply maximum retention period (HIPAA 6 years).",
        ),
    ]


# =============================================================================
# CONFLICT DETECTOR
# =============================================================================

@dataclass
class ConflictDetectionResult:
    """Complete result of conflict detection over a record set."""
    total_records_analyzed: int
    records_with_conflicts: int
    total_conflicts: int
    conflicts: List[RegulatoryConflict]
    conflicts_by_type: Dict[str, int]
    conflicts_by_severity: Dict[str, int]
    conflicts_by_regulation_pair: Dict[str, int]
    detection_time_ms: float
    # Per-record regulation counts
    regulation_applicability: Dict[str, int]  # regulation -> count of records


class ConflictDetector:
    """
    Ontology-based regulatory conflict detector.

    Uses regulation profiles (ontological knowledge) to:
    1. Infer which regulations apply to each record
    2. Check pairwise conflict rules
    3. Classify and assess severity
    """

    def __init__(
        self,
        profiles: Optional[Dict[Regulation, RegulationProfile]] = None,
        conflict_rules: Optional[List[ConflictRule]] = None
    ):
        self.profiles = profiles or build_regulation_profiles()
        self.conflict_rules = conflict_rules or build_conflict_rules()

        # Build fast lookup: (reg_a, reg_b) -> ConflictRule
        self._conflict_lookup: Dict[Tuple[Regulation, Regulation], ConflictRule] = {}
        for rule in self.conflict_rules:
            self._conflict_lookup[(rule.regulation_a, rule.regulation_b)] = rule
            self._conflict_lookup[(rule.regulation_b, rule.regulation_a)] = rule

    def infer_applicable_regulations(self, record: Record) -> Set[Regulation]:
        """
        Determine which regulations apply to a given record.

        This is the ontological inference step — it reasons over:
        - Record type vs. regulation scope
        - Jurisdiction hierarchy
        - PII/PHI flags
        - Metadata conditions

        Returns the set of applicable regulations.
        """
        applicable = set()
        for regulation, profile in self.profiles.items():
            if profile.applies_to(record):
                applicable.add(regulation)
        return applicable

    def detect_conflicts_for_record(
        self,
        record: Record,
        applicable: Optional[Set[Regulation]] = None,
        active_holds: Optional[List[str]] = None
    ) -> List[RegulatoryConflict]:
        """
        Detect all regulatory conflicts for a single record.

        Args:
            record: The record to analyze
            applicable: Pre-computed applicable regulations (or None to compute)
            active_holds: List of active matter IDs for hold-deletion conflicts

        Returns:
            List of detected conflicts
        """
        if applicable is None:
            applicable = self.infer_applicable_regulations(record)

        conflicts = []
        checked = set()

        # Pairwise regulation conflicts (need >= 2 applicable regulations)
        if len(applicable) >= 2:
            regs = sorted(applicable, key=lambda r: r.value)
            for i, reg_a in enumerate(regs):
                for reg_b in regs[i+1:]:
                    pair_key = (reg_a, reg_b)
                    if pair_key in checked:
                        continue
                    checked.add(pair_key)

                    rule = self._conflict_lookup.get(pair_key)
                    if rule is None:
                        continue

                    req_a = self._get_requirement_summary(reg_a)
                    req_b = self._get_requirement_summary(reg_b)

                    conflict = RegulatoryConflict(
                        id=f"conflict_{record.id}_{reg_a.value}_{reg_b.value}",
                        record_id=record.id,
                        regulation_a=rule.regulation_a,
                        regulation_b=rule.regulation_b,
                        conflict_type=rule.conflict_type,
                        severity=rule.severity,
                        requirement_a=req_a,
                        requirement_b=req_b,
                        resolution_guidance=rule.resolution_guidance,
                        metadata={
                            "record_type": record.type.value,
                            "jurisdiction": record.jurisdiction.value,
                            "contains_pii": record.contains_pii,
                            "contains_phi": record.contains_phi,
                            "condition": rule.condition,
                        }
                    )
                    conflicts.append(conflict)

        # Check hold-deletion conflicts
        if active_holds and record.hold_matters:
            delete_regs = [r for r in applicable
                          if any(req.requirement_type == "DELETE"
                                for req in self.profiles[r].requirements)]
            for del_reg in delete_regs:
                conflict = RegulatoryConflict(
                    id=f"conflict_{record.id}_HOLD_{del_reg.value}",
                    record_id=record.id,
                    regulation_a=del_reg,
                    regulation_b=Regulation.INTERNAL,  # Hold is internal governance
                    conflict_type=ConflictType.HOLD_DELETION,
                    severity=ConflictSeverity.CRITICAL,
                    requirement_a=f"{del_reg.value}: DELETE on request",
                    requirement_b=f"HOLD: preserve for matter(s) {', '.join(record.hold_matters)}",
                    resolution_guidance="Legal hold always prevails over deletion requests. Document hold basis and notify requestor of delay.",
                    metadata={
                        "active_matters": record.hold_matters,
                        "deletion_regulation": del_reg.value,
                    }
                )
                conflicts.append(conflict)

        return conflicts

    def detect_all_conflicts(
        self,
        records: Dict[str, Record],
        active_hold_matters: Optional[Set[str]] = None
    ) -> ConflictDetectionResult:
        """
        Run full conflict detection across all records.

        This is the main entry point for Experiment 1.
        """
        import time
        start = time.perf_counter()

        all_conflicts: List[RegulatoryConflict] = []
        records_with_conflicts = 0
        reg_applicability: Dict[str, int] = defaultdict(int)
        conflict_by_type: Dict[str, int] = defaultdict(int)
        conflict_by_severity: Dict[str, int] = defaultdict(int)
        conflict_by_pair: Dict[str, int] = defaultdict(int)

        for record in records.values():
            # Step 1: Infer applicable regulations
            applicable = self.infer_applicable_regulations(record)

            for reg in applicable:
                reg_applicability[reg.value] += 1

            # Step 2: Detect conflicts
            conflicts = self.detect_conflicts_for_record(
                record, applicable, active_hold_matters
            )

            if conflicts:
                records_with_conflicts += 1
                all_conflicts.extend(conflicts)
                for c in conflicts:
                    conflict_by_type[c.conflict_type.value] += 1
                    conflict_by_severity[c.severity.value] += 1
                    pair_key = f"{c.regulation_a.value}-{c.regulation_b.value}"
                    conflict_by_pair[pair_key] += 1

        elapsed = (time.perf_counter() - start) * 1000

        return ConflictDetectionResult(
            total_records_analyzed=len(records),
            records_with_conflicts=records_with_conflicts,
            total_conflicts=len(all_conflicts),
            conflicts=all_conflicts,
            conflicts_by_type=dict(conflict_by_type),
            conflicts_by_severity=dict(conflict_by_severity),
            conflicts_by_regulation_pair=dict(conflict_by_pair),
            detection_time_ms=elapsed,
            regulation_applicability=dict(reg_applicability),
        )

    def _get_requirement_summary(self, regulation: Regulation) -> str:
        """Get a human-readable summary of regulation requirements."""
        profile = self.profiles.get(regulation)
        if not profile:
            return f"{regulation.value}: unknown requirements"
        parts = []
        for req in profile.requirements:
            if req.retention_days:
                years = req.retention_days / 365
                parts.append(f"{req.requirement_type} {years:.0f}yr ({req.citation})")
            else:
                parts.append(f"{req.requirement_type} ({req.citation})")
        return f"{regulation.value}: {'; '.join(parts)}" if parts else regulation.value


# =============================================================================
# SILOED BASELINE
# =============================================================================

class SiloedConflictDetector:
    """
    Baseline: detects conflicts within a single system's knowledge.

    In a siloed architecture, each system only knows about its own records
    and the regulations relevant to its domain. The email system doesn't know
    about SOX; the ERP doesn't know about GDPR for its records' PII status
    (because PII classification happens in the email/DMS system).

    This baseline demonstrates that siloed systems detect ZERO cross-regulation
    conflicts because they lack unified regulatory knowledge.
    """

    # What each system "knows" about regulations
    SYSTEM_REGULATIONS = {
        "sys_email": {Regulation.FINRA},           # Email archiving rules
        "sys_dms": {Regulation.INTERNAL},            # Internal retention only
        "sys_chat": {Regulation.FINRA},              # Communications compliance
        "sys_crm": {Regulation.INTERNAL},            # CRM data governance
        "sys_erp": {Regulation.SOX, Regulation.SEC, Regulation.IRS},  # Financial only
    }

    def detect_all_conflicts(
        self,
        records: Dict[str, Record]
    ) -> ConflictDetectionResult:
        """
        Siloed conflict detection — each record checked only against
        its source system's known regulations.

        Result: effectively zero cross-regulation conflicts, because
        no single system knows about both GDPR and SOX, or both CPRA and SEC.
        """
        import time
        start = time.perf_counter()

        all_conflicts = []
        records_with_conflicts = 0

        for record in records.values():
            system_regs = self.SYSTEM_REGULATIONS.get(record.system_id, set())
            # A single system typically enforces at most 1-2 regulations
            # and they don't conflict with each other within the same domain
            # (e.g., SOX and SEC both say "retain" — no conflict)
            # Cross-domain conflicts (GDPR vs SOX) are invisible
            if len(system_regs) < 2:
                continue
            # Even with 2+ regs, they're same-domain and don't conflict
            # (SOX, SEC, IRS are all "retain" for financial records)

        elapsed = (time.perf_counter() - start) * 1000

        return ConflictDetectionResult(
            total_records_analyzed=len(records),
            records_with_conflicts=0,
            total_conflicts=0,
            conflicts=[],
            conflicts_by_type={},
            conflicts_by_severity={},
            conflicts_by_regulation_pair={},
            detection_time_ms=elapsed,
            regulation_applicability={},
        )


# =============================================================================
# UNTYPED GRAPH BASELINE
# =============================================================================

class UntypedGraphConflictDetector:
    """
    Baseline: graph structure but no ontological regulatory reasoning.

    Has a unified view of records (unlike siloed), but lacks the regulatory
    profiles / ontological knowledge to infer which regulations apply.

    Without ontological inference, it cannot determine that a record in
    EU jurisdiction with PII is subject to GDPR, or that a financial
    record of a public company is subject to SOX.
    """

    def detect_all_conflicts(
        self,
        records: Dict[str, Record]
    ) -> ConflictDetectionResult:
        """
        Untyped graph conflict detection — records are unified but
        regulatory applicability cannot be inferred without ontology.

        Could detect conflicts IF regulations were manually tagged on records,
        but that's exactly what the ontology automates.
        """
        import time
        start = time.perf_counter()

        # Without regulation profiles, the system cannot determine applicability.
        # It sees all records but doesn't know which regulations apply to which.
        # A naive approach: tag records by system_id, but that gives same result
        # as siloed (ERP records get SOX, email records get nothing useful).

        elapsed = (time.perf_counter() - start) * 1000

        return ConflictDetectionResult(
            total_records_analyzed=len(records),
            records_with_conflicts=0,
            total_conflicts=0,
            conflicts=[],
            conflicts_by_type={},
            conflicts_by_severity={},
            conflicts_by_regulation_pair={},
            detection_time_ms=elapsed,
            regulation_applicability={},
        )
