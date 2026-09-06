# Repository Freeze Manifest

> Purpose (Part H): make the frozen release discoverable — a new user must know,
> without ambiguity, which artifacts are FINAL vs LEGACY vs SUPERSEDED.

## 1. Frozen release layout (final_freeze/)

```text
final_freeze/
├── FINAL_METHOD_FREEZE_REPORT.md          # method freeze (previous round)
├── FINAL_REPRODUCIBILITY_FREEZE_REPORT.md # this round (Q1–Q8)
├── final_quota_method_config.yaml         # single source of truth (human)
├── final_quota_method_config.json         # single source of truth (runtime twin)
├── SHA256SUMS.txt                         # immutable hashes
├── base_pass_deployment_final.md          # Part A decision
├── base_pass_deployment_audit.md          # Phase 1–2 audit (previous round)
├── final_operational_rule.md              # frozen ordering (previous round)
├── final_ablation_table.csv               # guardrail ablation
├── in_domain_vs_ood_results.csv           # in-domain vs OOD
├── amsterdam_failure_case.md              # failure-mode case study
├── claims_boundary.md                     # allowed/forbidden claims
├── final_consistency_audit.md             # stale-value audit
├── final_d2_provenance.txt                # D2 data provenance (RESOLVED)
├── D2_DATA_RESTORE_PLAN.md                # data-restore + verification gate (DONE)
├── D2_RECONSTRUCTION_VERIFICATION.md      # data found + chain reproduced
├── final_dataset_counts.json              # exact counts (confirmed, 400 rows)
├── runtime_parameter_sync_audit.md        # runtime == config == paper
├── reproduction_smoke_test.md             # smoke-test status
├── repository_freeze_manifest.md          # this file
├── data/                                  # base_pass CSVs (proxy, P1b)
│   ├── base_pass_by_cell.csv
│   ├── base_pass_monotonicity_audit.csv
│   └── sidewalk_baseline_thresholds.csv
├── src/                                   # frozen runtime + tooling
│   ├── operational_quota.py
│   ├── base_pass_monotonicity.py
│   ├── reproduce_metrics.py
│   ├── reproduce_frozen_chain.py
│   ├── verify_d2.py
│   └── verify_base_pass.py
├── paper_outputs/                         # paper-ready text (see below)
└── (paper_*.md files)
```

`data/final/` (repo root) holds the recovered D2 table + raw baseline/sweep/
refinement CSVs (11 files, hashes in `data/final/SHA256SUMS.txt`).

## 2. Classification of every parameter/result

| Artifact | Classification |
|---|---|
| `final_quota_method_config.{yaml,json}` | **FINAL** — single source of truth |
| `src/operational_quota.py` | **FINAL** — frozen runtime |
| `final_ablation_table.csv`, `in_domain_vs_ood_results.csv` | **FINAL** |
| `paper_methods_ready.md`, `paper_results_ready.md`, `paper_limitations_ready.md`, `claims_boundary.md` | **FINAL** |
| `quota_params/quota_params.json` | **SUPERSEDED** (pre-D2 mean-based) |
| `quota_params/quota_params_seedwise.json` | **SUPERSEDED** (pre-D2 seedwise) |
| `quota_params/quota_params_final.json` | **SUPERSEDED** (synthetic-line) |
| `pipeline/p1b_reference_dryrun.csv`, `pipeline/dryrun/*` | **LEGACY** (P1b archived) |
| `pipeline/sim/scripts/*` | **LEGACY pipeline** (pre-freeze; fitting/scan scripts) |
| `data/final/full_reference_dataset.csv` (D2) + raw baseline/sweep/refinement CSVs | **FINAL** — recovered & hashed |

## 3. Paper-outputs mapping

`paper_methods_ready.md`, `paper_results_ready.md`, `paper_limitations_ready.md`,
`paper_figures_tables_plan.md`, `claims_boundary.md` (in `final_freeze/`) are the
paper-ready text; they must match the frozen config (see Part J).

## 4. Blockers to a fully-reproducible release

**None remaining.** The D2 reference table and raw baseline/sweep/refinement CSVs
were located at `D:\quota_experiment` and copied into `data/final/` (hashes in
`data/final/SHA256SUMS.txt`). The frozen chain reproduces exactly
(`D2_RECONSTRUCTION_VERIFICATION.md`). The release is self-contained and
reproducible.
