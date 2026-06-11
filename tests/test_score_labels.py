"""Unit tests for the E4 scorer (experiments/labeling/score_labels.py).

Hand-built tiny example: 3 records, a known ground truth, and two annotator
sheets with deliberate agreements/disagreements/blanks so every branch of
score_sheet and cohens_kappa is exercised.
"""

from experiments.labeling.score_labels import (
    _parse_cell,
    score_sheet,
    cohens_kappa,
)


def test_parse_cell():
    assert _parse_cell("TRUE") is True
    assert _parse_cell(" true ") is True
    assert _parse_cell("FALSE") is False
    assert _parse_cell("false") is False
    assert _parse_cell("") is None
    assert _parse_cell("   ") is None
    assert _parse_cell("maybe") is None
    assert _parse_cell(None) is None


# Ground truth: r1 -> {GDPR, SOX}; r2 -> {SOX}; r3 -> {} (nothing applies).
GT = {
    "r1": {"GDPR", "SOX"},
    "r2": {"SOX"},
    "r3": set(),
}


def test_score_sheet_perfect_agreement():
    """A sheet that exactly matches T-RKG -> P=R=F1=1 on firing regs."""
    sheet = {
        "r1": {"GDPR": True, "SOX": True, "CPRA": False, "PIPEDA": False,
               "HIPAA": False, "SEC": False, "FINRA": False, "IRS": False, "HGB": False},
        "r2": {"GDPR": False, "SOX": True, "CPRA": False, "PIPEDA": False,
               "HIPAA": False, "SEC": False, "FINRA": False, "IRS": False, "HGB": False},
        "r3": {"GDPR": False, "SOX": False, "CPRA": False, "PIPEDA": False,
               "HIPAA": False, "SEC": False, "FINRA": False, "IRS": False, "HGB": False},
    }
    res = score_sheet(sheet, GT)
    assert res["overall_agreement"] == 1.0
    assert res["labeled_cells"] == 27  # 3 records x 9 regs, all labeled
    gdpr = res["per_regulation"]["GDPR"]
    assert gdpr["tp"] == 1 and gdpr["fp"] == 0 and gdpr["fn"] == 0
    assert gdpr["precision"] == 1.0 and gdpr["recall"] == 1.0 and gdpr["f1"] == 1.0
    sox = res["per_regulation"]["SOX"]
    assert sox["tp"] == 2 and sox["fp"] == 0 and sox["fn"] == 0
    assert sox["f1"] == 1.0


def test_score_sheet_fp_fn_and_blanks():
    """Mixed sheet: one FP (GDPR on r2), one FN (SOX on r1), blanks skipped."""
    sheet = {
        "r1": {"GDPR": True, "SOX": False},   # SOX FN; others blank
        "r2": {"GDPR": True, "SOX": True},    # GDPR FP; SOX TP
        "r3": {"GDPR": False, "SOX": False},  # both TN
    }
    # Fill remaining regs as blank (None) so only GDPR/SOX are scored.
    res = score_sheet(sheet, GT)
    gdpr = res["per_regulation"]["GDPR"]
    # GDPR truth only on r1. r1=T(tp), r2=T(fp), r3=F(tn).
    assert gdpr["tp"] == 1 and gdpr["fp"] == 1 and gdpr["fn"] == 0 and gdpr["tn"] == 1
    assert gdpr["precision"] == 0.5 and gdpr["recall"] == 1.0
    sox = res["per_regulation"]["SOX"]
    # SOX truth on r1,r2. r1=F(fn), r2=T(tp), r3=F(tn).
    assert sox["tp"] == 1 and sox["fp"] == 0 and sox["fn"] == 1 and sox["tn"] == 1
    assert sox["precision"] == 1.0 and sox["recall"] == 0.5
    # A regulation never labeled anywhere -> precision/recall None, f1 None.
    hipaa = res["per_regulation"]["HIPAA"]
    assert hipaa["precision"] is None and hipaa["recall"] is None and hipaa["f1"] is None


def test_score_sheet_blank_cells_excluded():
    """Blank cells are not counted toward agreement or confusion matrix."""
    sheet = {"r1": {"GDPR": True}}  # only GDPR labeled, rest blank
    res = score_sheet(sheet, GT)
    assert res["labeled_cells"] == 1
    assert res["overall_agreement"] == 1.0  # the single labeled cell agrees


def test_cohens_kappa_perfect():
    a = {"r1": {"GDPR": True, "SOX": True}, "r2": {"GDPR": False, "SOX": True}}
    b = {"r1": {"GDPR": True, "SOX": True}, "r2": {"GDPR": False, "SOX": True}}
    assert cohens_kappa(a, b) == 1.0


def test_cohens_kappa_partial():
    # 4 labeled cells; annotators disagree on exactly one -> po=0.75.
    a = {"r1": {"GDPR": True, "SOX": True, "CPRA": False, "HIPAA": False}}
    b = {"r1": {"GDPR": True, "SOX": False, "CPRA": False, "HIPAA": False}}
    k = cohens_kappa(a, b)
    # a: T,T,F,F (pa_true=.5); b: T,F,F,F (pb_true=.25)
    # pe = .5*.25 + .5*.75 = .5 ; po=.75 ; kappa=(.75-.5)/(1-.5)=.5
    assert abs(k - 0.5) < 1e-9


def test_cohens_kappa_blank_skipped():
    a = {"r1": {"GDPR": True, "SOX": None}}
    b = {"r1": {"GDPR": True, "SOX": True}}
    # Only GDPR comparable -> both TRUE -> perfect by convention.
    assert cohens_kappa(a, b) == 1.0


def test_cohens_kappa_no_overlap_returns_none():
    a = {"r1": {"GDPR": None}}
    b = {"r2": {"GDPR": True}}
    assert cohens_kappa(a, b) is None
