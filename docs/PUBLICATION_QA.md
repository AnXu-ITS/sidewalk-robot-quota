# Repository publication QA — 19 September 2026

A clean export of the staged Git tree passed verification without access to the original workspace paths:

- 1,600 frozen recommendations reproduced.
- 315 unique positive-flow groups and 9,450 seed decisions checked; no independent replication seeds in the primary analysis; UNTESTED = 0.
- Three service-boundary tests passed.
- Figure generation passed in the isolated export.
- LaTeX compilation passed without undefined references or overfull boxes; 12 pages. Extracted text matches the submitted PDF exactly.
- The published PDF is byte-identical to the final CICPT2027 PDF.
- No simulations or reference refits were launched for repository publication. The optional SUMO execution path is documented but was not newly executed.

The earlier page-by-page paper inspection is recorded in `audits/FINAL_SUBMISSION_QA.md`. This publication check preserves that approved manuscript and its figures. Full raw logs remain local; published per-seed metrics support the lightweight verification described in REPRODUCIBILITY.md.

GitHub Actions was not enabled: the current OAuth credential lacks workflow scope. `verify-workflow-template.yml` preserves the optional configuration; all reported checks were run locally.
