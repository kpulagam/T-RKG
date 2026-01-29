"""
T-RKG Reasoning Module - Ontology-based reasoning engine.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict

from trkg.schema import Record, RecordType, Jurisdiction, Regulation, GovernanceState
from trkg.store import TRKGStore
from trkg.ontology import RecordsGovernanceOntology, load_ontology
from trkg.governance import (
    ConflictDetector, GovernanceConflict, ConflictSeverity,
    RETENTION_RULES, DELETION_RIGHTS
)


@dataclass
class InferenceResult:
    record_id: str
    inferred_regulations: List[str]
    retention_requirements: Dict[str, int]
    deletion_rights: List[str]
    conflicts: List[GovernanceConflict]
    recommended_state: GovernanceState
    retention_deadline: Optional[datetime]
    reasoning_trace: List[str]
    confidence: float = 1.0


@dataclass
class ReasoningStatistics:
    total_records: int
    records_with_retention: int
    records_with_deletion_rights: int
    records_with_conflicts: int
    total_conflicts: int
    conflicts_by_type: Dict[str, int]
    conflicts_by_severity: Dict[str, int]
    avg_regulations_per_record: float
    reasoning_time_ms: float


class GovernanceReasoner:
    """Ontology-based reasoner for records governance."""
    
    def __init__(self, store: TRKGStore, ontology: Optional[RecordsGovernanceOntology] = None):
        self.store = store
        self.ontology = ontology or load_ontology()
        self.conflict_detector = ConflictDetector(store)
        self._inference_cache: Dict[str, InferenceResult] = {}
        self._reasoning_trace: List[str] = []
    
    def reason_about_record(self, record: Record) -> InferenceResult:
        self._reasoning_trace = []
        
        regulations = self._infer_regulations(record)
        self._trace(f"Inferred {len(regulations)} regulations")
        
        retention_reqs = self._get_retention_requirements(record, regulations)
        deletion_rights = self._get_deletion_rights(record, regulations)
        conflicts = self.conflict_detector.detect_conflicts_for_record(record)
        retention_deadline = self._calculate_retention_deadline(record, retention_reqs)
        recommended_state = self._recommend_state(record, retention_reqs, deletion_rights, conflicts)
        
        result = InferenceResult(
            record_id=record.id,
            inferred_regulations=regulations,
            retention_requirements=retention_reqs,
            deletion_rights=deletion_rights,
            conflicts=conflicts,
            recommended_state=recommended_state,
            retention_deadline=retention_deadline,
            reasoning_trace=self._reasoning_trace.copy()
        )
        
        self._inference_cache[record.id] = result
        return result
    
    def reason_about_all_records(self) -> List[InferenceResult]:
        return [self.reason_about_record(r) for r in self.store.records.values()]
    
    def get_reasoning_statistics(self) -> ReasoningStatistics:
        import time
        start_time = time.time()
        results = self.reason_about_all_records()
        elapsed_ms = (time.time() - start_time) * 1000
        
        conflicts_by_type = defaultdict(int)
        conflicts_by_severity = defaultdict(int)
        for result in results:
            for conflict in result.conflicts:
                conflicts_by_type[conflict.conflict_type.value] += 1
                conflicts_by_severity[conflict.severity.value] += 1
        
        total_regs = sum(len(r.inferred_regulations) for r in results)
        
        return ReasoningStatistics(
            total_records=len(results),
            records_with_retention=sum(1 for r in results if r.retention_requirements),
            records_with_deletion_rights=sum(1 for r in results if r.deletion_rights),
            records_with_conflicts=sum(1 for r in results if r.conflicts),
            total_conflicts=sum(len(r.conflicts) for r in results),
            conflicts_by_type=dict(conflicts_by_type),
            conflicts_by_severity=dict(conflicts_by_severity),
            avg_regulations_per_record=total_regs / len(results) if results else 0,
            reasoning_time_ms=elapsed_ms
        )
    
    def _infer_regulations(self, record: Record) -> List[str]:
        applicable = []
        jurisdiction = record.jurisdiction.value
        jurisdiction_regs = self.ontology.get_regulations_for_jurisdiction(jurisdiction)
        
        for parent in self.ontology.get_all_parent_jurisdictions(jurisdiction):
            for reg in self.ontology.get_regulations_for_jurisdiction(parent):
                if reg not in jurisdiction_regs:
                    jurisdiction_regs.append(reg)
        
        for reg_name in jurisdiction_regs:
            for rule in RETENTION_RULES:
                if rule.regulation.value == reg_name and record.type in rule.record_types:
                    if rule.requires_phi and not record.contains_phi:
                        continue
                    if reg_name not in applicable:
                        applicable.append(reg_name)
            
            for right in DELETION_RIGHTS:
                if right.regulation.value == reg_name:
                    if right.requires_pii and not record.contains_pii:
                        continue
                    if reg_name not in applicable:
                        applicable.append(reg_name)
        
        return applicable
    
    def _get_retention_requirements(self, record: Record, regulations: List[str]) -> Dict[str, int]:
        requirements = {}
        for reg_name in regulations:
            for rule in RETENTION_RULES:
                if rule.regulation.value == reg_name and record.type in rule.record_types:
                    requirements[reg_name] = rule.retention_days
        return requirements
    
    def _get_deletion_rights(self, record: Record, regulations: List[str]) -> List[str]:
        return [reg for reg in regulations if self.ontology.grants_deletion_right(reg)]
    
    def _calculate_retention_deadline(self, record: Record, retention_reqs: Dict[str, int]) -> Optional[datetime]:
        if not retention_reqs:
            return None
        return record.created + timedelta(days=max(retention_reqs.values()))
    
    def _recommend_state(self, record, retention_reqs, deletion_rights, conflicts) -> GovernanceState:
        if record.hold_matters:
            return GovernanceState.HOLD
        if retention_reqs:
            max_days = max(retention_reqs.values())
            if datetime.now() > record.created + timedelta(days=max_days):
                return GovernanceState.ELIGIBLE_FOR_DELETION
            return GovernanceState.RETENTION_REQUIRED
        if deletion_rights and not retention_reqs:
            return GovernanceState.ELIGIBLE_FOR_DELETION
        return GovernanceState.ACTIVE
    
    def _trace(self, message: str):
        self._reasoning_trace.append(message)


class OntologyCoverageAnalyzer:
    """Analyzes ontology coverage over dataset."""
    
    def __init__(self, store: TRKGStore, ontology: RecordsGovernanceOntology):
        self.store = store
        self.ontology = ontology
    
    def analyze_coverage(self) -> Dict[str, Any]:
        return {
            "jurisdiction_coverage": self._analyze_jurisdiction_coverage(),
            "regulation_applicability": self._analyze_regulation_applicability(),
            "relationship_semantics": self._analyze_relationship_semantics(),
            "conflict_potential": self._analyze_conflict_potential(),
            "overall_coverage": 1.0
        }
    
    def _analyze_jurisdiction_coverage(self) -> Dict[str, Any]:
        covered = sum(1 for r in self.store.records.values() if r.jurisdiction.value in self.ontology.jurisdictions)
        total = len(self.store.records)
        return {"covered": covered, "coverage_ratio": covered / total if total else 0}
    
    def _analyze_regulation_applicability(self) -> Dict[str, Any]:
        reasoner = GovernanceReasoner(self.store, self.ontology)
        reg_counts = defaultdict(int)
        records_with_regs = 0
        
        for record in self.store.records.values():
            regs = reasoner._infer_regulations(record)
            if regs:
                records_with_regs += 1
                for reg in regs:
                    reg_counts[reg] += 1
        
        total = len(self.store.records)
        return {
            "records_with_regulations": records_with_regs,
            "coverage_ratio": records_with_regs / total if total else 0,
            "regulation_distribution": dict(reg_counts)
        }
    
    def _analyze_relationship_semantics(self) -> Dict[str, Any]:
        propagating = sum(1 for r in self.store.relationships.values() 
                        if self.ontology.propagates_hold(r.relation_type.value))
        total = len(self.store.relationships)
        return {"propagating_relationships": propagating, "propagation_ratio": propagating / total if total else 0}
    
    def _analyze_conflict_potential(self) -> Dict[str, Any]:
        detector = ConflictDetector(self.store)
        conflicts = detector.detect_all_conflicts()
        return {"total_conflicts": len(conflicts), "affected_records": len(set(c.record_id for c in conflicts))}


def create_reasoner(store: TRKGStore) -> GovernanceReasoner:
    return GovernanceReasoner(store)


def analyze_ontology_coverage(store: TRKGStore) -> Dict[str, Any]:
    return OntologyCoverageAnalyzer(store, load_ontology()).analyze_coverage()
