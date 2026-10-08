# E4 Zero-margin failure decomposition

Status: COMPLETE. Existing data only; no new simulation.

Scope: 18 original M1 FAIL scenarios, exact original candidate flow, configuration and seeds 0–29. All 540 seed records use the matching original baseline mean. Undefined completed-departure denominator fails the flow component. Technical failures and absent evidence are not recoded as adverse service outcomes.

```text
                  mode  scenarios
                 speed         10
          speed + flow          5
speed + density + flow          3
```

Scenario failure mode is the union of violated components across its seeds; it does not imply simultaneous violation in a single seed. E4_FAILURE_PER_SEED.csv and seed_failure_patterns give actual seed-level conjunctions. Dominance is the largest component-specific failing-seed count, retaining ties.

```text
                              tag     W   qp  candidate_flow  q_star  passing  scenario_failure_mode dominant_component
AMS-amsterdam-chain-166482-0|qp11 2.267 11.0            12.0     9.0       25                  speed              speed
                    DC-042|qp30.5 1.697 30.5             2.0     1.0       27 speed + density + flow              speed
                    DC-045|qp31.5 1.749 31.5             2.0     1.0       26           speed + flow              speed
   NTP-newtaipei-idx11901-0-0|qp9 1.780  9.0             7.0     8.0       28                  speed              speed
   NTP-newtaipei-idx13763-0-2|qp9 1.800  9.0             8.0     7.0       28                  speed              speed
    NTP-newtaipei-idx6919-0-0|qp9 1.740  9.0             6.0     5.0       27           speed + flow              speed
    NTP-newtaipei-idx7317-0-1|qp9 1.740  9.0             6.0     5.0       28                  speed              speed
                    DC-006|qp30.2 1.676 30.2             2.0     1.0       28           speed + flow              speed
      SEA-seattle-5426480-0-0|qp9 1.829  9.0             8.0     7.0       28                  speed              speed
      SEA-seattle-5433778-0-0|qp9 1.829  9.0             8.0     7.0       28                  speed              speed
      SEA-seattle-5449118-0-0|qp9 1.829  9.0             8.0     7.0       27                  speed              speed
      TPE-taipei-idx12521-0-5|qp9 1.750  9.0             7.0     5.0       28                  speed              speed
                    DC-067|qp59.5 2.480 59.5             3.0     2.0       27           speed + flow              speed
     TAO-taoyuan-idx10181-0-0|qp9 1.800  9.0             8.0     6.0       27                  speed              speed
     TAO-taoyuan-idx7044-0-7|qp11 2.230 11.0            12.0    11.0       28                  speed              speed
     TAO-taoyuan-idx5160-0-0|qp22 1.870 22.0             4.0     6.0       28           speed + flow       speed + flow
                    DC-111|qp32.4 1.800 32.4             2.0     1.0       28 speed + density + flow              speed
                    DC-112|qp43.2 1.800 43.2             2.0     0.0       16 speed + density + flow              speed
```

Widths, demand, specific demand, reference utilization and E1 diagnostics are associations, not identified causal effects. A reference exceedance is not itself a service failure. A small or zero q* does not justify inferring another flow’s outcome. No manuscript Figure 2 was changed.
