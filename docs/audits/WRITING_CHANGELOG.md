# Writing changelog

- Reframed the paper from a formula-superiority claim to an interpretable segment-level admission framework that balances pedestrian service and robot access.
- Reconstructed the reference and downstream writing derivatives using original seeds 0--29; independent replication seeds remain separate. No new simulation was launched.
- Corrected throughput handling: completed arrivals divided by completed departures is undefined at a zero denominator and is never imputed to one. Added denominator and demand-execution diagnostics.
- Replaced stale V2 values in macros, tables, results and figures with V3-derived values. Five q-star labels changed; all downstream descriptive outputs were regenerated.
- Made M0/M1 the first main result, including positive/zero recommendations, direct-flow PASS/FAIL/UNTESTED, mean candidate rate, utilization and denominator n. Added common-positive and withdrawn-access decomposition.
- Added M0/M2/M3 comparison without equivalence or no-performance-loss language.
- Reported Hong Kong 13 original and 5 entrance-repaired configurations separately. Clarified that shape retention does not preserve entrance placement and that this is simulation geometry transfer, not field validation.
- Restored the original Figure 1 and Figure 2 visual grammar with Figure 1 typography. Figure 2 now combines the compact baseline/mixed-flow schematic, a reference scan and P/F/UNTESTED/Z outcome bars. Figure 3 carries the Hong Kong transfer.
- Deleted the Data and Code chapter. Removed historical raw-log warnings and unsupported superiority, universal capacity, guarantee, field-validation and feedback-control implications.
- Preserved nonmonotonic replication, robot-size and direction-ratio sensitivity results as applicability diagnostics.
- Kept eight corrected candidate flows explicitly UNTESTED because the user instructed this pass not to launch new simulations; these are not counted as PASS.
- Compiled the ASCE manuscript to 12 pages and completed page-image inspection, citation/reference checks, overfull-box checks and figure readability checks.

## Final narrative rewrite
- Rewrote the full paper around the segment admission problem and moved limitations to Discussion.
- Corrected writing-only cell/censoring/subset macros and Figure 2 zero-bar rendering; no simulation or refitting.
- Final PDF is 11 pages within the 12-page limit; see NARRATIVE_REWRITE_REPORT.md.


## Final submission completion
Completed 6 missing unique groups (180 original-seed runs), reused existing baseline evidence, and resolved all positive exact tests. Re-generated final statuses, continuous summaries, macros and tables without changing references or estimators. Removed audit-count prose and UNTESTED display categories, standardized admission terminology, split five official policy citations, verified the extreme speed observation, and compiled/visually checked 12 pages. FINAL_SUBMISSION_QA.md supersedes earlier pending-test and page-count notes.
