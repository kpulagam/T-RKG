"""E4 scorer — human applicability labels vs. T-RKG's hidden ground truth.

Given one or more filled labeling sheets (human TRUE/FALSE per regulation) and
`ground_truth_hidden.json` (T-RKG's per-record verdict), this computes:
  (a) per-regulation precision / recall / F1 of human-vs-T-RKG agreement,
  (b) overall cell-level agreement,
  (c) Cohen's kappa between two annotators (when a second sheet is supplied).

T-RKG's verdict is treated as the reference ("truth") for P/R/F1: a positive is
"this regulation applies to this record." Cohen's kappa instead measures the two
HUMAN annotators against each other, chance-corrected.

PREP-ONLY: this script never writes label values. The human columns are filled by
a person; here we only read and score them.

Usage:
    python experiments/labeling/score_labels.py \
        --ground-truth experiments/labeling/ground_truth_hidden.json \
        --sheet annotator_a.csv [--sheet annotator_b.csv]
"""

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List, Optional

# The nine profiled regulations, matching the labeling-sheet columns.
REGULATIONS = ["GDPR", "CPRA", "PIPEDA", "HIPAA", "SOX", "SEC", "FINRA", "IRS", "HGB"]


def load_ground_truth(path: str) -> Dict[str, set]:
    """record_id -> set of regulation codes T-RKG marked applicable."""
    raw = json.loads(Path(path).read_text())
    return {rid: set(v["trkg_regulations"]) for rid, v in raw.items()}


def _parse_cell(value: str) -> Optional[bool]:
    """TRUE/FALSE -> bool; blank/unknown -> None (unlabeled)."""
    s = (value or "").strip().upper()
    if s == "TRUE":
        return True
    if s == "FALSE":
        return False
    return None


def load_sheet(path: str) -> Dict[str, Dict[str, Optional[bool]]]:
    """record_id -> {regulation -> bool|None} from a filled labeling sheet."""
    out: Dict[str, Dict[str, Optional[bool]]] = {}
    with Path(path).open(newline="") as f:
        for row in csv.DictReader(f):
            out[row["record_id"]] = {reg: _parse_cell(row.get(reg, "")) for reg in REGULATIONS}
    return out


def score_sheet(
    sheet: Dict[str, Dict[str, Optional[bool]]],
    ground_truth: Dict[str, set],
) -> dict:
    """Per-regulation P/R/F1 (human vs T-RKG) and overall cell agreement.

    Cells the human left blank are skipped (not counted as TRUE or FALSE).
    """
    per_reg = {}
    agree_cells = 0
    total_cells = 0
    for reg in REGULATIONS:
        tp = fp = fn = tn = 0
        for rid, labels in sheet.items():
            if rid not in ground_truth:
                continue
            human = labels.get(reg)
            if human is None:
                continue  # unlabeled cell — excluded
            truth = reg in ground_truth[rid]
            total_cells += 1
            if human == truth:
                agree_cells += 1
            if human and truth:
                tp += 1
            elif human and not truth:
                fp += 1
            elif (not human) and truth:
                fn += 1
            else:
                tn += 1
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        if precision and recall:
            f1 = 2 * precision * recall / (precision + recall)
        elif precision is None or recall is None:
            f1 = None
        else:
            f1 = 0.0
        per_reg[reg] = {
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": precision, "recall": recall, "f1": f1,
        }
    overall_agreement = agree_cells / total_cells if total_cells else None
    return {"per_regulation": per_reg, "overall_agreement": overall_agreement,
            "labeled_cells": total_cells}


def cohens_kappa(
    sheet_a: Dict[str, Dict[str, Optional[bool]]],
    sheet_b: Dict[str, Dict[str, Optional[bool]]],
) -> Optional[float]:
    """Chance-corrected agreement between two annotators over all labeled cells
    (categories TRUE/FALSE). Cells either annotator left blank are skipped."""
    both = [rid for rid in sheet_a if rid in sheet_b]
    a_labels: List[bool] = []
    b_labels: List[bool] = []
    for rid in both:
        for reg in REGULATIONS:
            av = sheet_a[rid].get(reg)
            bv = sheet_b[rid].get(reg)
            if av is None or bv is None:
                continue
            a_labels.append(av)
            b_labels.append(bv)
    n = len(a_labels)
    if n == 0:
        return None
    po = sum(1 for x, y in zip(a_labels, b_labels) if x == y) / n
    pa_true = sum(a_labels) / n
    pb_true = sum(b_labels) / n
    pe = pa_true * pb_true + (1 - pa_true) * (1 - pb_true)
    if pe == 1.0:
        return 1.0  # both annotators constant and agree -> perfect by convention
    return (po - pe) / (1 - pe)


def _fmt(x):
    return "  n/a" if x is None else f"{x:.3f}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ground-truth", required=True)
    ap.add_argument("--sheet", action="append", required=True,
                    help="filled labeling sheet CSV (repeat for a second annotator)")
    args = ap.parse_args()

    gt = load_ground_truth(args.ground_truth)
    sheets = [load_sheet(p) for p in args.sheet]

    for path, sheet in zip(args.sheet, sheets):
        res = score_sheet(sheet, gt)
        print(f"\n=== {path} vs T-RKG ({res['labeled_cells']} labeled cells) ===")
        print(f"{'reg':8} {'P':>6} {'R':>6} {'F1':>6}   tp/fp/fn/tn")
        for reg in REGULATIONS:
            m = res["per_regulation"][reg]
            print(f"{reg:8} {_fmt(m['precision']):>6} {_fmt(m['recall']):>6} "
                  f"{_fmt(m['f1']):>6}   {m['tp']}/{m['fp']}/{m['fn']}/{m['tn']}")
        print(f"overall cell agreement: {_fmt(res['overall_agreement'])}")

    if len(sheets) >= 2:
        k = cohens_kappa(sheets[0], sheets[1])
        print(f"\nCohen's kappa (annotator 1 vs annotator 2): {_fmt(k)}")


if __name__ == "__main__":
    main()
