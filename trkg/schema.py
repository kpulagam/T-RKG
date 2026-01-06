"""
T-RKG Schema: Temporal Records Knowledge Graph

Defines the core entity types, relationship types, and governance states
for enterprise records management.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List, Any, Set


# =============================================================================
# ENUMERATIONS
# =============================================================================

class RecordType(Enum):
    """Categories of records in enterprise systems."""
    EMAIL = "EMAIL"
    DOCUMENT = "DOCUMENT"
    CHAT = "CHAT"
    ATTACHMENT = "ATTACHMENT"
    SPREADSHEET = "SPREADSHEET"
    PRESENTATION = "PRESENTATION"
    CONTRACT = "CONTRACT"
    INVOICE = "INVOICE"
    MEDICAL = "MEDICAL"
    FINANCIAL = "FINANCIAL"
    TAX = "TAX"
    AUDIT = "AUDIT"
    WORKPAPER = "WORKPAPER"
    LOG = "LOG"
    TICKET = "TICKET"
    OTHER = "OTHER"


class RelationType(Enum):
    """Relationship types between records."""
    ATTACHMENT = "ATTACHMENT"      # Email -> Attached file
    THREAD = "THREAD"              # Message -> Reply/Forward
    DERIVATION = "DERIVATION"      # Source -> Derived document
    REFERENCE = "REFERENCE"        # Document -> Referenced document
    CONTAINER = "CONTAINER"        # Folder -> Contained record
    VERSION = "VERSION"            # Document -> Previous version
    DUPLICATE = "DUPLICATE"        # Record -> Duplicate record


class GovernanceState(Enum):
    """Current governance status of a record."""
    ACTIVE = "ACTIVE"                      # Normal state, policies apply
    RETENTION_REQUIRED = "RETENTION_REQUIRED"  # Under retention obligation
    HOLD = "HOLD"                          # Under legal hold
    ELIGIBLE_FOR_DELETION = "ELIGIBLE_FOR_DELETION"  # Can be deleted
    MUST_DELETE = "MUST_DELETE"            # Required to delete (GDPR etc)
    DELETED = "DELETED"                    # Logically deleted
    ARCHIVED = "ARCHIVED"                  # Moved to archive tier


class Jurisdiction(Enum):
    """Legal jurisdictions for compliance."""
    US = "US"
    US_CA = "US_CA"  # California
    US_NY = "US_NY"  # New York
    EU = "EU"
    EU_DE = "EU_DE"  # Germany
    EU_ES = "EU_ES"  # Spain
    EU_FR = "EU_FR"  # France
    UK = "UK"
    CA = "CA"        # Canada
    GLOBAL = "GLOBAL"


class Regulation(Enum):
    """Regulatory frameworks."""
    HIPAA = "HIPAA"
    SOX = "SOX"
    SEC = "SEC"
    FINRA = "FINRA"
    GDPR = "GDPR"
    CPRA = "CPRA"
    PIPEDA = "PIPEDA"
    PCI_DSS = "PCI_DSS"
    IRS = "IRS"
    HGB = "HGB"  # German Commercial Code
    INTERNAL = "INTERNAL"


# =============================================================================
# CORE ENTITIES
# =============================================================================

@dataclass
class Record:
    """
    A record in the knowledge graph.
    
    Records are the primary entities representing documents, emails,
    chat messages, and other information objects subject to governance.
    """
    id: str
    type: RecordType
    title: str
    
    # Temporal attributes
    created: datetime
    modified: datetime
    accessed: Optional[datetime] = None
    
    # Ownership and location
    custodian_id: str = ""
    system_id: str = ""
    container_id: Optional[str] = None
    
    # Content attributes
    content_hash: str = ""
    size_bytes: int = 0
    mime_type: str = ""
    
    # Classification
    contains_pii: bool = False
    contains_phi: bool = False  # Protected Health Information
    confidentiality: str = "INTERNAL"  # PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED
    
    # Jurisdiction
    jurisdiction: Jurisdiction = Jurisdiction.US
    
    # Metadata (flexible key-value)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: Set[str] = field(default_factory=set)
    
    # Governance state (computed)
    governance_state: GovernanceState = GovernanceState.ACTIVE
    retention_deadline: Optional[datetime] = None
    hold_matters: List[str] = field(default_factory=list)
    deletion_eligible_date: Optional[datetime] = None
    
    # Audit
    created_in_graph: datetime = field(default_factory=datetime.now)
    last_evaluated: Optional[datetime] = None


@dataclass
class Custodian:
    """
    A person or entity responsible for records.
    
    Custodians are employees, contractors, or systems that create,
    own, or manage records.
    """
    id: str
    name: str
    email: str
    department: str = ""
    title: str = ""
    manager_id: Optional[str] = None
    location: str = ""
    jurisdiction: Jurisdiction = Jurisdiction.US
    is_active: bool = True
    
    # Employment dates (for temporal queries)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Matter:
    """
    A legal matter triggering holds.
    
    Matters represent litigation, investigations, or audits that
    require preservation of relevant records.
    """
    id: str
    name: str
    description: str = ""
    matter_type: str = "LITIGATION"  # LITIGATION, INVESTIGATION, AUDIT, REGULATORY
    
    # Temporal
    created: datetime = field(default_factory=datetime.now)
    hold_start: Optional[datetime] = None
    hold_end: Optional[datetime] = None
    is_active: bool = True
    
    # Scope
    custodian_ids: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None
    
    # Legal reference
    case_number: str = ""
    counsel: str = ""
    
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class System:
    """
    A source system containing records.
    
    Systems represent email servers, document management systems,
    chat platforms, and other data sources.
    """
    id: str
    name: str
    system_type: str  # EMAIL, DMS, CHAT, CRM, ERP, DATABASE
    vendor: str = ""
    
    # Connection info (for connectors)
    connection_string: str = ""
    last_sync: Optional[datetime] = None
    
    # Jurisdiction default
    default_jurisdiction: Jurisdiction = Jurisdiction.US
    
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# RELATIONSHIPS
# =============================================================================

@dataclass
class Relationship:
    """
    A temporal relationship between two records.
    
    Relationships enable hold propagation and governance inheritance.
    All relationships are temporal (valid_from, valid_to).
    """
    id: str
    source_id: str
    target_id: str
    relation_type: RelationType
    
    # Temporal validity (bitemporal)
    valid_from: datetime
    valid_to: Optional[datetime] = None  # None = still valid
    
    # Transaction time (when recorded in graph)
    transaction_time: datetime = field(default_factory=datetime.now)
    
    # Relationship metadata
    confidence: float = 1.0  # For inferred relationships
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_current(self) -> bool:
        """Check if relationship is currently valid."""
        now = datetime.now()
        return self.valid_from <= now and (self.valid_to is None or self.valid_to > now)


@dataclass 
class CustodianAssignment:
    """
    Temporal assignment of a custodian to a record.
    
    Tracks ownership changes over time.
    """
    id: str
    record_id: str
    custodian_id: str
    
    valid_from: datetime
    valid_to: Optional[datetime] = None
    
    assignment_type: str = "OWNER"  # OWNER, CREATOR, CONTRIBUTOR, REVIEWER
    
    transaction_time: datetime = field(default_factory=datetime.now)


@dataclass
class HoldAssignment:
    """
    Assignment of a record to a legal hold.
    
    Tracks which records are under which holds, with propagation info.
    """
    id: str
    record_id: str
    matter_id: str
    
    # How this record came to be on hold
    assignment_type: str = "DIRECT"  # DIRECT, PROPAGATED, CUSTODIAN
    propagation_path: List[str] = field(default_factory=list)  # Record IDs in propagation chain
    propagation_relation: Optional[RelationType] = None
    
    # Temporal
    assigned_at: datetime = field(default_factory=datetime.now)
    released_at: Optional[datetime] = None
    
    # Audit
    assigned_by: str = ""
    release_reason: str = ""


# =============================================================================
# GOVERNANCE RULES (Runtime representation of DRGL)
# =============================================================================

@dataclass
class RetentionRule:
    """Compiled retention rule from DRGL."""
    id: str
    name: str
    
    # Selector (compiled to callable)
    selector_expr: str  # Original DRGL selector
    
    # Duration
    duration_days: int
    trigger: str  # CREATION, LAST_MODIFIED, EVENT(x)
    
    # Scope
    regulation: Optional[Regulation] = None
    jurisdiction: Optional[Jurisdiction] = None
    
    # Priority for conflicts
    priority: int = 0
    
    # Audit
    source_text: str = ""  # Original NL policy
    citation: str = ""


@dataclass
class HoldRule:
    """Compiled hold rule from DRGL."""
    id: str
    matter_id: str
    
    # Selector
    selector_expr: str
    
    # Propagation
    propagate_via: List[RelationType] = field(default_factory=list)
    propagation_depth: int = -1  # -1 = unlimited
    
    # Temporal scope
    date_range_start: Optional[datetime] = None
    date_range_end: Optional[datetime] = None
    
    # Status
    is_active: bool = True
    
    source_text: str = ""


@dataclass
class DeletionRule:
    """Compiled deletion rule from DRGL (DELETE, MUST_DELETE, ALLOW_DELETION)."""
    id: str
    name: str
    rule_type: str  # DELETE, MUST_DELETE, ALLOW_DELETION
    
    selector_expr: str
    
    # Conditions
    condition_expr: str = ""  # e.g., "processing_complete = true"
    
    # Exceptions
    unless_expr: str = ""  # e.g., "legal_hold_active = true"
    
    regulation: Optional[Regulation] = None
    jurisdiction: Optional[Jurisdiction] = None
    
    priority: int = 0
    source_text: str = ""
    citation: str = ""


# =============================================================================
# GOVERNANCE EVALUATION RESULT
# =============================================================================

@dataclass
class GovernanceDecision:
    """
    Result of evaluating governance rules for a record.
    
    Provides full explainability of why a record has its current state.
    """
    record_id: str
    evaluated_at: datetime
    
    # Final state
    final_state: GovernanceState
    
    # Contributing rules
    applicable_retention_rules: List[str] = field(default_factory=list)
    applicable_hold_rules: List[str] = field(default_factory=list)
    applicable_deletion_rules: List[str] = field(default_factory=list)
    
    # Computed dates
    retention_deadline: Optional[datetime] = None
    earliest_deletion_date: Optional[datetime] = None
    
    # Active holds
    active_holds: List[str] = field(default_factory=list)
    
    # Conflicts detected
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    
    # Explanation chain
    explanation: List[str] = field(default_factory=list)
    
    # Winning rule per category
    winning_retention_rule: Optional[str] = None
    winning_deletion_rule: Optional[str] = None


# =============================================================================
# AUDIT LOG
# =============================================================================

@dataclass
class AuditEvent:
    """Audit log entry for governance actions."""
    id: str
    timestamp: datetime
    
    event_type: str  # HOLD_APPLIED, HOLD_RELEASED, RETENTION_SET, DELETED, RULE_EVALUATED
    record_id: Optional[str] = None
    matter_id: Optional[str] = None
    rule_id: Optional[str] = None
    
    actor: str = "SYSTEM"
    
    before_state: Optional[GovernanceState] = None
    after_state: Optional[GovernanceState] = None
    
    details: Dict[str, Any] = field(default_factory=dict)
