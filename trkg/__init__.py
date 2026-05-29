"""T-RKG: Temporal Records Knowledge Graph."""

from trkg.schema import (
    Record,
    Custodian,
    Matter,
    System,
    Relationship,
    CustodianAssignment,
    HoldAssignment,
    RecordType,
    RelationType,
    GovernanceState,
    Jurisdiction,
    Regulation,
    GovernanceDecision,
    AuditEvent,
    RetentionRule,
    HoldRule,
    DeletionRule,
    ConflictType,
    ConflictSeverity,
    RegulatoryConflict,
)

from trkg.store import TRKGStore

from trkg.synthetic import (
    SyntheticDataGenerator,
    GeneratorConfig,
    generate_test_dataset,
    generate_minimal_dataset,
)

from trkg.conflict import (
    ConflictDetector,
    ConflictDetectionResult,
    RegulationProfile,
    RegulatoryRequirement,
    SiloedConflictDetector,
    UntypedGraphConflictDetector,
    build_regulation_profiles,
    build_conflict_rules,
    get_ancestor_jurisdictions,
    JURISDICTION_HIERARCHY,
)

from trkg.composition import (
    siloed_view,
    decompose_records,
    assert_no_cross_system_triggers,
    ATTRIBUTE_HOME_SYSTEM,
)

__version__ = "1.0.0"

__all__ = [
    # Core entities
    'Record', 'Custodian', 'Matter', 'System',
    'Relationship', 'CustodianAssignment', 'HoldAssignment',
    # Enums
    'RecordType', 'RelationType', 'GovernanceState',
    'Jurisdiction', 'Regulation',
    'ConflictType', 'ConflictSeverity',
    # Governance
    'GovernanceDecision', 'AuditEvent',
    'RetentionRule', 'HoldRule', 'DeletionRule',
    'RegulatoryConflict',
    # Store
    'TRKGStore',
    # Conflict detection
    'ConflictDetector', 'ConflictDetectionResult',
    'RegulationProfile', 'RegulatoryRequirement',
    'SiloedConflictDetector', 'UntypedGraphConflictDetector',
    'build_regulation_profiles', 'build_conflict_rules',
    'get_ancestor_jurisdictions', 'JURISDICTION_HIERARCHY',
    # Cross-system composition partition
    'siloed_view', 'decompose_records',
    'assert_no_cross_system_triggers', 'ATTRIBUTE_HOME_SYSTEM',
    # Data generation
    'SyntheticDataGenerator', 'GeneratorConfig',
    'generate_test_dataset', 'generate_minimal_dataset',
]
