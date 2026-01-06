"""
T-RKG: Temporal Records Knowledge Graph

A graph-based approach to enterprise records governance with bitemporal modeling,
relationship-aware hold propagation, and multi-jurisdictional compliance.
"""

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
    DeletionRule
)

from trkg.store import TRKGStore

from trkg.synthetic import (
    SyntheticDataGenerator,
    GeneratorConfig,
    generate_test_dataset,
    generate_minimal_dataset
)

__version__ = "1.0.0"

__all__ = [
    # Core entities
    'Record',
    'Custodian',
    'Matter', 
    'System',
    'Relationship',
    'CustodianAssignment',
    'HoldAssignment',
    
    # Enums
    'RecordType',
    'RelationType',
    'GovernanceState',
    'Jurisdiction',
    'Regulation',
    
    # Governance
    'GovernanceDecision',
    'AuditEvent',
    'RetentionRule',
    'HoldRule',
    'DeletionRule',
    
    # Store
    'TRKGStore',
    
    # Data generation
    'SyntheticDataGenerator',
    'GeneratorConfig',
    'generate_test_dataset',
    'generate_minimal_dataset',
]
