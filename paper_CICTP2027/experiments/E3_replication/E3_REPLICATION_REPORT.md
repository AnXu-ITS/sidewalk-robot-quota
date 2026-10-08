# E3 Independent seed replication

Status: COMPLETE

Fifteen scenarios frozen before execution: five robust M0, five near-boundary M0 and five remaining M1 failures spanning severity ranks. Selection code is deterministic and uses original metrics only; SHA256 matches the original sample freeze. Robust/near ranks cycle through cities; failure ranks are evenly spaced. Two M0 recommendations in the failure stratum are zero and remain zero-admission records, not fabricated PASS decisions. No intermediate-margin replication added.

Each independent candidate uses its own scenario/configuration-matched 10000–10029 baseline mean. Candidates remain frozen. Decision stability denominator is positive method/scenario decisions, not 15 scenarios: M0 and M1 can have distinct decisions within one scenario. Shared-flow evidence would be cached; correlated paired conditions are not independent observations.

```text
           group  replicated_decisions  requested_decisions  unchanged  decision_stability  PASS_to_PASS  PASS_to_FAIL  FAIL_to_PASS  FAIL_to_FAIL
             ALL                    28                   28         20            0.714286            18             2             6             2
       S1 robust                    10                   10         10            1.000000            10             0             0             0
S2 near-boundary                    10                   10          6            0.600000             5             2             2             1
   S3 M1-failure                     8                    8          4            0.500000             3             0             4             1
              M0                    13                   13         13            1.000000            13             0             0             0
              M1                    15                   15          7            0.466667             5             2             6             2
```

```text
                              tag selection_stratum method  candidate_flow  original_pass_count  independent_pass_count transition independent_dominant_failure_component
       TPE-taipei-idx813-0-1|qp45         S1 robust     M0             2.0                 30.0                    30.0 PASS->PASS                                   none
       TPE-taipei-idx813-0-1|qp45         S1 robust     M1             5.0                 30.0                    30.0 PASS->PASS                                   none
 AMS-amsterdam-chain-44642-0|qp30         S1 robust     M0             2.0                 30.0                    30.0 PASS->PASS                                   none
 AMS-amsterdam-chain-44642-0|qp30         S1 robust     M1             5.0                 30.0                    30.0 PASS->PASS                                   none
     TAO-taoyuan-idx3430-0-3|qp24         S1 robust     M0             1.0                 30.0                    30.0 PASS->PASS                                   none
     TAO-taoyuan-idx3430-0-3|qp24         S1 robust     M1             4.0                 30.0                    30.0 PASS->PASS                                   none
   MEL-melbourne-1465759-0-1|qp28         S1 robust     M0             1.0                 30.0                    30.0 PASS->PASS                                   none
   MEL-melbourne-1465759-0-1|qp28         S1 robust     M1             5.0                 30.0                    30.0 PASS->PASS                                   none
    NTP-newtaipei-idx251-0-0|qp30         S1 robust     M0             2.0                 30.0                    30.0 PASS->PASS                                   none
    NTP-newtaipei-idx251-0-0|qp30         S1 robust     M1             5.0                 30.0                    30.0 PASS->PASS                                   none
      SEA-seattle-5438086-0-1|qp9  S2 near-boundary     M0             6.0                 29.0                    30.0 PASS->PASS                                   none
      SEA-seattle-5438086-0-1|qp9  S2 near-boundary     M1             8.0                 29.0                    28.0 PASS->FAIL                                  speed
AMS-amsterdam-chain-166482-0|qp11  S2 near-boundary     M0             9.0                 29.0                    30.0 PASS->PASS                                   none
AMS-amsterdam-chain-166482-0|qp11  S2 near-boundary     M1            12.0                 25.0                    28.0 FAIL->FAIL                                  speed
     TAO-taoyuan-idx10181-0-0|qp9  S2 near-boundary     M0             6.0                 29.0                    29.0 PASS->PASS                                  speed
     TAO-taoyuan-idx10181-0-0|qp9  S2 near-boundary     M1             8.0                 27.0                    29.0 FAIL->PASS                                  speed
    MEL-melbourne-1477330-0-0|qp9  S2 near-boundary     M0             6.0                 29.0                    30.0 PASS->PASS                                   none
    MEL-melbourne-1477330-0-0|qp9  S2 near-boundary     M1             8.0                 29.0                    27.0 PASS->FAIL                                  speed
   NTP-newtaipei-idx13763-0-2|qp9  S2 near-boundary     M0             6.0                 29.0                    29.0 PASS->PASS                                  speed
   NTP-newtaipei-idx13763-0-2|qp9  S2 near-boundary     M1             8.0                 28.0                    29.0 FAIL->PASS                                  speed
                    DC-112|qp43.2     S3 M1-failure     M1             2.0                 16.0                    19.0 FAIL->FAIL                                  speed
    NTP-newtaipei-idx6919-0-0|qp9     S3 M1-failure     M0             5.0                 30.0                    29.0 PASS->PASS                                  speed
    NTP-newtaipei-idx6919-0-0|qp9     S3 M1-failure     M1             6.0                 27.0                    29.0 FAIL->PASS                                  speed
                    DC-111|qp32.4     S3 M1-failure     M1             2.0                 28.0                    29.0 FAIL->PASS                           speed + flow
      SEA-seattle-5426480-0-0|qp9     S3 M1-failure     M0             6.0                 30.0                    29.0 PASS->PASS                                  speed
      SEA-seattle-5426480-0-0|qp9     S3 M1-failure     M1             8.0                 28.0                    29.0 FAIL->PASS                                  speed
      TPE-taipei-idx12521-0-5|qp9     S3 M1-failure     M0             5.0                 30.0                    30.0 PASS->PASS                                   none
      TPE-taipei-idx12521-0-5|qp9     S3 M1-failure     M1             7.0                 28.0                    29.0 FAIL->PASS                                  speed
```

Original and independent speed, density and flow-ratio summaries, component failures and baseline status are in the results CSV; seed-level records are in E3_SERVICE_PER_SEED.csv. Baseline failures are separately reported and are not hidden by conditioning on a new baseline. Results describe this prespecified small sample only; 30 seeds do not guarantee population-level reliability. Stratum selection intentionally enriches boundary/failure cases and cannot estimate all-164 population decision stability.
