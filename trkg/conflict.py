"""
Ontology-based regulatory conflict detection: applicability inference,
pairwise conflict checking, severity classification, and resolution guidance.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict

from trkg.schema import (
    Record, RecordType, Jurisdiction, Regulation, Matter,
    GovernanceState, ConflictType, ConflictSeverity, RegulatoryConflict
)


# =============================================================================
# JURISDICTION HIERARCHY
# =============================================================================

# Jurisdiction subsumption (US_CA is-a US, EU_DE is-a EU, etc.).
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
    """Scope (record types, jurisdictions, attributes) and requirements for a regulation."""
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
        """Return True if this regulation governs the given record."""
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
    """Return the built-in regulation profiles."""

    profiles = {}

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

    # SOX reaches subsidiaries of US-listed companies regardless of location,
    # so applicable_jurisdictions is intentionally empty and applicability is
    # gated on is_public_company.
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
    """Return pairwise conflict rules between regulations."""
    return [
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
    """Ontology-based regulatory conflict detector."""

    def __init__(
        self,
        profiles: Optional[Dict[Regulation, RegulationProfile]] = None,
        conflict_rules: Optional[List[ConflictRule]] = None,
        matters: Optional[Dict[str, "Matter"]] = None,
    ):
        self.profiles = profiles or build_regulation_profiles()
        self.conflict_rules = conflict_rules or build_conflict_rules()
        # Optional matter lookup enables GDPR Art. 17(3) exemption suppression
        # on Hold-Deletion conflicts. If absent, no suppression is applied.
        self.matters: Dict[str, "Matter"] = matters or {}
        # Suppressions during the most recent detect_all_conflicts call.
        self.suppressed_exemption_count: int = 0

        # Build fast lookup: (reg_a, reg_b) -> ConflictRule
        self._conflict_lookup: Dict[Tuple[Regulation, Regulation], ConflictRule] = {}
        for rule in self.conflict_rules:
            self._conflict_lookup[(rule.regulation_a, rule.regulation_b)] = rule
            self._conflict_lookup[(rule.regulation_b, rule.regulation_a)] = rule

    def _exemption_holds(self, record: "Record", del_reg: Regulation) -> bool:
        """Return True if a GDPR Art. 17(3) exemption suppresses this conflict.

        Triggers only when the deletion regulation is GDPR and one of the
        matters holding the record carries an active legal_obligation_flag
        (Art. 17(3)(b)) or legal_claim_flag (Art. 17(3)(e)).
        """
        if del_reg != Regulation.GDPR:
            return False
        if not self.matters or not record.hold_matters:
            return False
        for matter_id in record.hold_matters:
            m = self.matters.get(matter_id)
            if m is None:
                continue
            if m.legal_obligation_flag or m.legal_claim_flag:
                return True
        return False

    def infer_applicable_regulations(self, record: Record) -> Set[Regulation]:
        """Return the set of regulations whose profile matches the record."""
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
        """Detect all regulatory conflicts for a single record."""
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
                # GDPR Art. 17(3) exemption: a matter holding the record with
                # a legal_obligation or legal_claim basis lawfully suspends
                # the erasure right, so no conflict is emitted.
                if self._exemption_holds(record, del_reg):
                    self.suppressed_exemption_count += 1
                    continue
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
        """Run conflict detection over all records."""
        import time
        start = time.perf_counter()

        self.suppressed_exemption_count = 0

        all_conflicts: List[RegulatoryConflict] = []
        records_with_conflicts = 0
        reg_applicability: Dict[str, int] = defaultdict(int)
        conflict_by_type: Dict[str, int] = defaultdict(int)
        conflict_by_severity: Dict[str, int] = defaultdict(int)
        conflict_by_pair: Dict[str, int] = defaultdict(int)

        for record in records.values():
            applicable = self.infer_applicable_regulations(record)

            for reg in applicable:
                reg_applicability[reg.value] += 1

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
    """Baseline: per-system conflict detection without cross-system knowledge.

    Each source system runs an independent conflict pass restricted to the
    regulation set it would normally enforce. The 0-conflict outcome is an
    empirical observation, not an assumption: pairwise rules within each
    system's intra-domain regulation set simply never fire.
    """

    SYSTEM_REGULATIONS = {
        "sys_email": {Regulation.FINRA},
        "sys_dms":   {Regulation.INTERNAL},
        "sys_chat":  {Regulation.FINRA},
        "sys_crm":   {Regulation.INTERNAL},
        "sys_erp":   {Regulation.SOX, Regulation.SEC, Regulation.IRS},
    }

    def __init__(
        self,
        profiles: Optional[Dict[Regulation, "RegulationProfile"]] = None,
        conflict_rules: Optional[List["ConflictRule"]] = None,
    ):
        self.profiles = profiles or build_regulation_profiles()
        self.conflict_rules = conflict_rules or build_conflict_rules()
        self._conflict_lookup: Dict[Tuple[Regulation, Regulation], "ConflictRule"] = {}
        for rule in self.conflict_rules:
            self._conflict_lookup[(rule.regulation_a, rule.regulation_b)] = rule
            self._conflict_lookup[(rule.regulation_b, rule.regulation_a)] = rule

    def detect_all_conflicts(
        self,
        records: Dict[str, Record],
    ) -> ConflictDetectionResult:
        import time
        start = time.perf_counter()

        all_conflicts: List[RegulatoryConflict] = []
        records_with_conflicts = 0
        reg_applicability: Dict[str, int] = defaultdict(int)
        conflict_by_type: Dict[str, int] = defaultdict(int)
        conflict_by_severity: Dict[str, int] = defaultdict(int)
        conflict_by_pair: Dict[str, int] = defaultdict(int)

        for record in records.values():
            allowed = self.SYSTEM_REGULATIONS.get(record.system_id, set())
            if not allowed:
                continue

            applicable: Set[Regulation] = set()
            for reg in allowed:
                profile = self.profiles.get(reg)
                if profile is not None and profile.applies_to(record):
                    applicable.add(reg)
                    reg_applicability[reg.value] += 1

            if len(applicable) < 2:
                continue

            regs = sorted(applicable, key=lambda r: r.value)
            local_hits = []
            for i, reg_a in enumerate(regs):
                for reg_b in regs[i + 1:]:
                    rule = self._conflict_lookup.get((reg_a, reg_b))
                    if rule is None:
                        continue
                    conflict = RegulatoryConflict(
                        id=f"siloed_{record.id}_{reg_a.value}_{reg_b.value}",
                        record_id=record.id,
                        regulation_a=rule.regulation_a,
                        regulation_b=rule.regulation_b,
                        conflict_type=rule.conflict_type,
                        severity=rule.severity,
                        resolution_guidance=rule.resolution_guidance,
                    )
                    local_hits.append(conflict)
                    conflict_by_type[rule.conflict_type.value] += 1
                    conflict_by_severity[rule.severity.value] += 1
                    conflict_by_pair[f"{reg_a.value}-{reg_b.value}"] += 1

            if local_hits:
                records_with_conflicts += 1
                all_conflicts.extend(local_hits)

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


# =============================================================================
# UNTYPED GRAPH BASELINE
# =============================================================================

class UntypedGraphConflictDetector:
    """Baseline: unified record graph with naive regulation tagging from
    record_type and system_id only -- no jurisdiction subsumption, PII/PHI
    flags, or metadata conditions. The per-record applicable set rarely
    exceeds one, so pairwise rules typically do not fire.
    """

    SYSTEM_DEFAULT_REGULATIONS = {
        "sys_email": {Regulation.FINRA},
        "sys_chat":  {Regulation.FINRA},
        "sys_dms":   {Regulation.INTERNAL},
        "sys_crm":   {Regulation.INTERNAL},
        "sys_erp":   {Regulation.SOX, Regulation.SEC, Regulation.IRS},
    }
    TYPE_DEFAULT_REGULATIONS = {
        RecordType.FINANCIAL: {Regulation.SOX, Regulation.SEC},
        RecordType.AUDIT:     {Regulation.SOX},
        RecordType.WORKPAPER: {Regulation.SOX},
        RecordType.INVOICE:   {Regulation.SEC, Regulation.IRS},
        RecordType.TAX:       {Regulation.IRS},
        RecordType.MEDICAL:   {Regulation.HIPAA},
    }

    def __init__(
        self,
        conflict_rules: Optional[List["ConflictRule"]] = None,
    ):
        self.conflict_rules = conflict_rules or build_conflict_rules()
        self._conflict_lookup: Dict[Tuple[Regulation, Regulation], "ConflictRule"] = {}
        for rule in self.conflict_rules:
            self._conflict_lookup[(rule.regulation_a, rule.regulation_b)] = rule
            self._conflict_lookup[(rule.regulation_b, rule.regulation_a)] = rule

    def _naive_applicable(self, record: Record) -> Set[Regulation]:
        # Tagging depends only on system_id and record type, so the
        # generator's fixed allocation of 500 financial records per seed
        # produces a constant 1500-conflict count at 10K (3 SOX/SEC/IRS
        # priority pairs per financial record).
        regs: Set[Regulation] = set()
        regs |= self.SYSTEM_DEFAULT_REGULATIONS.get(record.system_id, set())
        regs |= self.TYPE_DEFAULT_REGULATIONS.get(record.type, set())
        return regs

    def detect_all_conflicts(
        self,
        records: Dict[str, Record],
    ) -> ConflictDetectionResult:
        import time
        start = time.perf_counter()

        all_conflicts: List[RegulatoryConflict] = []
        records_with_conflicts = 0
        reg_applicability: Dict[str, int] = defaultdict(int)
        conflict_by_type: Dict[str, int] = defaultdict(int)
        conflict_by_severity: Dict[str, int] = defaultdict(int)
        conflict_by_pair: Dict[str, int] = defaultdict(int)

        for record in records.values():
            applicable = self._naive_applicable(record)
            for reg in applicable:
                reg_applicability[reg.value] += 1
            if len(applicable) < 2:
                continue

            regs = sorted(applicable, key=lambda r: r.value)
            local_hits = []
            for i, reg_a in enumerate(regs):
                for reg_b in regs[i + 1:]:
                    rule = self._conflict_lookup.get((reg_a, reg_b))
                    if rule is None:
                        continue
                    conflict = RegulatoryConflict(
                        id=f"untyped_{record.id}_{reg_a.value}_{reg_b.value}",
                        record_id=record.id,
                        regulation_a=rule.regulation_a,
                        regulation_b=rule.regulation_b,
                        conflict_type=rule.conflict_type,
                        severity=rule.severity,
                        resolution_guidance=rule.resolution_guidance,
                    )
                    local_hits.append(conflict)
                    conflict_by_type[rule.conflict_type.value] += 1
                    conflict_by_severity[rule.severity.value] += 1
                    conflict_by_pair[f"{reg_a.value}-{reg_b.value}"] += 1

            if local_hits:
                records_with_conflicts += 1
                all_conflicts.extend(local_hits)

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
