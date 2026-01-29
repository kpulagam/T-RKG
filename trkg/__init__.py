"""
T-RKG: Temporal Records Knowledge Graph

A domain-specific knowledge graph framework for enterprise records governance.
"""

__version__ = "2.0.0"

from trkg.schema import (
    Record, Custodian, Matter, System, Relationship,
    CustodianAssignment, HoldAssignment,
    RecordType, RelationType, GovernanceState, Jurisdiction, Regulation,
    GovernanceDecision, AuditEvent, RetentionRule, HoldRule, DeletionRule,
)

from trkg.store import TRKGStore

from trkg.synthetic import (
    SyntheticDataGenerator, GeneratorConfig,
    generate_test_dataset, generate_minimal_dataset,
)

from trkg.governance import (
    ConflictDetector, GovernanceConflict, ConflictType, ConflictSeverity,
    RetentionCalculator, RETENTION_RULES, DELETION_RIGHTS,
    JURISDICTION_REGULATIONS, CONFLICT_RULES,
)

from trkg.ontology import (
    RecordsGovernanceOntology, load_ontology, get_ontology_statistics,
)

from trkg.reasoning import (
    GovernanceReasoner, InferenceResult, ReasoningStatistics,
    OntologyCoverageAnalyzer, create_reasoner, analyze_ontology_coverage,
)

__all__ = [
    "__version__",
    "Record", "Custodian", "Matter", "System", "Relationship",
    "CustodianAssignment", "HoldAssignment",
    "RecordType", "RelationType", "GovernanceState", "Jurisdiction", "Regulation",
    "GovernanceDecision", "AuditEvent", "RetentionRule", "HoldRule", "DeletionRule",
    "TRKGStore",
    "SyntheticDataGenerator", "GeneratorConfig",
    "generate_test_dataset", "generate_minimal_dataset",
    "ConflictDetector", "GovernanceConflict", "ConflictType", "ConflictSeverity",
    "RetentionCalculator", "RETENTION_RULES", "DELETION_RIGHTS",
    "JURISDICTION_REGULATIONS", "CONFLICT_RULES",
    "RecordsGovernanceOntology", "load_ontology", "get_ontology_statistics",
    "GovernanceReasoner", "InferenceResult", "ReasoningStatistics",
    "OntologyCoverageAnalyzer", "create_reasoner", "analyze_ontology_coverage",
]
