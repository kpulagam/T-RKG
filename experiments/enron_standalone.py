#!/usr/bin/env python3
"""
Standalone Enron Experiment Script
Run this directly - no file replacement needed.
"""

import os
import sys
import re
import email
import hashlib
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Any

# Add trkg to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trkg import (
    TRKGStore, Record, Custodian, Matter, Relationship,
    RecordType, RelationType, Jurisdiction, GovernanceState,
    ConflictDetector, RetentionCalculator, GovernanceReasoner
)

# Enron employees
ENRON_EMPLOYEES = {
    "allen-p": {"name": "Phillip Allen", "dept": "Trading"},
    "arnold-j": {"name": "John Arnold", "dept": "Trading"},
    "beck-s": {"name": "Sally Beck", "dept": "Operations"},
    "buy-r": {"name": "Rick Buy", "dept": "Risk Management"},
    "cash-m": {"name": "Michelle Cash", "dept": "Legal"},
    "dasovich-j": {"name": "Jeff Dasovich", "dept": "Government Affairs"},
    "delainey-d": {"name": "David Delainey", "dept": "Trading"},
    "derrick-j": {"name": "James Derrick", "dept": "Legal"},
    "fastow-a": {"name": "Andrew Fastow", "dept": "Finance"},
    "germany-c": {"name": "Chris Germany", "dept": "Trading"},
    "haedicke-m": {"name": "Mark Haedicke", "dept": "Legal"},
    "kaminski-v": {"name": "Vince Kaminski", "dept": "Research"},
    "kean-s": {"name": "Steven Kean", "dept": "Government Affairs"},
    "kitchen-l": {"name": "Louise Kitchen", "dept": "Trading"},
    "lavorato-j": {"name": "John Lavorato", "dept": "Trading"},
    "lay-k": {"name": "Kenneth Lay", "dept": "Executive"},
    "mann-k": {"name": "Kay Mann", "dept": "Legal"},
    "presto-k": {"name": "Kevin Presto", "dept": "Trading"},
    "sanders-r": {"name": "Richard Sanders", "dept": "Legal"},
    "shackleton-s": {"name": "Sara Shackleton", "dept": "Legal"},
    "skilling-j": {"name": "Jeffrey Skilling", "dept": "Executive"},
    "taylor-m": {"name": "Mark Taylor", "dept": "Legal"},
    "whalley-g": {"name": "Greg Whalley", "dept": "Executive"},
}


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse email date."""
    if not date_str:
        return None
    
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S",
        "%d %b %Y %H:%M:%S %z",
        "%d %b %Y %H:%M:%S",
    ]
    
    date_str = re.sub(r'\s+', ' ', date_str.strip())
    date_str = re.sub(r'\([^)]+\)', '', date_str).strip()
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str[:30], fmt)
            # Make timezone-naive
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            return dt
        except:
            continue
    return None


def normalize_subject(subj: str) -> str:
    """Remove Re:/Fw: prefixes and normalize."""
    cleaned = re.sub(r'^(re|fw|fwd)[\s]*:[\s]*', '', subj.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r'^(re|fw|fwd)[\s]*:[\s]*', '', cleaned, flags=re.IGNORECASE)
    return cleaned.strip().lower()[:100]


def load_enron(data_dir: str = "data/enron", max_emails: int = 50000) -> TRKGStore:
    """Load Enron with subject-based thread inference."""
    
    data_path = Path(data_dir)
    store = TRKGStore()
    
    print(f"  Loading from {data_path}...")
    
    # Add custodians
    for emp_id, info in ENRON_EMPLOYEES.items():
        store.add_custodian(Custodian(
            id=f"enron_{emp_id}",
            name=info["name"],
            email=f"{emp_id}@enron.com",
            department=info["dept"],
            jurisdiction=Jurisdiction.US,
        ))
    
    # Add matter
    store.add_matter(Matter(
        id="matter_sec",
        name="SEC v. Enron",
        matter_type="REGULATORY",
        custodian_ids=[f"enron_{e}" for e in ["fastow-a", "skilling-j", "lay-k"]],
    ))
    
    # Load emails
    emails_data = []  # (record_id, created, title, custodian)
    count = 0
    
    for custodian_dir in sorted(data_path.iterdir()):
        if not custodian_dir.is_dir():
            continue
        
        custodian_id = custodian_dir.name
        
        for root, dirs, files in os.walk(custodian_dir):
            for fname in files:
                if fname.startswith('.') or count >= max_emails:
                    continue
                
                try:
                    with open(Path(root) / fname, 'r', errors='ignore') as f:
                        msg = email.message_from_file(f)
                    
                    subject = msg.get('Subject', '(no subject)')[:200]
                    date_str = msg.get('Date', '')
                    created = parse_date(date_str)
                    
                    if not created:
                        continue
                    
                    record_id = f"enron_{hashlib.md5(f'{root}/{fname}'.encode()).hexdigest()[:12]}"
                    
                    record = Record(
                        id=record_id,
                        type=RecordType.EMAIL,
                        title=subject,
                        created=created,
                        modified=created,
                        custodian_id=f"enron_{custodian_id}" if custodian_id in ENRON_EMPLOYEES else "enron_unknown",
                        system_id="sys_enron",
                        jurisdiction=Jurisdiction.US,
                        metadata={"is_public_company": True, "is_financial": True},
                    )
                    
                    store.add_record(record)
                    emails_data.append((record_id, created, subject, custodian_id))
                    count += 1
                    
                    if count % 10000 == 0:
                        print(f"    Loaded {count:,} emails...")
                
                except Exception as e:
                    continue
            
            if count >= max_emails:
                break
        if count >= max_emails:
            break
    
    print(f"  Loaded {count:,} emails")
    
    # Build thread relationships from subject lines
    print(f"  Building thread relationships from subject patterns...")
    
    subject_groups = defaultdict(list)
    for record_id, created, title, custodian in emails_data:
        norm = normalize_subject(title)
        if norm and len(norm) > 3:  # Skip very short subjects
            subject_groups[norm].append((record_id, created, title))
    
    thread_count = 0
    for norm_subj, emails in subject_groups.items():
        if len(emails) < 2:
            continue
        
        # Sort by date
        emails.sort(key=lambda x: x[1])
        
        # Link Re:/Fw: emails to previous
        for i in range(1, len(emails)):
            curr_id, curr_date, curr_title = emails[i]
            prev_id, prev_date, prev_title = emails[i-1]
            
            # Check if current is a reply/forward
            if re.match(r'^(re|fw|fwd)[\s]*:', curr_title, re.IGNORECASE):
                rel = Relationship(
                    id=f"rel_{prev_id}_{curr_id}",
                    source_id=prev_id,
                    target_id=curr_id,
                    relation_type=RelationType.THREAD,
                    valid_from=curr_date,
                )
                store.add_relationship(rel)
                thread_count += 1
    
    print(f"  Created {thread_count:,} thread relationships")
    
    return store


def run_experiments(store: TRKGStore) -> Dict[str, Any]:
    """Run all experiments."""
    
    results = {"metadata": {"run_date": datetime.now().isoformat(), "is_real_data": True}}
    
    stats = store.get_statistics()
    print(f"\n  Records: {stats['total_records']:,}")
    print(f"  Relationships: {stats['total_relationships']:,}")
    
    results["dataset"] = {
        "records": stats["total_records"],
        "relationships": stats["total_relationships"],
    }
    
    # Propagation test
    print(f"\n  [RQ2] Typed Hold Propagation")
    seeds = list(store.records.keys())[:100]
    
    for name, rel_types in [
        ("No propagation", []),
        ("THREAD only", [RelationType.THREAD]),
        ("All types", list(RelationType)),
    ]:
        if rel_types:
            propagated = store.propagate_hold(seeds, rel_types, max_depth=10)
        else:
            propagated = set(seeds)
        
        ratio = len(propagated) / len(seeds) if seeds else 0
        print(f"    {name}: {len(seeds)} → {len(propagated)} ({ratio:.2f}x)")
    
    # Retention
    print(f"\n  [RQ4] Retention Reasoning")
    calculator = RetentionCalculator(store)
    with_retention = 0
    multi_reg = 0
    
    for record in list(store.records.values())[:10000]:  # Sample
        deadline, rules = calculator.calculate_retention_deadline(record)
        if deadline:
            with_retention += 1
            if len(rules) >= 2:
                multi_reg += 1
    
    print(f"    Records with retention: {with_retention:,}")
    print(f"    Multi-regulation: {multi_reg:,}")
    
    results["retention"] = {"with_retention": with_retention, "multi_regulation": multi_reg}
    
    # Conflicts (will be 0 for US-only data)
    print(f"\n  [RQ3] Conflict Detection")
    detector = ConflictDetector(store)
    conflicts = detector.detect_all_conflicts()
    print(f"    Conflicts: {len(conflicts)} (expected 0 for US-only data)")
    
    results["conflicts"] = len(conflicts)
    
    return results


def main():
    print("\n" + "=" * 60)
    print("  ENRON REAL DATA EXPERIMENT (Standalone)")
    print("=" * 60)
    
    if not Path("data/enron").exists():
        print("ERROR: data/enron not found. Run the download first.")
        return
    
    store = load_enron(max_emails=50000)
    results = run_experiments(store)
    
    with open("enron_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n  Results saved to: enron_results.json")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
