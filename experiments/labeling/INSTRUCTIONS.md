# E4 Applicability Labeling — Instructions

You are labeling, for each record, which of the nine regulations **apply** to it,
using only the attributes shown in the row. Work from `E4_labeling_sheet.csv`.

**For every row, fill each of the nine regulation columns** — `GDPR`, `CPRA`,
`PIPEDA`, `HIPAA`, `SOX`, `SEC`, `FINRA`, `IRS`, `HGB` — with `TRUE` if that
regulation applies to the record, or `FALSE` if it does not. Decide from the
attributes in that same row only: `record_type`, `jurisdiction`, `PII`, `PHI`,
and `public_company`. Do not leave a regulation cell blank. If you are genuinely
unsure about a row after considering its attributes, put a short note in the
`unsure` column and still give your best TRUE/FALSE for every regulation.

Do **not** open, consult, or cross-reference any other file (no reference key,
no ground-truth file, no source code). Label independently from your own reading
of each row's attributes — that independence is the whole point of the exercise.

Save your filled sheet under a new name (e.g. `annotator_a.csv`); leave
`E4_labeling_sheet.csv` itself as the blank template.
