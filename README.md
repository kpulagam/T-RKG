# T-RKG: Temporal Records Knowledge Graph

A graph-based approach to enterprise records governance with bitemporal modeling, relationship-aware hold propagation, and multi-jurisdictional compliance.

## Key Contributions

1. **Graph-based record modeling** with typed relationships (attachment, thread, derivation, reference, container)
2. **Bitemporal attributes** (valid time + transaction time) for point-in-time queries
3. **Hold propagation algorithm** traversing relationships for legal discovery
4. **Multi-jurisdictional support** for SOX, HIPAA, GDPR, FINRA, HGB, PIPEDA


## Quick Start

```python
from trkg import TRKGStore, Record, RecordType, RelationType
from trkg.synthetic import generate_test_dataset
from datetime import datetime

# Generate sample enterprise data
store = generate_test_dataset(num_records=10000)
print(f"Generated {len(store.records)} records, {len(store.relationships)} relationships")

# Query records by type
emails = store.select_records(lambda r: r.type == RecordType.EMAIL)
print(f"Found {len(emails)} emails")

# Point-in-time query
records_2023 = store.query_at_time(datetime(2023, 6, 15))
print(f"Records as of 2023-06-15: {len(records_2023)}")

# Hold propagation
seed_records = [r.id for r in emails[:50]]
propagated = store.propagate_hold(
    seed_records,
    relation_types=[RelationType.ATTACHMENT, RelationType.THREAD],
    max_depth=5
)
print(f"Hold propagation: {len(seed_records)} seeds → {len(propagated)} total")

# Apply legal hold
store.apply_hold("litigation_2024", list(propagated))
held = store.get_records_on_hold("litigation_2024")
print(f"Records on hold: {len(held)}")
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    T-RKG Store                          │
├─────────────────────────────────────────────────────────┤
│  Entities          │  Relationships    │  Operations    │
│  ─────────         │  ─────────────    │  ──────────    │
│  • Record          │  • ATTACHMENT     │  • Query       │
│  • Custodian       │  • THREAD         │  • Propagate   │
│  • Matter          │  • DERIVATION     │  • Hold/Release│
│  • System          │  • REFERENCE      │  • Temporal    │
│                    │  • CONTAINER      │                │
├─────────────────────────────────────────────────────────┤
│  Bitemporal: valid_time + transaction_time              │
└─────────────────────────────────────────────────────────┘
```

## Performance Results

TBU

## Project Structure

```
t-rkg/
├── trkg/
│   ├── __init__.py
│   ├── schema.py        # Entity definitions
│   ├── store.py         # Graph storage & queries
│   └── synthetic.py     # Test data generator
├── experiments/
│   └── run_scalability.py
├── tests/
│   └── test_trkg.py
├── requirements.txt
└── README.md
```

## Running Experiments

```bash
# Reproduce paper experiments
python experiments/run_scalability.py
```
