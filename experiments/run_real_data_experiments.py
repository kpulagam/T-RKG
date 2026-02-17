#!/usr/bin/env python3
"""
T-RKG Real Data Experiments

Run this script to:
1. Download the real Enron email corpus from CMU
2. Run all T-RKG experiments on real data
3. Generate publication-ready results

Usage:
    python run_real_data_experiments.py --dataset enron
    python run_real_data_experiments.py --dataset icews  # Alternative: ICEWS temporal KG
"""

import argparse
import json
import os
import sys
import time
import tarfile
import urllib.request
import shutil
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from typing import Dict, Any, List, Tuple, Optional

# Ensure trkg is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trkg import (
    TRKGStore, Record, Custodian, Matter, Relationship,
    RecordType, RelationType, Jurisdiction, GovernanceState,
    SyntheticDataGenerator, GeneratorConfig,
    ConflictDetector, RetentionCalculator, GovernanceReasoner
)


# =============================================================================
# DATASET DOWNLOADERS
# =============================================================================

class EnronDownloader:
    """Downloads and extracts the Enron email corpus."""
    
    URL = "https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz"
    
    def __init__(self, data_dir: str = "data/enron"):
        self.data_dir = Path(data_dir)
        self.tar_path = self.data_dir.parent / "enron_mail.tar.gz"
    
    def download(self) -> bool:
        """Download Enron dataset. Returns True if successful."""
        self.data_dir.parent.mkdir(parents=True, exist_ok=True)
        
        if self.data_dir.exists() and any(self.data_dir.iterdir()):
            print(f"  Enron data already exists at {self.data_dir}")
            return True
        
        if not self.tar_path.exists():
            print(f"  Downloading Enron dataset (~423MB)...")
            print(f"  URL: {self.URL}")
            print(f"  This may take several minutes...")
            
            try:
                def progress_hook(count, block_size, total_size):
                    percent = int(count * block_size * 100 / total_size)
                    print(f"\r  Progress: {percent}%", end="", flush=True)
                
                urllib.request.urlretrieve(self.URL, self.tar_path, progress_hook)
                print(f"\n  Download complete: {self.tar_path}")
            except Exception as e:
                print(f"\n  Download failed: {e}")
                return False
        
        # Extract
        print(f"  Extracting to {self.data_dir}...")
        try:
            with tarfile.open(self.tar_path, "r:gz") as tar:
                tar.extractall(self.data_dir.parent)
            
            # The archive extracts to 'maildir/', rename to 'enron'
            maildir_path = self.data_dir.parent / "maildir"
            if maildir_path.exists():
                if self.data_dir.exists():
                    shutil.rmtree(self.data_dir)
                shutil.move(str(maildir_path), str(self.data_dir))
            
            print(f"  Extraction complete")
            return True
        except Exception as e:
            print(f"  Extraction failed: {e}")
            return False


class ICEWSDownloader:
    """Downloads ICEWS temporal knowledge graph dataset."""
    
    # Multiple mirror options for ICEWS14
    URL_OPTIONS = [
        # Option 1: tkbc repository (most reliable)
        {
            "train": "https://raw.githubusercontent.com/facebookresearch/tkbc/main/data/ICEWS14/train.txt",
            "valid": "https://raw.githubusercontent.com/facebookresearch/tkbc/main/data/ICEWS14/valid.txt",
            "test": "https://raw.githubusercontent.com/facebookresearch/tkbc/main/data/ICEWS14/test.txt",
        },
        # Option 2: TLogic repository
        {
            "train": "https://raw.githubusercontent.com/liu-yushan/TLogic/main/data/ICEWS14/train.txt",
            "valid": "https://raw.githubusercontent.com/liu-yushan/TLogic/main/data/ICEWS14/valid.txt",
            "test": "https://raw.githubusercontent.com/liu-yushan/TLogic/main/data/ICEWS14/test.txt",
        },
        # Option 3: xERTE repository  
        {
            "train": "https://raw.githubusercontent.com/TemporalKGTeam/xERTE/main/data/ICEWS14/train.txt",
            "valid": "https://raw.githubusercontent.com/TemporalKGTeam/xERTE/main/data/ICEWS14/valid.txt",
            "test": "https://raw.githubusercontent.com/TemporalKGTeam/xERTE/main/data/ICEWS14/test.txt",
        },
    ]
    
    def __init__(self, data_dir: str = "data/icews"):
        self.data_dir = Path(data_dir)
    
    def download(self) -> bool:
        """Download ICEWS dataset. Returns True if successful."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Try each URL option until one works
        for option_idx, urls in enumerate(self.URL_OPTIONS):
            print(f"  Trying mirror {option_idx + 1}/{len(self.URL_OPTIONS)}...")
            success = True
            
            for split, url in urls.items():
                filepath = self.data_dir / f"{split}.txt"
                if filepath.exists():
                    print(f"    {split}.txt already exists")
                    continue
                
                print(f"    Downloading {split}.txt...")
                try:
                    urllib.request.urlretrieve(url, filepath)
                except Exception as e:
                    print(f"    Failed: {e}")
                    success = False
                    # Clean up partial downloads
                    for s in ["train", "valid", "test"]:
                        p = self.data_dir / f"{s}.txt"
                        if p.exists():
                            p.unlink()
                    break
            
            if success:
                print(f"  ICEWS14 download complete from mirror {option_idx + 1}")
                return True
        
        print(f"  All download mirrors failed.")
        print(f"  You can manually download ICEWS14 from:")
        print(f"    https://github.com/facebookresearch/tkbc/tree/main/data/ICEWS14")
        print(f"  Place train.txt, valid.txt, test.txt in: {self.data_dir}")
        return False


# =============================================================================
# ENRON DATA LOADER
# =============================================================================

# Real Enron employee metadata
ENRON_EMPLOYEES = {
    "allen-p": {"name": "Phillip Allen", "dept": "Trading", "title": "Managing Director"},
    "arnold-j": {"name": "John Arnold", "dept": "Trading", "title": "VP Trading"},
    "bass-e": {"name": "Eric Bass", "dept": "Trading", "title": "Trader"},
    "beck-s": {"name": "Sally Beck", "dept": "Operations", "title": "COO"},
    "buy-r": {"name": "Rick Buy", "dept": "Risk Management", "title": "Chief Risk Officer"},
    "cash-m": {"name": "Michelle Cash", "dept": "Legal", "title": "VP Legal"},
    "dasovich-j": {"name": "Jeff Dasovich", "dept": "Government Affairs", "title": "Director"},
    "delainey-d": {"name": "David Delainey", "dept": "Trading", "title": "CEO Enron Americas"},
    "derrick-j": {"name": "James Derrick", "dept": "Legal", "title": "General Counsel"},
    "fastow-a": {"name": "Andrew Fastow", "dept": "Finance", "title": "CFO"},
    "germany-c": {"name": "Chris Germany", "dept": "Trading", "title": "Trader"},
    "haedicke-m": {"name": "Mark Haedicke", "dept": "Legal", "title": "General Counsel"},
    "kaminski-v": {"name": "Vince Kaminski", "dept": "Research", "title": "MD Research"},
    "kean-s": {"name": "Steven Kean", "dept": "Government Affairs", "title": "EVP"},
    "kitchen-l": {"name": "Louise Kitchen", "dept": "Trading", "title": "President EnronOnline"},
    "lavorato-j": {"name": "John Lavorato", "dept": "Trading", "title": "CEO Enron Americas"},
    "lay-k": {"name": "Kenneth Lay", "dept": "Executive", "title": "CEO"},
    "mann-k": {"name": "Kay Mann", "dept": "Legal", "title": "Senior Counsel"},
    "mcconnell-m": {"name": "Mike McConnell", "dept": "Executive", "title": "EVP"},
    "presto-k": {"name": "Kevin Presto", "dept": "Trading", "title": "VP Trading"},
    "sanders-r": {"name": "Richard Sanders", "dept": "Legal", "title": "VP Legal"},
    "shackleton-s": {"name": "Sara Shackleton", "dept": "Legal", "title": "VP Legal"},
    "shapiro-r": {"name": "Richard Shapiro", "dept": "Government Affairs", "title": "VP"},
    "skilling-j": {"name": "Jeffrey Skilling", "dept": "Executive", "title": "CEO"},
    "taylor-m": {"name": "Mark Taylor", "dept": "Legal", "title": "VP Legal"},
    "whalley-g": {"name": "Greg Whalley", "dept": "Executive", "title": "President"},
}


def load_enron_data(data_dir: str = "data/enron", max_emails: int = 50000) -> Tuple[TRKGStore, Dict]:
    """
    Load real Enron email data into T-RKG store.
    
    Returns:
        Tuple of (store, stats_dict)
    """
    import email
    import hashlib
    import re
    
    data_path = Path(data_dir)
    store = TRKGStore()
    
    stats = {
        "emails_processed": 0,
        "emails_skipped": 0,
        "threads_found": 0,
        "attachments_found": 0,
        "custodians": 0,
        "is_real_data": True,
    }
    
    # Track for relationship building
    message_id_to_record = {}
    in_reply_to_map = defaultdict(list)
    
    print(f"  Loading Enron emails from {data_path}...")
    
    # Add custodians
    for emp_id, info in ENRON_EMPLOYEES.items():
        custodian = Custodian(
            id=f"enron_{emp_id}",
            name=info["name"],
            email=f"{emp_id.replace('-', '.')}@enron.com",
            department=info["dept"],
            title=info["title"],
            jurisdiction=Jurisdiction.US,
            start_date=datetime(1995, 1, 1),
            end_date=datetime(2001, 12, 2),
        )
        store.add_custodian(custodian)
        stats["custodians"] += 1
    
    # Add Enron litigation matters
    matters = [
        Matter(
            id="matter_sec_enron",
            name="SEC v. Enron Corporation",
            matter_type="REGULATORY",
            hold_start=datetime(2001, 10, 22),
            custodian_ids=[f"enron_{e}" for e in ["fastow-a", "skilling-j", "lay-k"]],
            keywords=["accounting", "SPE", "fraud"],
        ),
        Matter(
            id="matter_doj_enron",
            name="United States v. Enron",
            matter_type="LITIGATION",
            hold_start=datetime(2002, 1, 9),
            custodian_ids=[f"enron_{e}" for e in ENRON_EMPLOYEES.keys()],
            keywords=["fraud", "obstruction"],
        ),
    ]
    for matter in matters:
        store.add_matter(matter)
    
    # Parse emails
    email_count = 0
    for custodian_dir in sorted(data_path.iterdir()):
        if not custodian_dir.is_dir():
            continue
        
        custodian_id = custodian_dir.name
        if custodian_id not in ENRON_EMPLOYEES:
            # Still process, just use generic custodian
            pass
        
        for root, dirs, files in os.walk(custodian_dir):
            for fname in files:
                if fname.startswith('.'):
                    continue
                
                if email_count >= max_emails:
                    break
                
                filepath = Path(root) / fname
                
                try:
                    with open(filepath, 'r', errors='ignore') as f:
                        msg = email.message_from_file(f)
                    
                    # Extract headers
                    subject = msg.get('Subject', '(no subject)')[:200]
                    date_str = msg.get('Date', '')
                    message_id = msg.get('Message-ID', '')
                    in_reply_to = msg.get('In-Reply-To', '')
                    
                    # Parse date
                    created = parse_email_date(date_str)
                    if not created:
                        stats["emails_skipped"] += 1
                        continue
                    
                    # Generate record ID
                    record_id = f"enron_{hashlib.md5(str(filepath).encode()).hexdigest()[:12]}"
                    
                    # Detect content characteristics
                    body = get_email_body(msg)
                    contains_pii = detect_pii(body)
                    is_financial = is_financial_content(subject, body)
                    
                    # Create record
                    record = Record(
                        id=record_id,
                        type=RecordType.EMAIL,
                        title=subject,
                        created=created,
                        modified=created,
                        custodian_id=f"enron_{custodian_id}" if custodian_id in ENRON_EMPLOYEES else f"enron_unknown",
                        system_id="sys_enron_email",
                        contains_pii=contains_pii,
                        jurisdiction=Jurisdiction.US,
                        metadata={
                            "message_id": message_id,
                            "in_reply_to": in_reply_to,
                            "is_financial": is_financial,
                            "is_public_company": True,
                            "source": "enron_corpus",
                            "folder": str(filepath.parent.name),
                        },
                    )
                    
                    store.add_record(record)
                    email_count += 1
                    stats["emails_processed"] += 1
                    
                    # Track for threading - normalize Message-IDs (strip angle brackets and whitespace)
                    def normalize_msg_id(mid):
                        if not mid:
                            return ''
                        return mid.strip().strip('<>').strip()
                    
                    if message_id:
                        normalized_id = normalize_msg_id(message_id)
                        if normalized_id:
                            message_id_to_record[normalized_id] = record_id
                    if in_reply_to:
                        normalized_reply = normalize_msg_id(in_reply_to)
                        if normalized_reply:
                            in_reply_to_map[normalized_reply].append(record_id)
                    
                    if email_count % 10000 == 0:
                        print(f"    Processed {email_count:,} emails...")
                
                except Exception as e:
                    stats["emails_skipped"] += 1
            
            if email_count >= max_emails:
                break
        
        if email_count >= max_emails:
            break
    
    # Build thread relationships
    print(f"  Building thread relationships...")
    print(f"    Message-IDs tracked: {len(message_id_to_record)}")
    print(f"    In-Reply-To references: {len(in_reply_to_map)}")
    
    # Method 1: In-Reply-To header (if available)
    for parent_msg_id, reply_record_ids in in_reply_to_map.items():
        parent_record_id = message_id_to_record.get(parent_msg_id)
        if not parent_record_id:
            continue
        
        for reply_id in reply_record_ids:
            rel = Relationship(
                id=f"rel_thread_{parent_record_id}_{reply_id}",
                source_id=parent_record_id,
                target_id=reply_id,
                relation_type=RelationType.THREAD,
                valid_from=store.records[reply_id].created,
            )
            store.add_relationship(rel)
            stats["threads_found"] += 1
    
    # Method 2: Subject-line inference (Re: and Fw: patterns)
    # This is needed for Enron which lacks In-Reply-To headers
    print(f"    Inferring threads from subject lines (Re:/Fw: patterns)...")
    
    import re
    
    # Group emails by normalized subject (without Re:/Fw: prefixes)
    def normalize_subject(subj):
        # Remove Re:, Fw:, Fwd:, RE:, FW: etc.
        cleaned = re.sub(r'^(re|fw|fwd|fw|Re|Fw|Fwd|RE|FW|FWD)[\s]*:[\s]*', '', subj.strip())
        cleaned = re.sub(r'^(re|fw|fwd|fw|Re|Fw|Fwd|RE|FW|FWD)[\s]*:[\s]*', '', cleaned)  # Handle double Re: Re:
        return cleaned.strip().lower()[:100]  # Normalize case and limit length
    
    subject_groups = defaultdict(list)
    for record_id, record in store.records.items():
        norm_subj = normalize_subject(record.title)
        if norm_subj:  # Skip empty subjects
            subject_groups[norm_subj].append((record_id, record.created, record.title))
    
    # Create thread relationships within each subject group
    inferred_threads = 0
    for norm_subj, emails in subject_groups.items():
        if len(emails) < 2:
            continue
        
        # Sort by date
        emails.sort(key=lambda x: x[1])
        
        # Link sequential emails in thread (only if they have Re:/Fw: indicators)
        for i in range(1, len(emails)):
            curr_id, curr_date, curr_title = emails[i]
            prev_id, prev_date, prev_title = emails[i-1]
            
            # Only link if current email has Re: or Fw: prefix
            if re.match(r'^(re|fw|fwd|Re|Fw|Fwd|RE|FW|FWD)[\s]*:', curr_title):
                rel = Relationship(
                    id=f"rel_thread_inferred_{prev_id}_{curr_id}",
                    source_id=prev_id,
                    target_id=curr_id,
                    relation_type=RelationType.THREAD,
                    valid_from=curr_date,
                    metadata={"inference": "subject_pattern"}
                )
                store.add_relationship(rel)
                inferred_threads += 1
    
    stats["threads_found"] += inferred_threads
    print(f"    In-Reply-To threads: {stats['threads_found'] - inferred_threads}")
    print(f"    Subject-inferred threads: {inferred_threads}")
    print(f"  Loaded {stats['emails_processed']:,} emails, {stats['threads_found']:,} thread relationships")
    
    return store, stats


def parse_email_date(date_str: str) -> Optional[datetime]:
    """Parse email date string."""
    import re
    
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
            return datetime.strptime(date_str[:30], fmt)
        except ValueError:
            continue
    
    return None


def get_email_body(msg) -> str:
    """Extract email body text."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode('utf-8', errors='ignore')
        return ""
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode('utf-8', errors='ignore')
        return str(msg.get_payload())


def detect_pii(text: str) -> bool:
    """Detect PII in text."""
    import re
    patterns = [
        r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
        r'\b\d{3}[-.]\d{3}[-.]\d{4}\b',  # Phone
        r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b',  # Credit card
    ]
    for pattern in patterns:
        if re.search(pattern, text):
            return True
    return False


def is_financial_content(subject: str, body: str) -> bool:
    """Detect financial content."""
    keywords = [
        'financial', 'accounting', 'revenue', 'earnings', 'profit',
        'balance sheet', 'income statement', 'audit', 'quarter',
        'SEC', '10-K', '10-Q', 'GAAP', 'mark-to-market', 'SPE',
    ]
    text = (subject + ' ' + body).lower()
    return any(kw in text for kw in keywords)


# =============================================================================
# ICEWS DATA LOADER
# =============================================================================

def load_icews_data(data_dir: str = "data/icews", max_facts: int = 50000) -> Tuple[TRKGStore, Dict]:
    """
    Load ICEWS temporal knowledge graph data.
    
    ICEWS format: subject \t relation \t object \t timestamp
    
    We convert this to T-RKG format treating events as records.
    """
    data_path = Path(data_dir)
    store = TRKGStore()
    
    stats = {
        "facts_processed": 0,
        "entities": set(),
        "relations": set(),
        "is_real_data": True,
    }
    
    print(f"  Loading ICEWS data from {data_path}...")
    
    fact_count = 0
    for split in ["train", "valid", "test"]:
        filepath = data_path / f"{split}.txt"
        if not filepath.exists():
            continue
        
        with open(filepath, 'r') as f:
            for line in f:
                if fact_count >= max_facts:
                    break
                
                parts = line.strip().split('\t')
                if len(parts) != 4:
                    continue
                
                subject, relation, obj, timestamp = parts
                
                # Parse timestamp (ICEWS uses YYYY-MM-DD)
                try:
                    created = datetime.strptime(timestamp, "%Y-%m-%d")
                except:
                    continue
                
                # Create record for this event
                record = Record(
                    id=f"icews_{fact_count:08d}",
                    type=RecordType.OTHER,
                    title=f"{subject} {relation} {obj}",
                    created=created,
                    modified=created,
                    jurisdiction=Jurisdiction.GLOBAL,
                    metadata={
                        "subject": subject,
                        "relation": relation,
                        "object": obj,
                        "source": "icews14",
                    },
                )
                store.add_record(record)
                
                stats["facts_processed"] += 1
                stats["entities"].add(subject)
                stats["entities"].add(obj)
                stats["relations"].add(relation)
                
                fact_count += 1
    
    stats["entities"] = len(stats["entities"])
    stats["relations"] = len(stats["relations"])
    
    print(f"  Loaded {stats['facts_processed']:,} facts, {stats['entities']} entities, {stats['relations']} relations")
    
    return store, stats


# =============================================================================
# EXPERIMENTS
# =============================================================================

def run_experiments(store: TRKGStore, data_stats: Dict) -> Dict[str, Any]:
    """Run all T-RKG experiments on the given store."""
    
    results = {
        "metadata": {
            "run_date": datetime.now().isoformat(),
            "is_real_data": data_stats.get("is_real_data", False),
            "data_source": data_stats,
        }
    }
    
    print("\n" + "=" * 70)
    print("  RUNNING T-RKG EXPERIMENTS")
    print("=" * 70)
    
    # RQ1: Dataset characteristics
    print("\n  [RQ1] Dataset Characteristics")
    stats = store.get_statistics()
    results["dataset"] = {
        "records": stats["total_records"],
        "relationships": stats["total_relationships"],
        "custodians": stats["total_custodians"],
        "matters": stats["total_matters"],
    }
    print(f"    Records: {stats['total_records']:,}")
    print(f"    Relationships: {stats['total_relationships']:,}")
    
    # RQ2: Typed Hold Propagation
    print("\n  [RQ2] Typed Hold Propagation")
    
    # Get seed records
    if store.matters:
        matter = list(store.matters.values())[0]
        print(f"    Using matter: {matter.name}")
        print(f"    Matter custodian_ids: {matter.custodian_ids[:5]}...")
        
        # Debug: check what custodian_ids are in records
        record_custodians = set(r.custodian_id for r in store.records.values())
        print(f"    Unique custodians in records: {list(record_custodians)[:5]}...")
        
        seeds = [r.id for r in store.records.values() 
                 if r.custodian_id in matter.custodian_ids][:100]
        print(f"    Seeds from matter custodians: {len(seeds)}")
        
        # If no seeds from matter, just take some records
        if not seeds:
            print(f"    No seeds from matter custodians, using first 100 records")
            seeds = list(store.records.keys())[:100]
    else:
        seeds = list(store.records.keys())[:100]
    
    propagation_results = []
    configs = [
        ("No propagation", [], 0),
        ("THREAD only", [RelationType.THREAD], 10),
        ("ATTACHMENT only", [RelationType.ATTACHMENT], 10),
        ("THREAD + ATTACHMENT", [RelationType.ATTACHMENT, RelationType.THREAD], 10),
        ("All types", list(RelationType), 10),
    ]
    
    for name, rel_types, depth in configs:
        if rel_types:
            propagated = store.propagate_hold(seeds, rel_types, max_depth=depth)
        else:
            propagated = set(seeds)
        
        result = {
            "strategy": name,
            "seeds": len(seeds),
            "propagated": len(propagated),
            "expansion": round(len(propagated) / len(seeds), 2) if seeds else 0,
        }
        propagation_results.append(result)
        print(f"    {name}: {len(seeds)} → {len(propagated)} ({result['expansion']}x)")
    
    results["typed_propagation"] = propagation_results
    
    # Calculate over-inclusion
    typed_count = propagation_results[3]["propagated"]  # THREAD + ATTACHMENT
    untyped_count = propagation_results[4]["propagated"]  # All types
    over_inclusion = untyped_count - typed_count
    results["over_inclusion_avoided"] = over_inclusion
    print(f"    Over-inclusion avoided: {over_inclusion} records")
    
    # RQ3: Conflict Detection
    print("\n  [RQ3] Cross-Jurisdictional Conflict Detection")
    detector = ConflictDetector(store)
    
    start = time.time()
    conflicts = detector.detect_all_conflicts()
    detection_time = (time.time() - start) * 1000
    
    summary = detector.get_conflict_summary()
    results["conflict_detection"] = {
        "total_conflicts": summary["total_conflicts"],
        "affected_records": summary["affected_records"],
        "by_severity": summary["by_severity"],
        "by_regulation_pair": summary["by_regulation_pair"],
        "detection_time_ms": round(detection_time, 2),
    }
    
    print(f"    Total conflicts: {summary['total_conflicts']}")
    print(f"    Critical: {summary.get('critical_count', 0)}")
    for pair, count in list(summary["by_regulation_pair"].items())[:5]:
        print(f"      {pair}: {count}")
    
    # RQ4: Retention Reasoning
    print("\n  [RQ4] Multi-Regulation Retention Reasoning")
    calculator = RetentionCalculator(store)
    
    retention_stats = {
        "with_retention": 0,
        "multi_regulation": 0,
        "by_regulation": defaultdict(int),
    }
    
    for record in store.records.values():
        deadline, rules = calculator.calculate_retention_deadline(record)
        if deadline:
            retention_stats["with_retention"] += 1
            if len(rules) >= 2:
                retention_stats["multi_regulation"] += 1
            for rule in rules:
                reg = rule.split(":")[0]
                retention_stats["by_regulation"][reg] += 1
    
    results["retention_reasoning"] = {
        "with_retention": retention_stats["with_retention"],
        "multi_regulation": retention_stats["multi_regulation"],
        "by_regulation": dict(retention_stats["by_regulation"]),
    }
    
    print(f"    Records with retention: {retention_stats['with_retention']:,}")
    print(f"    Multi-regulation: {retention_stats['multi_regulation']:,}")
    
    # RQ5: Explainability
    print("\n  [RQ5] Explainable Governance Decisions")
    reasoner = GovernanceReasoner(store)
    
    start = time.time()
    reasoning_stats = reasoner.get_reasoning_statistics()
    reasoning_time = time.time() - start
    
    results["explainability"] = {
        "total_records": len(store.records),
        "reasoning_time_ms": round(reasoning_time * 1000, 1),
        "time_per_record_ms": round(reasoning_time * 1000 / len(store.records), 3) if store.records else 0,
        "records_with_retention": reasoning_stats.records_with_retention,
        "records_with_deletion_rights": reasoning_stats.records_with_deletion_rights,
        "records_with_conflicts": reasoning_stats.records_with_conflicts,
    }
    
    print(f"    Reasoning time: {reasoning_time*1000:.1f}ms ({reasoning_time*1000/len(store.records):.3f}ms/record)")
    print(f"    Records with conflicts: {reasoning_stats.records_with_conflicts}")
    
    return results


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Run T-RKG experiments with real data")
    parser.add_argument("--dataset", choices=["enron", "icews", "synthetic"], default="enron",
                        help="Dataset to use")
    parser.add_argument("--max-records", type=int, default=50000,
                        help="Maximum records to load")
    parser.add_argument("--output", type=str, default="real_data_results.json",
                        help="Output file for results")
    parser.add_argument("--skip-download", action="store_true",
                        help="Skip download, assume data exists")
    args = parser.parse_args()
    
    print("\n" + "=" * 70)
    print("  T-RKG REAL DATA EXPERIMENTS")
    print("=" * 70)
    
    # Download data
    if args.dataset == "enron":
        if not args.skip_download:
            downloader = EnronDownloader()
            if not downloader.download():
                print("Failed to download Enron data. Use --skip-download if data exists.")
                return
        
        store, data_stats = load_enron_data(max_emails=args.max_records)
        
    elif args.dataset == "icews":
        if not args.skip_download:
            downloader = ICEWSDownloader()
            if not downloader.download():
                print("Failed to download ICEWS data.")
                return
        
        store, data_stats = load_icews_data(max_facts=args.max_records)
        
    else:  # synthetic
        print("  Using synthetic data...")
        store = SyntheticDataGenerator(GeneratorConfig(), seed=42).generate()
        data_stats = {"is_real_data": False, "source": "synthetic"}
    
    # Run experiments
    results = run_experiments(store, data_stats)
    
    # Save results
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n  Results saved to: {args.output}")
    
    # Print summary
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"""
  Dataset: {args.dataset.upper()} ({'REAL' if data_stats.get('is_real_data') else 'SYNTHETIC'})
  Records: {results['dataset']['records']:,}
  Relationships: {results['dataset']['relationships']:,}
  
  Key Findings:
  - Typed propagation expansion: {results['typed_propagation'][3]['expansion']}x
  - Over-inclusion avoided: {results['over_inclusion_avoided']} records
  - Conflicts detected: {results['conflict_detection']['total_conflicts']}
  - Multi-regulation records: {results['retention_reasoning']['multi_regulation']:,}
  - Reasoning time: {results['explainability']['time_per_record_ms']:.3f}ms/record
    """)


if __name__ == "__main__":
    main()
