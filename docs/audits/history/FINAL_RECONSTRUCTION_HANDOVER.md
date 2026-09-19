# FINAL RECONSTRUCTION HANDOVER

Generated: 2026-09-16T21:31:45.929312

## 1. Recovered vs re-run
- Existing raw runs recovered (hash-verified reuse): 85501
- Re-run baseline seed-runs (Development qr=0): 12095
- Re-run mixed-flow seed-runs (Development qr>0): 65791
- Re-run Hong Kong seed-runs: 5280
- Rebuilt scenario-flow groups: 2760

## 2. Final-paper dependency on aggregate-only legacy evidence
- LEGACY_METRICS_ONLY rows remaining in inventory: 0
- FINAL PAPER EVIDENCE STATUS: COMPLETE RAW EVIDENCE

## 3. Planned-vs-realized demand integrity
- Per-run arrival_schedule_and_observation.csv carries planned/scheduled/realized entry, completed arrival and stock for ped and robot.

## 4. Reference dataset composition
- CEILING_CENSORED: 12
- OUT_OF_DOMAIN_GEOMETRY: 44
- POSITIVE: 189
- TECHNICAL_INVALID: 5
- ZERO: 150

## 5. M0-M3 strict LOCO (verified v2)
            dataset scope  total    n  abstain  out_of_domain  technical_invalid  positive_reference_n  positive_recommendations  zero  reference_exceedance  max_exceedance       mae  median_utilization
method                                                                                                                                                                                                    
M0      Development  LOCO    400  164      236             44                  5                   141                        98    66                     2             1.0  4.554878            0.166667
M1      Development  LOCO    400  164      236             44                  5                   141                       138    26                    17             3.0  2.469512            0.750000
M2      Development  LOCO    400  164      236             44                  5                   141                        57   107                     0             0.0  7.091463            0.000000
M3      Development  LOCO    400  164      236             44                  5                   141                       101    63                     2             1.0  4.518293            0.181818

## 6. Exact-flow validation
Development:
exact_flow_status  FAIL  PASS
method                       
M0                    3   198
M1                   35   241
M2                    0   113
M3                    6   198
Hong Kong:
exact_flow_status  FAIL  PASS
method                       
M0                    0    11
M1                    2    14
M2                    0     7
M3                    0    11

## 7. Hong Kong clean evaluation
exact_flow_status     FAIL  PASS  ZERO
configuration method                  
ORIGINAL      M0         0     7     6
              M1         1    10     2
              M2         0     5     8
              M3         0     7     6
REPAIRED      M0         0     4     1
              M1         0     5     0
              M2         0     2     3
              M3         0     4     1

## 8. Conclusion changes vs legacy
- Reference composition: legacy 194 zero / 17 ceiling / 189 positive; v2 150 zero / 12 ceiling / 189 positive / 44 out-of-domain / 5 technical-invalid.
- Out-of-domain corridors (robot diameter > width) and technical-invalid deadlocks are reported honestly, not relabeled as capacity.
- See LEGACY_VS_V2_DIFF.csv for row-level changes.

## 9. Output locations
- reference_dataset_raw_verified_v2.csv
- revised_analysis/LOCO_VERIFIED_V2.csv, v2_metrics.csv, v2_fit_and_margin_parameters.csv
- revised_analysis/exact_flow_validation_v2.csv
- revised_analysis/HK_ORIGINAL_VERIFIED_V2.csv, HK_REPAIRED_VERIFIED_V2.csv, HK_COMBINED_ANALYSIS_V2.csv
- RESULTS_VERIFIED_V2.json, LEGACY_VS_V2_DIFF.csv, FULL_EVIDENCE_INVENTORY.csv, EVIDENCE_GAPS.csv
- revised_analysis/raw_rebuilt_service_per_seed.csv (rebuild_metrics_from_raw.py output)
- revised_analysis/geometry_feasibility_v2.csv + geometry_diagnostics/

## 10. Resume command
`python revision_review/reconstruction.py run 12 24.0`  (and `python revision_review/reconstruction.py timeout 16`)

FINAL PAPER EVIDENCE STATUS:
COMPLETE RAW EVIDENCE