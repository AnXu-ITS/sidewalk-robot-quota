# Data dictionary

The experimental unit is a geometry–pedestrian-demand **scenario**. `tag` identifies
it; `cell_id` identifies a geometry reused at different demands. `configuration`
distinguishes entrances and operating assumptions. An exact service group is
`dataset × tag × configuration × integer flow × seed block`.

| Field | Meaning / unit |
|---|---|
| `W`, `L` | Effective width and corridor length, m |
| `qp`, `qp_over_W` | Scheduled pedestrians/min and pedestrians/(min m) |
| `x` | Archived rounded specific demand used for fitting/residual calibration |
| `qr`, `quota`, `candidate_flow` | Scheduled/offered robot entry rate, robots/min |
| `q_star` | Frozen highest qualifying scanned reference flow;20 is ceiling-censored |
| `q_star_status` | POSITIVE, ZERO, CEILING_CENSORED, physical exclusion or technical unresolved |
| `mean_speed` | Mean instantaneous pedestrian speed in zone/window, m/s |
| `mean_density` | Average pedestrian count / assessed zone area, ped/m² |
| `inflow_ped` | Completed-person records whose departure is in [100,340)s |
| `outflow_ped` | Completed-person records whose arrival is in [100,340)s |
| `baseline_mean_speed` | Mean of 30 matching pedestrian-only seed means, m/s |
| `speed_retention` | Mixed-seed mean / matching baseline mean |
| `throughput_ratio` | Completed arrivals/departures; undefined denominator fails |
| `passing`, `seed_PASS` | Qualifying-seed count and individual service flag |
| `ped_planned_window` | Scheduled pedestrian measurement-window cohort |
| `ped_cohort_observed_by_end` | Cohort visible somewhere by 440 s; not proof of insertion by 340 s |
| position-update fields | First-movement proxy; not an exact physical insertion timestamp |
| `stock_start`, `stock_end` | Movement-proxy stock just before 100 s and 340 s |
| `cohort_completed_by_run_end` | New-run scheduled cohort with a recorded completion by 440 s |
| `spec_hash`, configuration hash | Configuration/seed lineage, retained without local paths |

Original seeds are0–29. Independent seeds are10000–10029. Baseline means are
matched by scenario, entrance/operating configuration and block, not by a shared
city mean or a seed-paired denominator. Positive PASS/FAIL excludes zero admission.

`data/seed_evidence/` supplies original archived scalar runs, prior independent
records and the actual1,920 new outcomes. A few historical sensitivity records lack
W/qp metadata in the broad raw table; corresponding confirmed values are present
in `data/operating_conditions/`. Missing stock/movement/cohort fields in old records
are unknown, not zero. `reference_flow_audit_v3.csv` identifies the original scan
support; later selectively tested recommendation flows do not redefine q*.

`experiments/` preserves full five-setting scenario/city outputs, the original
replication sample and freeze hash, paired transitions, seed-level failure flags,
demand diagnostics and rule history. `SOURCE`/report filenames refer to the
historical local campaign; use the portable scripts here for current reproduction.

Demand completion and scheduled counts in one clock window are cross-cohort
diagnostics. A 29/30 PASS group may include one adverse seed. Group-mode failures
are unions across seeds, whereas per-seed flags report simultaneous components.
Scenario- and method-level rows can reuse the same underlying test; do not treat
duplicated evidence as independent observations.
