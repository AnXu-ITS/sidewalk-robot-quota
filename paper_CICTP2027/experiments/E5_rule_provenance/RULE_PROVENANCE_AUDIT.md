# E5 Rule provenance / leakage audit

Status: COMPLETE WITH LIMITATIONS. No simulations.

Finding: coefficient and residual calibration are city-held-out, but the entire decision architecture cannot be claimed as independently selected on six cities in every fold. Controlled corner tests were explicitly motivated by a historical Amsterdam collapse (AMS-1351790552), an evaluation-city outcome. That cell is not among current 140 selected cells. This is a frozen development heuristic, not evidence of direct per-fold held-out tuning; it nonetheless prevents a fully city-blind architecture claim.

Current six-city coefficients and Q80 margins independently reproduce stored parameters, with disjoint training/test tags and cells. E2 margins use only six training cities for every tau. Scenario-specific held-out pedestrian baseline is an explicit operational input; it is not used to fit coefficients or margins. New direct-test outcomes never alter frozen references.

Synthetic C(W), Q_low(W) and x_crit reconstruct exactly from the surviving 48-row aggregate table using the historical construction functions. Prior audit documents 14,400 recovered synthetic seed records and hashes, but their old external archive paths are now absent; this phase independently verifies aggregate reconstruction, not their raw insertion history. Chronology is documented by the 2026-09-15 session protocol and prior freeze records, not independent preregistration. Unknown timing and outcome dependence remain marked unknown.

The absolute-speed guard, geometry domain and Q80 initial selection do not have complete independent selection histories. The archive contains prior margin-sweep results and city diagnostics; their existence alone does not prove selection on held-out outcomes, nor establish pre-data independence. Claims about clean parameter/margin estimation remain defensible; strict end-to-end unseen-city generalization requires later qualification. No frozen rule was changed.

A clean end-to-end validation would need an independently specified architecture and genuinely untouched city data, or a fully nested reconstruction of rule selection if its inputs can be recovered. Neither can be asserted from this repository alone; it is beyond this authorized E1–E5 extension and unnecessary to compute its conditional access/service results. We therefore record the limitation rather than invent a supposedly clean retuning.

```text
                          rule                                          selected_before_reported_folds                                                                     used_evaluation_city_outcomes  learned_inside_each_fold
            service thresholds                        documented; original preregistration unavailable                                                                      no outcome tuning documented                     False
  pedestrian-only service gate          before final corrected predictions; reviewed existing outcomes                                         yes: diagnostic correction uses existing per-city records                     False
 absolute baseline speed floor    documented prior final folds; exact first selection date unavailable                                       development diagnostics; precise city dependence unresolved                     False
              demand gate C(W)                      documented historical freeze before reported folds                                                  no: synthetic grid, not seven-city outcome table                     False
   low-demand ceiling Q_low(W)                      documented historical freeze before reported folds                                                                  no city outcomes in construction                     False
   specific demand upper bound                      documented historical freeze before reported folds                                                                  no city outcomes in construction                     False
                  width domain         documented historical freeze; original chronology only archival                                           not established independent of all development outcomes                     False
       pedestrian demand range                                        documented before reported folds                                                                   no direct per-city tuning shown                     False
   geometry types and barriers     fixed before reported folds; first-selection chronology unavailable                   unknown: geometry types from evaluation cities are available during development                     False
              Type B sinuosity fixed before final folds; derivation and initial selection date unknown                                                                                           unknown                     False
     sharp concentrated corner          before reported final folds, after historical city diagnostics         YES: historical Amsterdam outcome motivated design; example absent from current 140 cells                     False
robot-center feasible geometry          before final v3 fold fits; after historical simulation results                        applied after reviewing anomalies; exclusion itself deterministic geometry                     False
                robot flow cap                   before final folds; extended after ceiling saturation                             development outcome-driven scan extension, not held-out fold retuning                     False
           reference scan rule                      before final v3 fits, after prior reported results YES: labels reconstructed from all evaluation cities; reference scoring not fit leakage by itself                     False
       width-demand regression                                                            within folds                                                                  NO held-out city used in fitting                      True
   residual margin calibration                                                            within folds                                                                NO held-out city used in quantiles                      True
    Q80 operating-point choice        protocol before new final diagnostics; selection already existed                         unknown whether initial tau choice was informed by earlier city summaries                     False
         clipping and flooring                                           documented fixed before folds                                                                            no fold outcome tuning                     False
simulator and robot properties                                                        prior final runs                               calibration1.094 is empirical development tuning; no held-out refit                     False
```
