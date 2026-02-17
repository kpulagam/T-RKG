#!/usr/bin/env python3
"""Debug script to check why thread relationships aren't being found."""

import os
import email
from pathlib import Path
from collections import defaultdict

data_path = Path("data/enron")

message_ids = []
in_reply_tos = []
references = []

print("Scanning first 1000 emails for Message-ID patterns...")

count = 0
for custodian_dir in sorted(data_path.iterdir()):
    if not custodian_dir.is_dir():
        continue
    
    for root, dirs, files in os.walk(custodian_dir):
        for fname in files:
            if fname.startswith('.'):
                continue
            if count >= 1000:
                break
            
            filepath = Path(root) / fname
            try:
                with open(filepath, 'r', errors='ignore') as f:
                    msg = email.message_from_file(f)
                
                msg_id = msg.get('Message-ID', '')
                in_reply = msg.get('In-Reply-To', '')
                refs = msg.get('References', '')
                
                if msg_id:
                    message_ids.append(msg_id)
                if in_reply:
                    in_reply_tos.append(in_reply)
                if refs:
                    references.append(refs)
                
                count += 1
            except:
                pass
        
        if count >= 1000:
            break
    if count >= 1000:
        break

print(f"\nScanned {count} emails")
print(f"Emails with Message-ID: {len(message_ids)}")
print(f"Emails with In-Reply-To: {len(in_reply_tos)}")
print(f"Emails with References: {len(references)}")

print("\n--- Sample Message-IDs (first 5) ---")
for mid in message_ids[:5]:
    print(f"  '{mid}'")

print("\n--- Sample In-Reply-To (first 5) ---")
for irt in in_reply_tos[:5]:
    print(f"  '{irt}'")

# Check for matches
print("\n--- Checking for matches ---")
msg_id_set = set(message_ids)
matches = 0
for irt in in_reply_tos:
    if irt in msg_id_set:
        matches += 1
        
print(f"Direct matches: {matches} / {len(in_reply_tos)}")

# Try stripping angle brackets
def normalize(s):
    return s.strip().strip('<>').strip()

msg_id_normalized = set(normalize(m) for m in message_ids)
matches_normalized = 0
for irt in in_reply_tos:
    if normalize(irt) in msg_id_normalized:
        matches_normalized += 1

print(f"Matches after normalizing: {matches_normalized} / {len(in_reply_tos)}")

# Check if In-Reply-To might reference external emails
print("\n--- In-Reply-To domain analysis ---")
domains = defaultdict(int)
for irt in in_reply_tos:
    if '@' in irt:
        domain = irt.split('@')[-1].rstrip('>')
        domains[domain] += 1

print("Top domains in In-Reply-To:")
for domain, cnt in sorted(domains.items(), key=lambda x: -x[1])[:10]:
    print(f"  {domain}: {cnt}")
