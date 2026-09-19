# FINAL_SUBMISSION_QA

## A. Unique additional groups
6 new scenario–configuration–flow groups: five development and one Hong Kong original. Queue: FINAL_UNTESTED_QUEUE.csv. One further previously untested development flow was resolved from existing complete raw evidence; two methods share it. There are 315 unique directly tested positive flow groups overall.

## B. New seed runs
180 new runs, all exit code 0 and COMPLETED_DIAGNOSTIC, seeds 0–29. No baseline reruns. Methods share identical flow evidence. Raw files, merged stdout/stderr (sumo.log), simulator error log, inputs, routes, trajectories, trip records, demand diagnostics and hashes are preserved under revision_review/runs/<spec_hash>. NEW_RAW_HASH_MANIFEST.csv verifies the new files; exact_seed_service_final.csv records metrics, seed decisions and matching baseline hashes. No references, fits, margins, thresholds or recommendations were changed (frozen hashes checked).

## C. Final development results
| Method | Positive | Zero | PASS | FAIL | Exceed | MAE | U (%) | Mean positive flow |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| M0 | 98 | 66 | 98 | 0 | 0 | 4.54 | 16.7 | 4.81 |
| M1 | 136 | 28 | 118 | 18 | 16 | 2.43 | 75.0 | 6.32 |
| M2 | 59 | 105 | 59 | 0 | 0 | 6.98 | 0.0 | 1.19 |
| M3 | 98 | 66 | 96 | 2 | 2 | 4.55 | 18.2 | 4.83 |

All methods use 164 scenarios from 64 cells. Candidate sample: 400 scenarios, 140 cells. Exceedance and MAE use all evaluated scenarios; U uses 139 positive references and includes zero recommendations. Rates and MAE are robots/min. Reference-based metrics and bootstrap intervals equal the frozen pre-completion outputs.

Common-positive subset: 98 scenarios; M0 98 PASS/0 FAIL, M1 86 PASS/12 FAIL; mean candidate rates 4.81 and 7.55 robots/min.

## D. Untested status
UNTESTED = 0 and INCOMPLETE = 0 for M0–M3. All Hong Kong positive recommendations are tested. Positive = PASS + FAIL throughout; zero admission is never counted as PASS. The paper, tables and Figure 2 contain no UNTESTED category or unresolved-test statements.

## E. Additional access when removing the margin
M0 = 0 and M1 > 0: 38 scenarios, 32 PASS and 6 FAIL. Recomputed from frozen predictions joined to final exact-flow results.

## F. Hong Kong
| Configuration | Method | Positive | Zero | PASS | FAIL | Exceed | U (%) | U denominator |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| ORIGINAL | M0 | 7 | 6 | 7 | 0 | 0 | 16.7 | 10 |
| ORIGINAL | M1 | 11 | 2 | 10 | 1 | 1 | 64.6 | 10 |
| ORIGINAL | M2 | 7 | 6 | 7 | 0 | 0 | 8.3 | 10 |
| ORIGINAL | M3 | 7 | 6 | 7 | 0 | 0 | 16.7 | 10 |
| REPAIRED | M0 | 4 | 1 | 4 | 0 | 0 | 20.0 | 5 |
| REPAIRED | M1 | 5 | 0 | 5 | 0 | 0 | 50.0 | 5 |
| REPAIRED | M2 | 2 | 3 | 2 | 0 | 0 | 0.0 | 5 |
| REPAIRED | M3 | 4 | 1 | 4 | 0 | 0 | 20.0 | 5 |

Original and repaired strata remain separate; shapes and candidate point positions are unchanged. This is simulation geometry transfer, not field validation or a new blind test.

## G. Methods cleanup
Removed precise baseline/mixed-flow raw-audit record counts from the paper; retained internal diagnostic files. The paper states the final undefined-denominator rule, seed blocks, service criterion, reference definition, gates, margin and test design. No historical repair narrative or Data and Code section remains.

## H. Policy references
Five independent official entries: Virginia General Assembly (2020 amendment; Code §46.2-908.1:1), Washington State Legislature (2019; RCW 46.75.020), LTA (page updated 2022), IMDA (11 March 2021 trial notice), DDOT (16 July 2026 permit notice). Titles, date bases, agencies, URLs and access date are recorded in POLICY_SOURCES_VERIFIED.json. Five clickable official-source links are present in the PDF. IMDA release text was verified via the official-domain search index after direct page retrieval timed out. The synthetic authority citation is removed.

## I. Terminology
Core terms: candidate entry rate (q_cand), positive recommendation, zero admission, abstention. Figure 1 uses Abstain, Zero admission and Candidate entry rate. Flow ceiling refers only to imposed bounds. No q_op, zero quota or operational quota appears in the rendered paper. Service language is varied without changing the criteria. Figure 2 keeps only PASS/FAIL/ZERO.

## J. Extreme speed-retention check
DC-111|qp32.4, M1, 2 robots/min, seed 12: recomputed retention 0.071190625979; mean speed 0.080887103912 m/s divided by matching 30-seed baseline mean 1.136204420170 m/s. Exit code 0; all stored hashes verified. The 100–340 s window contains 2400 snapshots and 135576 pedestrian observations; no empty-zone snapshots. All 130 planned-window pedestrians and 8 robots were observed and moved by run end. Boundary retries occurred, but no boundary-rejected agent remained unmoved; first movement is a diagnostic proxy, not an exact model-entry timestamp. Pedestrian stock rose from 23 to 135 near window end. Completed-departure denominator = 0, completed arrivals = 19; throughput is undefined and fails. The low observed speed is retained as severe degradation in a technically completed run, not an empty-zone or parsing artifact. See EXTREME_SPEED_RAW_AUDIT.json and extreme_agent_movement.csv.

## K. PDF and compilation QA
12 pages including references; three figures; original class, margins, authors, affiliation and correspondence retained. LaTeX/BibTeX compile successfully; no undefined references/citations, overfull boxes or rerun warnings. All pages 1–12 were rendered and visually inspected. Tables, formulas and figures fit; adverse findings remain. Figure 1 font family/style is retained across figures; vector PDFs and editable SVGs exported. All figure font-floor tests passed and collision audits have zero failures. Figure 2's threshold annotation overlaps only the blank axes background boundary (reviewed, no obstructed text or data). Heterogeneous schematic/data panels are not comparable alignment peers; exemptions are recorded in reports/*.alignment.json. Explicit figures/ paths prevent stale same-name root images from shadowing final plots. MiKTeX emits a maintenance reminder about update checks; it does not affect compilation.
