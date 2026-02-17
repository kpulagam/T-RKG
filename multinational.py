"""
Multinational Scenario Generator

Creates realistic cross-jurisdictional records that trigger
GDPR vs SOX, GDPR vs SEC, and other critical conflicts.

Use Case: Multinational corporation with:
- US headquarters (SOX compliance)
- EU subsidiary (GDPR compliance)
- Records that contain EU citizen PII but are subject to US financial regulations
"""

import random
from datetime import datetime, timedelta
from typing import List, Optional
from dataclasses import dataclass

from trkg.schema import (
    Record, Custodian, RecordType, Jurisdiction, GovernanceState
)
from trkg.store import TRKGStore
from trkg.synthetic import SyntheticDataGenerator, GeneratorConfig


@dataclass
class MultinationalConfig:
    """Configuration for multinational scenarios."""
    # Company structure
    us_employees: int = 60
    eu_employees: int = 30
    uk_employees: int = 10
    
    # Record distribution
    num_financial_records: int = 500      # Subject to SOX
    num_eu_pii_records: int = 300         # Subject to GDPR
    num_cross_border_records: int = 200   # Subject to BOTH
    num_medical_records: int = 100        # HIPAA
    num_german_commercial: int = 100      # HGB
    
    # General records
    num_emails: int = 2000
    num_documents: int = 1000
    num_chats: int = 500


def generate_multinational_dataset(
    config: Optional[MultinationalConfig] = None,
    seed: int = 42
) -> TRKGStore:
    """
    Generate a multinational corporation dataset with realistic conflicts.
    
    This creates records that span jurisdictions, triggering:
    - GDPR vs SOX (EU PII in US financial records)
    - GDPR vs SEC (EU PII in broker-dealer records)
    - GDPR vs HIPAA (EU citizen medical records in US)
    - HGB vs SOX (German subsidiary financial records)
    """
    config = config or MultinationalConfig()
    random.seed(seed)
    
    store = TRKGStore()
    
    # Add systems
    _add_systems(store)
    
    # Add custodians across jurisdictions
    us_custodians = _add_custodians(store, "US", config.us_employees, seed)
    eu_custodians = _add_custodians(store, "EU", config.eu_employees, seed + 1000)
    uk_custodians = _add_custodians(store, "UK", config.uk_employees, seed + 2000)
    de_custodians = _add_custodians(store, "EU_DE", 20, seed + 3000)  # German subsidiary
    ca_custodians = _add_custodians(store, "US_CA", 15, seed + 4000)  # California office
    
    all_custodians = us_custodians + eu_custodians + uk_custodians + de_custodians + ca_custodians
    
    print(f"Generated {len(all_custodians)} custodians across jurisdictions")
    
    record_id = 0
    
    # 1. US Financial Records (SOX) - no PII, just financial
    for i in range(config.num_financial_records):
        record = Record(
            id=f"fin_us_{record_id:06d}",
            type=random.choice([RecordType.FINANCIAL, RecordType.AUDIT, RecordType.TAX]),
            title=f"Financial Report Q{random.randint(1,4)} {random.randint(2020,2024)}",
            created=_random_date(seed + i),
            modified=_random_date(seed + i),
            custodian_id=random.choice(us_custodians),
            system_id="sys_erp",
            contains_pii=False,  # Pure financial, no PII
            contains_phi=False,
            jurisdiction=Jurisdiction.US,
            confidentiality="RESTRICTED",
            metadata={"is_public_company": True, "scenario": "us_financial"}
        )
        store.add_record(record)
        record_id += 1
    
    # 2. EU PII Records (GDPR) - EU citizen data, EU jurisdiction
    for i in range(config.num_eu_pii_records):
        record = Record(
            id=f"eu_pii_{record_id:06d}",
            type=random.choice([RecordType.DOCUMENT, RecordType.EMAIL, RecordType.TICKET]),
            title=f"Customer Record - EU Citizen {i}",
            created=_random_date(seed + i),
            modified=_random_date(seed + i),
            custodian_id=random.choice(eu_custodians + uk_custodians),
            system_id="sys_crm",
            contains_pii=True,  # EU citizen PII
            contains_phi=False,
            jurisdiction=random.choice([Jurisdiction.EU, Jurisdiction.EU_DE, Jurisdiction.EU_FR, Jurisdiction.UK]),
            metadata={"data_subject_location": "EU", "scenario": "eu_pii"}
        )
        store.add_record(record)
        record_id += 1
    
    # 3. CROSS-BORDER RECORDS (SOX + GDPR conflict!) 
    # These are US financial records that contain EU citizen PII
    # Example: EU customer payment records in US accounting system
    for i in range(config.num_cross_border_records):
        # Half in US jurisdiction with EU PII, half in EU jurisdiction with US financial requirements
        if random.random() < 0.5:
            # US financial record containing EU citizen PII
            jurisdiction = Jurisdiction.US
            custodian = random.choice(us_custodians)
        else:
            # EU subsidiary financial record (SOX + GDPR both apply)
            jurisdiction = random.choice([Jurisdiction.EU, Jurisdiction.EU_DE])
            custodian = random.choice(eu_custodians + de_custodians)
        
        record = Record(
            id=f"crossborder_{record_id:06d}",
            type=random.choice([RecordType.FINANCIAL, RecordType.INVOICE, RecordType.CONTRACT]),
            title=f"Cross-Border Transaction {i}",
            created=_random_date(seed + i),
            modified=_random_date(seed + i),
            custodian_id=custodian,
            system_id="sys_erp",
            contains_pii=True,  # Contains EU citizen PII!
            contains_phi=False,
            jurisdiction=jurisdiction,
            confidentiality="CONFIDENTIAL",
            metadata={
                "is_public_company": True,
                "data_subject_location": "EU",
                "scenario": "cross_border_sox_gdpr"
            }
        )
        store.add_record(record)
        record_id += 1
    
    # 4. US Medical Records with EU patients (HIPAA + GDPR)
    for i in range(config.num_medical_records):
        record = Record(
            id=f"medical_{record_id:06d}",
            type=RecordType.MEDICAL,
            title=f"Patient Record {i}",
            created=_random_date(seed + i),
            modified=_random_date(seed + i),
            custodian_id=random.choice(us_custodians),
            system_id="sys_dms",
            contains_pii=True,
            contains_phi=True,  # Protected Health Information
            jurisdiction=Jurisdiction.US,
            confidentiality="RESTRICTED",
            metadata={"patient_location": "EU", "scenario": "hipaa_gdpr"}
        )
        store.add_record(record)
        record_id += 1
    
    # 5. German Subsidiary Commercial Records (HGB + SOX)
    for i in range(config.num_german_commercial):
        record = Record(
            id=f"german_{record_id:06d}",
            type=random.choice([RecordType.FINANCIAL, RecordType.INVOICE, RecordType.CONTRACT]),
            title=f"German Commercial Document {i}",
            created=_random_date(seed + i),
            modified=_random_date(seed + i),
            custodian_id=random.choice(de_custodians),
            system_id="sys_erp",
            contains_pii=random.random() < 0.5,
            contains_phi=False,
            jurisdiction=Jurisdiction.EU_DE,  # German jurisdiction = HGB applies
            confidentiality="CONFIDENTIAL",
            metadata={"is_public_company": True, "scenario": "hgb_sox"}
        )
        store.add_record(record)
        record_id += 1
    
    # 6. California Records (SOX + CPRA)
    for i in range(150):
        record = Record(
            id=f"california_{record_id:06d}",
            type=random.choice([RecordType.FINANCIAL, RecordType.DOCUMENT]),
            title=f"California Financial Doc {i}",
            created=_random_date(seed + i),
            modified=_random_date(seed + i),
            custodian_id=random.choice(ca_custodians),
            system_id="sys_erp",
            contains_pii=True,  # California consumer PII
            contains_phi=False,
            jurisdiction=Jurisdiction.US_CA,
            metadata={"is_public_company": True, "scenario": "sox_cpra"}
        )
        store.add_record(record)
        record_id += 1
    
    # 7. General emails and documents (baseline)
    for i in range(config.num_emails):
        custodian = random.choice(all_custodians)
        jurisdiction = store.custodians[custodian].jurisdiction
        
        record = Record(
            id=f"email_{record_id:06d}",
            type=RecordType.EMAIL,
            title=f"Email {i}",
            created=_random_date(seed + i),
            modified=_random_date(seed + i),
            custodian_id=custodian,
            system_id="sys_email",
            contains_pii=random.random() < 0.2,
            jurisdiction=jurisdiction,
            metadata={"scenario": "general"}
        )
        store.add_record(record)
        record_id += 1
    
    print(f"Generated {len(store.records)} total records")
    
    # Print scenario breakdown
    scenarios = {}
    for r in store.records.values():
        s = r.metadata.get("scenario", "unknown")
        scenarios[s] = scenarios.get(s, 0) + 1
    
    print("\nScenario breakdown:")
    for s, count in sorted(scenarios.items()):
        print(f"  {s}: {count}")
    
    return store


def _add_systems(store: TRKGStore):
    """Add source systems."""
    from trkg.schema import System
    
    systems = [
        ("sys_email", "Exchange Online", "EMAIL"),
        ("sys_dms", "SharePoint", "DMS"),
        ("sys_crm", "Salesforce", "CRM"),
        ("sys_erp", "SAP", "ERP"),
    ]
    
    for sys_id, name, sys_type in systems:
        store.add_system(System(id=sys_id, name=name, system_type=sys_type))


def _add_custodians(store: TRKGStore, jurisdiction: str, count: int, seed: int) -> List[str]:
    """Add custodians for a jurisdiction."""
    random.seed(seed)
    
    jurisdiction_map = {
        "US": Jurisdiction.US,
        "US_CA": Jurisdiction.US_CA,
        "EU": Jurisdiction.EU,
        "EU_DE": Jurisdiction.EU_DE,
        "UK": Jurisdiction.UK,
    }
    
    first_names = ["James", "Mary", "John", "Emma", "Michael", "Sophie", "Hans", "Maria"]
    last_names = ["Smith", "Johnson", "Mueller", "Garcia", "Wilson", "Schmidt", "Brown"]
    departments = ["Finance", "Legal", "Sales", "Engineering", "HR"]
    
    custodian_ids = []
    for i in range(count):
        cust_id = f"emp_{jurisdiction}_{i:04d}"
        custodian = Custodian(
            id=cust_id,
            name=f"{random.choice(first_names)} {random.choice(last_names)}",
            email=f"employee{i}@acme-{jurisdiction.lower()}.com",
            department=random.choice(departments),
            jurisdiction=jurisdiction_map.get(jurisdiction, Jurisdiction.US)
        )
        store.add_custodian(custodian)
        custodian_ids.append(cust_id)
    
    return custodian_ids


def _random_date(seed: int) -> datetime:
    """Generate a random date."""
    random.seed(seed)
    start = datetime(2020, 1, 1)
    end = datetime(2024, 12, 31)
    delta = end - start
    return start + timedelta(days=random.randint(0, delta.days))


if __name__ == "__main__":
    from trkg import ConflictDetector
    
    print("Generating multinational dataset...")
    store = generate_multinational_dataset()
    
    print("\nRunning conflict detection...")
    detector = ConflictDetector(store)
    conflicts = detector.detect_all_conflicts()
    summary = detector.get_conflict_summary()
    
    print(f"\n=== CONFLICT SUMMARY ===")
    print(f"Total conflicts: {summary['total_conflicts']}")
    print(f"Affected records: {summary['affected_records']}")
    print(f"Critical conflicts: {summary['critical_count']}")
    
    print(f"\nBy type:")
    for ctype, count in summary['by_type'].items():
        print(f"  {ctype}: {count}")
    
    print(f"\nBy regulation pair:")
    for pair, count in sorted(summary['by_regulation_pair'].items(), key=lambda x: -x[1]):
        print(f"  {pair}: {count}")
    
    print(f"\nBy severity:")
    for sev, count in summary['by_severity'].items():
        print(f"  {sev}: {count}")
