"""
T-RKG Governance Module - Core Domain Knowledge

This module encodes expert knowledge about:
1. Regulatory requirements (SOX, GDPR, HIPAA, etc.)
2. Retention periods by jurisdiction and record type  
3. Conflict detection between competing obligations
4. Resolution guidance based on regulation priority
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Set, Optional, Any
from enum import Enum
from collections import defaultdict

from trkg.schema import Record, RecordType, Jurisdiction, Regulation, GovernanceState


class ConflictType(Enum):
    RETENTION_VS_DELETION = "RETENTION_VS_DELETION"
    HOLD_VS_DELETION = "HOLD_VS_DELETION"
    MULTI_RETENTION = "MULTI_RETENTION"
    JURISDICTION_CONFLICT = "JURISDICTION_CONFLICT"


class ConflictSeverity(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class RetentionRequirement:
    regulation: Regulation
    record_types: List[RecordType]
    retention_days: int
    jurisdictions: List[Jurisdiction]
    requires_pii: bool = False
    requires_phi: bool = False
    description: str = ""
    citation: str = ""


@dataclass
class DeletionRight:
    regulation: Regulation
    jurisdictions: List[Jurisdiction]
    requires_pii: bool = True
    description: str = ""
    citation: str = ""


@dataclass
class ConflictRule:
    regulation_a: Regulation
    regulation_b: Regulation
    conflict_type: ConflictType
    severity: ConflictSeverity
    description: str
    resolution_guidance: str


# Domain Knowledge: Retention Rules
RETENTION_RULES: List[RetentionRequirement] = [
    RetentionRequirement(
        regulation=Regulation.SOX,
        record_types=[RecordType.FINANCIAL, RecordType.AUDIT, RecordType.EMAIL],
        retention_days=7 * 365,
        jurisdictions=[Jurisdiction.US, Jurisdiction.US_CA, Jurisdiction.US_NY],
        description="SOX: Retain audit workpapers 7 years",
        citation="SOX Section 802"
    ),
    RetentionRequirement(
        regulation=Regulation.SEC,
        record_types=[RecordType.FINANCIAL, RecordType.EMAIL, RecordType.CHAT],
        retention_days=6 * 365,
        jurisdictions=[Jurisdiction.US, Jurisdiction.US_CA, Jurisdiction.US_NY],
        description="SEC Rule 17a-4: Broker-dealer records",
        citation="17 CFR 240.17a-4"
    ),
    RetentionRequirement(
        regulation=Regulation.HIPAA,
        record_types=[RecordType.MEDICAL],
        retention_days=6 * 365,
        jurisdictions=[Jurisdiction.US, Jurisdiction.US_CA, Jurisdiction.US_NY],
        requires_phi=True,
        description="HIPAA: Medical records 6 years",
        citation="45 CFR 164.530(j)"
    ),
    RetentionRequirement(
        regulation=Regulation.HGB,
        record_types=[RecordType.FINANCIAL, RecordType.INVOICE, RecordType.CONTRACT],
        retention_days=10 * 365,
        jurisdictions=[Jurisdiction.EU_DE],
        description="German Commercial Code: 10 years",
        citation="HGB §257"
    ),
    RetentionRequirement(
        regulation=Regulation.IRS,
        record_types=[RecordType.TAX, RecordType.FINANCIAL],
        retention_days=7 * 365,
        jurisdictions=[Jurisdiction.US, Jurisdiction.US_CA, Jurisdiction.US_NY],
        description="IRS: Tax records 7 years",
        citation="26 CFR 1.6001-1"
    ),
]

DELETION_RIGHTS: List[DeletionRight] = [
    DeletionRight(
        regulation=Regulation.GDPR,
        jurisdictions=[Jurisdiction.EU, Jurisdiction.EU_DE, Jurisdiction.EU_FR, Jurisdiction.UK],
        requires_pii=True,
        description="GDPR Art. 17: Right to erasure",
        citation="GDPR Art. 17"
    ),
    DeletionRight(
        regulation=Regulation.CPRA,
        jurisdictions=[Jurisdiction.US_CA],
        requires_pii=True,
        description="CPRA: Right to deletion",
        citation="Cal. Civ. Code §1798.105"
    ),
    DeletionRight(
        regulation=Regulation.PIPEDA,
        jurisdictions=[Jurisdiction.CA],
        requires_pii=True,
        description="PIPEDA: Right to challenge",
        citation="PIPEDA Principle 4.9"
    ),
]

JURISDICTION_REGULATIONS: Dict[Jurisdiction, List[Regulation]] = {
    Jurisdiction.US: [Regulation.SOX, Regulation.SEC, Regulation.HIPAA, Regulation.IRS],
    Jurisdiction.US_CA: [Regulation.SOX, Regulation.SEC, Regulation.HIPAA, Regulation.IRS, Regulation.CPRA],
    Jurisdiction.US_NY: [Regulation.SOX, Regulation.SEC, Regulation.HIPAA, Regulation.IRS],
    Jurisdiction.EU: [Regulation.GDPR],
    Jurisdiction.EU_DE: [Regulation.GDPR, Regulation.HGB],
    Jurisdiction.EU_FR: [Regulation.GDPR],
    Jurisdiction.UK: [Regulation.GDPR],
    Jurisdiction.CA: [Regulation.PIPEDA],
}

CONFLICT_RULES: List[ConflictRule] = [
    ConflictRule(
        regulation_a=Regulation.SOX,
        regulation_b=Regulation.GDPR,
        conflict_type=ConflictType.RETENTION_VS_DELETION,
        severity=ConflictSeverity.CRITICAL,
        description="SOX 7-year retention vs GDPR right to erasure",
        resolution_guidance="SOX takes precedence; document GDPR exemption"
    ),
    ConflictRule(
        regulation_a=Regulation.SEC,
        regulation_b=Regulation.GDPR,
        conflict_type=ConflictType.RETENTION_VS_DELETION,
        severity=ConflictSeverity.CRITICAL,
        description="SEC retention vs GDPR right to erasure",
        resolution_guidance="SEC takes precedence for regulated entities"
    ),
    ConflictRule(
        regulation_a=Regulation.HIPAA,
        regulation_b=Regulation.GDPR,
        conflict_type=ConflictType.RETENTION_VS_DELETION,
        severity=ConflictSeverity.CRITICAL,
        description="HIPAA retention vs GDPR erasure",
        resolution_guidance="HIPAA applies; GDPR Art. 17(3)(c) exemption"
    ),
    ConflictRule(
        regulation_a=Regulation.SOX,
        regulation_b=Regulation.CPRA,
        conflict_type=ConflictType.RETENTION_VS_DELETION,
        severity=ConflictSeverity.HIGH,
        description="SOX retention vs CPRA deletion",
        resolution_guidance="SOX takes precedence; CPRA has compliance exemption"
    ),
    ConflictRule(
        regulation_a=Regulation.SOX,
        regulation_b=Regulation.HGB,
        conflict_type=ConflictType.MULTI_RETENTION,
        severity=ConflictSeverity.MEDIUM,
        description="SOX 7yr vs HGB 10yr",
        resolution_guidance="Apply longest period (HGB 10 years)"
    ),
]


@dataclass
class GovernanceConflict:
    conflict_id: str
    record_id: str
    conflict_type: ConflictType
    severity: ConflictSeverity
    regulation_a: Regulation
    regulation_b: Regulation
    requirement_a: str
    requirement_b: str
    rule_a: str
    rule_b: str
    recommendation: str
    requires_legal_review: bool
    detected_at: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "record_id": self.record_id,
            "conflict_type": self.conflict_type.value,
            "severity": self.severity.value,
            "regulation_a": self.regulation_a.value,
            "regulation_b": self.regulation_b.value,
            "recommendation": self.recommendation,
            "requires_legal_review": self.requires_legal_review,
        }


class ConflictDetector:
    """Detects governance conflicts for records."""
    
    def __init__(self, store):
        self.store = store
        self._conflict_cache: Dict[str, List[GovernanceConflict]] = {}
    
    def get_applicable_regulations(self, record: Record) -> List[Regulation]:
        """
        Determine which regulations apply to a record.
        
        Implements cross-border regulation logic:
        1. Retention rules apply based on record jurisdiction + type
        2. Deletion rights (GDPR/CPRA) apply based on data subject location
        3. Financial regulations (SOX/SEC) apply to public company subsidiaries globally
        """
        applicable = []
        jurisdiction_regs = JURISDICTION_REGULATIONS.get(record.jurisdiction, [])
        
        # Check retention rules based on jurisdiction
        for reg in jurisdiction_regs:
            for rule in RETENTION_RULES:
                if rule.regulation == reg and record.type in rule.record_types:
                    if rule.requires_phi and not record.contains_phi:
                        continue
                    if reg not in applicable:
                        applicable.append(reg)
                    break
        
        # CROSS-BORDER: GDPR applies to EU citizen data globally
        if record.contains_pii:
            data_subject_location = record.metadata.get("data_subject_location", "")
            
            if data_subject_location == "EU" or record.jurisdiction in [
                Jurisdiction.EU, Jurisdiction.EU_DE, Jurisdiction.EU_FR, Jurisdiction.UK
            ]:
                if Regulation.GDPR not in applicable:
                    applicable.append(Regulation.GDPR)
            
            if data_subject_location in ["CA", "US_CA"] or record.jurisdiction == Jurisdiction.US_CA:
                if Regulation.CPRA not in applicable:
                    applicable.append(Regulation.CPRA)
        
        # CROSS-BORDER: SOX/SEC apply to public company records globally
        is_public_company = record.metadata.get("is_public_company", False)
        if is_public_company and record.type in [
            RecordType.FINANCIAL, RecordType.AUDIT, RecordType.TAX, 
            RecordType.INVOICE, RecordType.WORKPAPER
        ]:
            if Regulation.SOX not in applicable:
                applicable.append(Regulation.SOX)
        
        # Check jurisdiction-based deletion rights
        for right in DELETION_RIGHTS:
            if right.regulation in jurisdiction_regs and record.jurisdiction in right.jurisdictions:
                if right.requires_pii and not record.contains_pii:
                    continue
                if right.regulation not in applicable:
                    applicable.append(right.regulation)
        
        return applicable
    
    def detect_conflicts_for_record(self, record: Record) -> List[GovernanceConflict]:
        conflicts = []
        applicable_regs = self.get_applicable_regulations(record)
        
        for rule in CONFLICT_RULES:
            if rule.regulation_a in applicable_regs and rule.regulation_b in applicable_regs:
                conflict = GovernanceConflict(
                    conflict_id=f"conflict_{record.id}_{rule.regulation_a.value}_{rule.regulation_b.value}",
                    record_id=record.id,
                    conflict_type=rule.conflict_type,
                    severity=rule.severity,
                    regulation_a=rule.regulation_a,
                    regulation_b=rule.regulation_b,
                    requirement_a=f"{rule.regulation_a.value} requirement",
                    requirement_b=f"{rule.regulation_b.value} requirement",
                    rule_a=rule.regulation_a.value,
                    rule_b=rule.regulation_b.value,
                    recommendation=rule.resolution_guidance,
                    requires_legal_review=(rule.severity == ConflictSeverity.CRITICAL),
                    details={"record_type": record.type.value, "jurisdiction": record.jurisdiction.value}
                )
                conflicts.append(conflict)
        
        return conflicts
    
    def detect_all_conflicts(self) -> List[GovernanceConflict]:
        all_conflicts = []
        for record in self.store.records.values():
            conflicts = self.detect_conflicts_for_record(record)
            all_conflicts.extend(conflicts)
            self._conflict_cache[record.id] = conflicts
        return all_conflicts
    
    def get_conflict_summary(self) -> Dict[str, Any]:
        all_conflicts = self.detect_all_conflicts()
        
        by_type = defaultdict(int)
        by_severity = defaultdict(int)
        by_regulation_pair = defaultdict(int)
        affected_records = set()
        
        for conflict in all_conflicts:
            by_type[conflict.conflict_type.value] += 1
            by_severity[conflict.severity.value] += 1
            pair = f"{conflict.regulation_a.value} vs {conflict.regulation_b.value}"
            by_regulation_pair[pair] += 1
            affected_records.add(conflict.record_id)
        
        return {
            "total_conflicts": len(all_conflicts),
            "affected_records": len(affected_records),
            "by_type": dict(by_type),
            "by_severity": dict(by_severity),
            "by_regulation_pair": dict(by_regulation_pair),
            "critical_count": by_severity.get("CRITICAL", 0),
            "requires_legal_review": sum(1 for c in all_conflicts if c.requires_legal_review)
        }


class RetentionCalculator:
    """Calculate retention deadlines."""
    
    def __init__(self, store):
        self.store = store
    
    def calculate_retention_deadline(self, record: Record):
        applicable_rules = []
        max_retention_days = 0
        
        jurisdiction_regs = JURISDICTION_REGULATIONS.get(record.jurisdiction, [])
        
        for rule in RETENTION_RULES:
            if rule.regulation not in jurisdiction_regs:
                continue
            if record.type not in rule.record_types:
                continue
            if rule.requires_phi and not record.contains_phi:
                continue
            
            applicable_rules.append(f"{rule.regulation.value}: {rule.retention_days // 365}yr")
            if rule.retention_days > max_retention_days:
                max_retention_days = rule.retention_days
        
        if max_retention_days > 0:
            deadline = record.created + timedelta(days=max_retention_days)
            return deadline, applicable_rules
        
        return None, applicable_rules
