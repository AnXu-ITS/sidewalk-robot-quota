# Data coverage and dictionary

Final authority: data/submission/FINAL_RESULTS.json. Files with `_v3` names are the primary-block revision lineage, not the earlier VERIFIED_V2 aggregation. Independent seeds never enter primary calibration.

| File/group | Unit and role |
|---|---|
| reference_dataset_original_block_v3.csv | 400 geometry–demand scenarios and primary baseline/reference status |
| loco_predictions_v3.csv | 1,600 method–scenario candidate recommendations and reasons |
| fit_parameters_v3.csv | City-fold/method coefficients and margins; ALL_DEVELOPMENT applies to Hong Kong |
| exact_flow_validation_v3.csv | Positive development recommendation outcomes |
| hk_analysis_v3.csv | 18 configurations × four methods; ORIGINAL/REPAIRED separate |
| exact_seed_service_final.csv | 9,450 seeds in 315 unique positive-flow groups, shared across methods |
| matched_raw_primary.csv | Matching baseline and positive-flow seed metrics |
| raw_final.csv | Broader primary-seed registry including scan and diagnostic configurations; filter configuration explicitly |
| reference_flow_audit_v3.csv | Frozen scan qualification; later exact tests do not redefine q* |
| decomposition_v3.csv | Common-positive, M0-zero/M1-positive and both-zero subsets |
| NEW_RAW_HASH_MANIFEST.csv | Raw file hashes for final 180-run completion; raw files outside Git |
| FINAL_UNTESTED_QUEUE.csv | Pre-completion queue, not the final count of untested recommendations |
| data/diagnostics/ | Independent replication, assumption sensitivity and exclusions |
| data/geometry/ | Development centerlines/descriptors and Hong Kong original polygon/configuration metadata |

## Fields

- tag identifies the geometry–demand scenario; cell_id identifies the underlying cell; cities define LOCO folds.
- W: representative width (m); qp: specified demand (ped/min); x: stored specific demand (ped/min/m). Demand is not measured arrivals.
- quota/qr: candidate/tested entry flow (robots/min); historical column names retained.
- q_star: highest qualifying flow in the frozen scan, not a continuous capacity.
- Reference statuses: 185 POSITIVE, 154 ZERO, 12 CEILING_CENSORED, 44 OUT_OF_DOMAIN_GEOMETRY, 5 TECHNICAL_INVALID. Excluded cases are not zeros.
- configuration: original/historical or nearest-safe-anchor-v1 repair; never pool configurations.
- seed: primary 0–29; independent replication 10000–10029.
- mean_speed: observation-weighted zone speed (m/s); mean_density: time-mean pedestrian count/zone area (ped/m²).
- inflow_ped/outflow_ped: completed records departing/arriving within the window, not exact insertion counts.
- **flow_ratio is a legacy field. Do not use it for final scoring.** Recompute outflow/inflow; zero denominator is undefined.
- throughput_ratio_final: final ratio, missing when undefined; seed_PASS: conjunction of the three criteria.
- baseline_mean_speed: mean of 30 matching baseline seed means; baseline_spec_hash locates the paired original run.
- Planned/observed counts and stocks diagnose demand implementation. First observation/movement are proxies, not exact model-entry timestamps.

## Included and retained elsewhere

Included: final per-seed metrics, baseline matches, scan audit, frozen references/predictions/parameters, specifications, selected geometry, sensitivity/replication and raw hashes. These support the tested lightweight reproduction.

Retained locally, not uploaded: full trajectory/XML archive, simulator stdout/stderr archives, external raw GIS downloads and historical research assets. These are evidence/source material, not disposable cache. Contact the corresponding author listed in the paper for the raw archive; full raw-log availability is not asserted by this Git release.

Third-party geometry/template rights remain with their source providers. No blanket license is invented. Saved Hong Kong metadata and Git history retain upstream provenance.
