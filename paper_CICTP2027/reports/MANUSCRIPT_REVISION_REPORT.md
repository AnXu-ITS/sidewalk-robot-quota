# Manuscript revision report

## Scope and recoverable starting state

The latest local CICTP manuscript, including the Jin et al. citation and rounded
framework node, was the starting point. Before editing, the full local project
was snapshotted and the existing public Git tree was archived. Starting commit
was `98a738c65213f720549222e1512e64a8cf39b973` and the tracked working tree was clean. Historical D2,
intermediate calibration, previous manuscripts and the original experimental
extension remain intact.

## Before and after

| Item | Before | After |
|---|---:|---:|
| Pages |12|10|
| Figures |3|3|
| Tables |6|3|
| Keywords |6|5|

The final abstract contains 184 words. Official CICTP2027
instructions require at most12 full-paper pages, an English abstract of at most300
words and no more than five keywords. Source checked on8 October2026 at
https://cictp2027.tsinghua.edu.cn/Submission.htm. The existing ASCE class/style,
author information and acknowledgments are retained. The paper was not stretched
to fill12 pages.

## Narrative changes

Introduction now moves from urban delivery use and limited walking space to the
distinction between permits/fleet size and local entry-rate management. Literature
is positioned around operations, regulation, interactions and routing. The
regulatory catalog was shortened; the source BibTeX retains historical entries.
Jin et al. remains only at the shared-evidence/corroboration statement, without
PACT technical background.

Methodology preserves scenario construction, SUMO1.27.1/JuPedSim, robot/pedestrian
properties, time settings, the three service thresholds,29/30 acceptance, finite
reference scanning, applicability, gates, ceilings, model equation, margin
calibration and exact recommendation testing. Independent replication and
transfer protocols remain understandable without the repository. Baseline
qualification follows the current frozen service implementation, rather than the
older D2 mean-based convention. The exact specific-demand limit is shown as100/3;
the underlying configuration is unchanged.

Results are organized around the access–service frontier, walking-speed
constraints, stochastic decision stability and local geometry/operating effects.
Discussion interprets conservative admission as an allocation choice, connects
width to demand and configuration, and states one bounded limitations paragraph.
Conclusion answers the local management question with one decisive comparison.

Figure1 retains the rounded framework. Figure2 is rebuilt from verified margin
data with direct labels and typography consistent with the retained figures.
Figure3 retains genuine stored Hong Kong shapes and rates. The tables now show
essential guardrails, a compact four-rule comparison and operating sensitivity.
The complete five-setting table is not repeated beside the frontier figure.

## Detail moved to the public research record

- All five margin rows, city/fold/scenario recommendations and service outcomes.
- Exact-test cache coverage and new-run accounting.
- Immutable replication sample, original/independent records, matching baselines
  and complete decision transitions.
- Planned/observed/completed/movement/stock diagnostics and interpretation limits.
- Seed-level speed/density/flow failures and full scenario taxonomy.
- All Hong Kong configurations, operating assumptions and exclusions.
- Guardrail construction/provenance, freeze history, parameters and scan support.
- Separate D2/intermediate/CICTP scientific versions and source/export hashes.

## Main claims and numerical integrity

The evaluated population remains164 scenarios. Original M0 remains98 positive,
98 PASS and0 FAIL; M1 remains136 positive,118 PASS and18 FAIL. Margin positives
remain136,129,122,98,58 and failures18,10,5,0,0. The32 passing opportunities among
38 withheld are retained. Replication remains13/13 unchanged M0 and7/15 M1.
Speed is involved in all18 original M1 failure groups and dominates17. Hong Kong
retains13 original and five repaired configurations.

No threshold, seed, frozen reference, candidate recommendation, physical assumption
or scientific outcome was changed. No new scientific simulation, E6 or E7 was run.
No confidence interval, population reliability or causal traffic mechanism was
invented. Completed-record balance is not presented as demand fulfillment; fixed
development rules are not described as independently selected in every city fold.

## Validation and visual inspection

The complete local project compiles with pdfLaTeX/BibTeX. Final log has no undefined
references/citations, overflow or oversized floats. All10 rendered pages were
inspected, with detailed checks of the framework, frontier, real geometry,
three tables, equations and references. Results floats are flushed before
Discussion; the References heading stays with entries. All three final figure
PDFs pass glyph/collision audits. Source preflight passes; inherited ASCE width
and300dpi preview warnings are documented rather than applying Nature dimensions.
Color is restrained and markers/text also distinguish series in grayscale.

One isolated-context CICTP narrative self-check found no blocking/Major concern.
Its three minor method clarifications were addressed. This is not external peer
review or an editorial acceptance decision.

Numerical reproduction, figure/table generation, compilation and package
validation were tested from a clean standalone copy. Existing service-boundary
unit tests also pass. Developer paths and potential credentials are absent from
the public package. 90 original public science/publication files are
verified byte-identical. Data Availability points to the named versioned research
release rather than a moving default branch.
