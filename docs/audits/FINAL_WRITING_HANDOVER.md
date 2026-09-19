# Final writing handover

The stable narrative connects operating permission to the segment entry-rate decision, then evaluates applicability, pedestrian-service gates, candidate rates, conservative allocation and transfer limits. Contributions remain the interpretable decision structure, direct access–service comparison and configuration-dependent geometric transfer. No superiority, equivalence, universal capacity, field-validation or below-rate guarantee is claimed.

FINAL_SUBMISSION_QA.md is the authoritative current A–K acceptance report. All positive recommendations have complete direct tests; references, coefficients, margins and predictions are frozen. FINAL_RESULTS.json in submission_final/ drives the numerical outputs. The earlier unresolved-test statements are superseded.

Authoritative manuscript: ascexmpl-new.tex and ascexmpl-new.pdf; bibliography: ascexmpl-new.bib; figures: figures/figure1–3.pdf plus SVG/PNG; automatic numerical macros/tables: generated/. Evidence matrix: EVIDENCE_CLAIM_MATRIX.csv. Exact-flow results, unique queue, per-seed decisions, checksums, policy metadata, extreme-value audit and generating scripts: submission_final/.

Methods no longer lists raw-audit totals or repair history. Terminology is unified; five official policy sources replace the synthetic citation. Model simplification, specified demand, completed-trip counting, finite seeds/flow scan and lack of field validation remain explicit limitations. Data and Code remains removed.

The complete 12-page PDF was compiled and every page visually inspected; no undefined references or overfull boxes. Build from this directory: pdflatex -interaction=nonstopmode -halt-on-error ascexmpl-new.tex; bibtex ascexmpl-new; pdflatex twice. Source uses explicit figures/ paths. No further narrative rewrite is pending.
