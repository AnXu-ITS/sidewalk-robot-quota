# New experiments — internal technical report

This is an experiment package, not manuscript prose. All manuscript copies, manuscript figures/tables, bibliography and historical experimental assets remain byte-identical. Date: 7 October 2026, Asia/Singapore.

# 1. Executive status


```text
                experiment                    status                                                                                                                    reason
     E1 demand realization COMPLETE WITH LIMITATIONS All reported direct tests audited; physical insertion timestamps and complete historical cohort/stock records unavailable
           E2 margin sweep                  COMPLETE                                              Five quantiles; 463 exact groups, 439 cached and24 new; all positives tested
E3 independent replication                  COMPLETE                                             15 frozen scenarios, matching independent baselines;40 new groups and3 cached
  E4 failure decomposition                  COMPLETE                                                                   18 original M1 failure groups; existing540 seed records
        E5 rule provenance COMPLETE WITH LIMITATIONS                         Fold fits/margins clean; architecture independence and some historical timing cannot be certified
                Validation                  COMPLETE                                                                                 16 checks pass; 1739 old assets unchanged
           E6 polygon area                   NOT RUN                                                                                    Optional, outside required E1–E5 scope
         E7 burst arrivals                   NOT RUN                                                                                                            Not authorized
```
# 2. Exact work performed

Reconstructed 400 scenario definitions, seven-city folds, configuration templates, baseline/flow evidence, frozen inference parameters and service protocol. Built a configuration/flow/seed-block cache index, reproduced current M0/M1 endpoints, reconstructed synthetic gates from surviving aggregate labels, froze a deterministic replication sample and queue before simulations, ran only missing tests, and produced seed/scenario/city tables plus six analysis-only figures. No model, threshold, reference q*, operating candidate, arrival process, geometry, simulator timestep or physical property was retuned.

# 3. New simulations executed

64 groups / 1,920 seeds: E2 24 groups /720 original seeds; E3 40 groups /1,200 independent seeds. E3 requests total43 groups:15 baseline and28 positive candidate groups, of which one baseline and two candidate groups were already covered for one selected scenario. 0 selected scenarios have identical positive M0/M1 flows. No intermediate-margin replication added.

Actual campaign elapsed: 23.26 min with at most four workers. Sum of simulator durations: 45.59 min; sum of complete run durations (simulation+parsing+hashes): 90.46 min. These sums overlap in wall time. Technical failures:0; retries:0; no replacement seeds. Valid adverse outcomes remain in all tables. The initial budget estimated38.79 minutes of four-worker simulation plus parsing/I/O; elapsed results are reported rather than rewriting that estimate.

Every new run retains spec, SUMO command, generated net/routes/configuration, stdout/stderr/error logs, personinfo, personfcd, completed records, per-agent observation/movement table, demand diagnostics, outcome and SHA256 hashes. Old XML is absent after a documented prior cleanup; old evidence is reused from preserved XML-derived records and configuration metadata.

# 4. E1 findings


```text
    dataset           scope method candidate_status  groups  first_observed_ratio_min  window_completed_ratio_min  position_proxy_seed_coverage  passing_seeds_with_under_90pct_window_completed
Development            LOCO     M0             PASS      98                       1.0                    0.916667                           330                                                0
Development            LOCO     M1             FAIL      18                       1.0                    0.138889                            90                                                0
Development            LOCO     M1             PASS     118                       1.0                    0.345070                           540                                                1
Development            LOCO     M2             PASS      59                       1.0                    0.764706                             0                                                1
Development            LOCO     M3             FAIL       2                       1.0                    0.138889                             0                                                0
Development            LOCO     M3             PASS      96                       1.0                    0.916667                           330                                                0
  Hong Kong Frozen transfer     M0             PASS      11                       1.0                    0.950000                           120                                                0
  Hong Kong Frozen transfer     M1             FAIL       1                       1.0                    0.368750                             0                                                0
  Hong Kong Frozen transfer     M1             PASS      15                       1.0                    0.943750                           210                                                0
  Hong Kong Frozen transfer     M2             PASS       9                       1.0                    0.950000                            60                                                0
  Hong Kong Frozen transfer     M3             PASS      11                       1.0                    0.950000                           120                                                0
```
All scheduled measurement-cohort pedestrians in the audited records have a first observation somewhere in the full440-second run. That is visibility, not verified physical insertion by340s. Original M0 has no seed with window completed-arrival/scheduled ratio below0.90: minimum11/12=0.9167; Hong Kong M0 minimum0.95. Surviving M0 movement-proxy subsets show scheduled-cohort movement, but cover only330/2940 development and120/330 Hong Kong seed records. Therefore there is no observed evidence that the reported M0 passes were produced by severe demand suppression, with incomplete physical insertion audit coverage.

**Material criterion limitation:** one original M1 qualifying seed and one M2 qualifying seed have completed-arrival/scheduled diagnostics below0.90. M1 NTP-newtaipei-idx6919-0-0|qp21, flow4, seed20:75 completed-window arrivals /84 scheduled=0.8929; completed departure denominator64 gives T=75/64=1.171875. M2 DC-067|qp59.5, flow1, seed4:182/238=0.7647 while T=182/174=1.0460 and speed retention1.0208; this directly demonstrates a near-unit balanced ratio coexisting with a23.5% nominal-window completion shortfall in a qualifying seed. It is not proof of insertion suppression because the completion and scheduled windows are cross-cohort. Four low-completion seed records occur within M1 PASS groups, including valid adverse seed outcomes allowed by29/30. The only original M0/M1 seed with T in[0.95,1.05] and low completion is in a M1 FAIL group (DC-112, flow2, seed14). No screened M0 PASS is misleading under the stated criterion. A PASS is misleading if interpreted as fulfillment of all scheduled demand; the criterion remains empirically usable for its stated conditional speed/density/completed-record objective, not as a demand-fulfillment guarantee.

New-run supplemental diagnostics retain movement-by340 and scheduled-cohort completions explicitly: 1 positive-flow pedestrian seeds have position-update-by340/scheduled ratio below0.90. This is a movement proxy; exact physical insertion remains unavailable. All3,840 new pedestrian/robot proxy stock-conservation rows balance. Full per-seed data are in NEW_SIMULATION_DEMAND_DIAGNOSTICS.csv. Historical stock_339 is not silently relabelled as340.


```text
experiment  type service_group_status  seed_service_PASS  seed_type_rows  scheduled  position_ratio_min  end_of_run_cohort_completion_min  window_completed_ratio_min
        E2   ped                 PASS              False               1         44            1.000000                          1.000000                    1.000000
        E2   ped                 PASS               True             719      35596            1.000000                          1.000000                    0.950000
        E2 robot                 PASS              False               1         28            1.000000                          1.000000                    1.000000
        E2 robot                 PASS               True             719      27212            1.000000                          1.000000                    0.928571
        E3   ped                 FAIL              False              18       2182            0.879310                          0.091954                    0.264368
        E3   ped                 FAIL               True             102       6518            0.994253                          0.988506                    0.942529
        E3   ped                 PASS              False               8        382            1.000000                          0.269231                    0.453846
        E3   ped                 PASS               True             652      53318            1.000000                          1.000000                    0.944444
        E3 robot                 FAIL              False              18        344            1.000000                          0.000000                    0.125000
        E3 robot                 FAIL               True             102       3256            1.000000                          1.000000                    0.875000
        E3 robot                 PASS              False               8        204            1.000000                          0.125000                    0.375000
        E3 robot                 PASS               True             652      12876            1.000000                          1.000000                    0.750000
```
The new-run table separates group PASS/FAIL from pedestrian seed qualification. A29/30 PASS group can contain one severe adverse seed: group-level minima are not automatically minima among qualifying seeds. None of the new qualifying pedestrian seeds has a window completed/scheduled ratio below0.90. All qualifying seeds within new PASS groups have complete scheduled-cohort records by the440s run end; qualified seeds in FAIL groups have minimum0.9885. Robot rows use the same pedestrian-service label and do not represent a robot-service criterion.

# 5. E2 findings


```text
 tau  positive_recommendations  zero_recommendations  PASS  FAIL  pass_fraction_among_positives  mean_positive_candidate_flow  median_reference_utilization  reference_exceedance_count  mae_to_reference  withheld_relative_to_tau0  withheld_tau0_flow_PASS
0.00                       136                    28   118    18                       0.867647                      6.316176                      0.750000                          16          2.426829                          0                        0
0.50                       129                    35   119    10                       0.922481                      5.240310                      0.428571                           9          3.408537                          7                        4
0.65                       122                    42   117     5                       0.959016                      4.836066                      0.300000                           4          3.859756                         14                        8
0.80                        98                    66    98     0                       1.000000                      4.806122                      0.166667                           0          4.536585                         38                       32
0.90                        58                   106    58     0                       1.000000                      4.810345                      0.000000                           0          5.707317                         78                       71
```
This observed sample displays a controllable access/service trade-off: stronger training-only margins reduce positive opportunities and observed failed tests. Tau0.80 preserves98 positives with0 failures; tau0.90 preserves58 with0 failures. Tau0.80 withholds38 original opportunities,32 of which pass at their directly tested zero-margin rates. Tau0.90 withholds78,71 of which pass. No universal optimal quantile is identified. Mean flow among the surviving positive subset need not decline monotonically because its composition changes. Zero median utilization at0.90 results from including all139 positive-reference scenarios, including withheld access; it does not mean no robots are admitted.

All exact tests use original0–29 seeds and matching original baseline. Quantile residuals contain only six training cities. Parameters, exclusions, clipping and flooring match the frozen protocol. All400 q* records and all1,600 existing recommendations are unchanged. New selective flows never augment training references.

# 6. E3 findings


```text
           group  replicated_decisions  requested_decisions  unchanged  decision_stability  PASS_to_PASS  PASS_to_FAIL  FAIL_to_PASS  FAIL_to_FAIL
             ALL                    28                   28         20            0.714286            18             2             6             2
       S1 robust                    10                   10         10            1.000000            10             0             0             0
S2 near-boundary                    10                   10          6            0.600000             5             2             2             1
   S3 M1-failure                     8                    8          4            0.500000             3             0             4             1
              M0                    13                   13         13            1.000000            13             0             0             0
              M1                    15                   15          7            0.466667             5             2             6             2
```
M0 robust stratum: 5/5 unchanged. M0 near-boundary stratum: 5/5 unchanged. Preselected M1-failure stratum: 1/5 unchanged. Across all replicated M0 positive conditions: 13/13 unchanged. Overall stability counts28 method/scenario decisions, with paired conditions correlated and both methods represented.


```text
                           tag selection_stratum method  candidate_flow  original_pass_count  independent_pass_count transition independent_dominant_failure_component
   SEA-seattle-5438086-0-1|qp9  S2 near-boundary     M1             8.0                 29.0                    28.0 PASS->FAIL                                  speed
  TAO-taoyuan-idx10181-0-0|qp9  S2 near-boundary     M1             8.0                 27.0                    29.0 FAIL->PASS                                  speed
 MEL-melbourne-1477330-0-0|qp9  S2 near-boundary     M1             8.0                 29.0                    27.0 PASS->FAIL                                  speed
NTP-newtaipei-idx13763-0-2|qp9  S2 near-boundary     M1             8.0                 28.0                    29.0 FAIL->PASS                                  speed
 NTP-newtaipei-idx6919-0-0|qp9     S3 M1-failure     M1             6.0                 27.0                    29.0 FAIL->PASS                                  speed
                 DC-111|qp32.4     S3 M1-failure     M1             2.0                 28.0                    29.0 FAIL->PASS                           speed + flow
   SEA-seattle-5426480-0-0|qp9     S3 M1-failure     M1             8.0                 28.0                    29.0 FAIL->PASS                                  speed
   TPE-taipei-idx12521-0-5|qp9     S3 M1-failure     M1             7.0                 28.0                    29.0 FAIL->PASS                                  speed
```
Independent baseline service outcomes are retained beside every mixed decision; new baseline means do not retune offered flows. The sample is selected to test robustness and boundary sensitivity; it cannot estimate reliability for all164 scenarios. Thirty seeds do not guarantee population-level reliability. Changed decisions are new observations and do not replace original decisions or the current manuscript numbers.

# 7. E4 findings


```text
                  mode  scenarios
                 speed         10
          speed + flow          5
speed + density + flow          3
```
Speed is involved in all18 failed scenarios and is dominant in17; one ties speed and flow ratio. Scenario mode is a union over failing components across seeds, not necessarily their same-seed conjunction. The CSV gives counts and seed patterns, along with width, demand, q_p/W, offered flow, q*, utilization and E1 diagnostics. These associations do not identify a causal traffic mechanism.

# 8. E5 findings

No held-out samples enter regression or residual calibration: independently reconstructed coefficients and Q80 margins match frozen values. Synthetic C(W), Q_low(W) and x_crit reproduce from the48-row table. Architecture selection is not fully city-blind: a historical Amsterdam collapse motivated the controlled corner studies; that historical cell is absent from the current140-cell sample, but its city is an evaluation city. The corner restriction is a frozen development heuristic. Selection timing/independence of some domain rules and the originalQ80 choice is incompletely documented. The September15 session protocol establishes a freeze before the final reported folds, not independent preregistration.

This limits strict end-to-end unseen-city claims, while preserving conditional city-held-out parameter/margin results under fixed guardrails. A genuinely clean whole-architecture validation would require untouched data and independently specified rules, or a recoverable nested selection history. Such data/history are not established here. No rule was redesigned and no simulated clean architecture claim is substituted for the actual history.

# 9. Consistency with current manuscript

A. Existing conclusion supported: the original M0/M1 outcomes reproduce exactly, and the new margin sweep directly supports an access/service trade-off. Hong Kong frozen results remain unchanged.

B. Existing conclusion supported but should later be qualified: demand realization is supported by observed/cohort and completed-window diagnostics, with incomplete movement/insertion coverage. The service ratio is not a demand-fulfillment metric. City-held-out rigor applies to coefficient/margin estimation under a fixed developed architecture. Independent replication must be reported by stratum and method, retaining transitions and finite-seed limits.

C. Existing conclusion requires later revision: any wording asserting all positive candidates are seed-block invariant, full scheduled-demand fulfillment from T alone, or completely city-blind development of all rules would need revision. Those stronger propositions are not established by the current evidence. The frozen manuscript already states completed-count and boundary limitations; observational numbers are not errors simply because new decisions differ.

D. Serious contradiction detected: no contradiction to the principal conditional margin/access finding is detected. This does not certify the entire model architecture or all untested seeds/cities. No current manuscript or figure was repaired.

# 10. Recommended manuscript changes

TODO only; not executed.

- Pedestrian-Service Criterion: add demand diagnostics and precise observation/movement/cohort-completion limitations; distinguish completed-window ratio from fulfillment.
- Admission Decision and Evaluation Design: add the prespecified quantiles and a rule-provenance table; qualify architecture selection versus training-only fold estimation.
- Results: add the margin sweep and failure decomposition using directly tested outcomes.
- Sensitivity/independent replication: add the frozen15-scenario stratified results and decision transitions; retain the original DC-063 observation.
- Discussion: explain access forfeiture, boundary sensitivity, finite seeds and development-heuristic limitations.
- Only after explicit later authorization, decide whether analysis figures/tables should enter the manuscript.

# 11. Artifact manifest

NEW_EXPERIMENT_ARTIFACT_MANIFEST.csv lists every script, CSV, config, log, figure, report and new raw-run file with bytes and SHA256. The manifest itself is excluded from self-hashing to avoid a circular digest. SOURCE_SNAPSHOT.csv and ENVIRONMENT_SNAPSHOT.json preserve the initial research state; VALIDATION_CHECKS.csv and VALIDATION_RESULT.json preserve final validation.

Principal entry points: extension.py prepare/run/analyze (prepare must not be rerun after simulations); plot_extension.py; validate_extension.py; finalize_extension.py. Original source inputs are named in reports and snapshots. Raw simulations: runs/<spec_hash>/ (1,920 directories); analysis figures: figures/; QA: figure_qa/.

Reanalysis may update only derived files in this new package; frozen sample/queue/config snapshots must retain their hashes. Existing run directories refuse overwrites and validate raw hashes before cache reuse. Git publication excludes this package under its existing .gitignore, so retain/package these artifacts explicitly when moving machines.

EXPERIMENT_EXTENSION_COMPLETE_WITH_LIMITATIONS
