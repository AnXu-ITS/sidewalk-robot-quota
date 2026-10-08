# New simulation budget — frozen before execution

E1: all final direct tests have archived planned/observed and completed-record metrics; subset position-update diagnostics. No reruns; disclose missing insertion and stocks.

E2: 5 quantile settings; 463 unique scenario/configuration/flow groups (16 distinct integer flows); 439 already covered; 24 missing 30-seed groups.

E3: 15 frozen scenarios, five per stratum. 15 baseline groups requested, 14 new baselines. 28 unique M0/M1 candidate groups, 26 new mixed groups. Zero admission is not tested as a positive recommendation. 0 scenarios share M0/M1 flow; all duplicated method requests share one group. No intermediate replication flow added.

```text
                              tag      city  M0_candidate  M1_candidate selection_stratum
       TPE-taipei-idx813-0-1|qp45    taipei           2.0           5.0         S1 robust
 AMS-amsterdam-chain-44642-0|qp30 amsterdam           2.0           5.0         S1 robust
     TAO-taoyuan-idx3430-0-3|qp24   taoyuan           1.0           4.0         S1 robust
   MEL-melbourne-1465759-0-1|qp28 melbourne           1.0           5.0         S1 robust
    NTP-newtaipei-idx251-0-0|qp30 newtaipei           2.0           5.0         S1 robust
      SEA-seattle-5438086-0-1|qp9   seattle           6.0           8.0  S2 near-boundary
AMS-amsterdam-chain-166482-0|qp11 amsterdam           9.0          12.0  S2 near-boundary
     TAO-taoyuan-idx10181-0-0|qp9   taoyuan           6.0           8.0  S2 near-boundary
    MEL-melbourne-1477330-0-0|qp9 melbourne           6.0           8.0  S2 near-boundary
   NTP-newtaipei-idx13763-0-2|qp9 newtaipei           6.0           8.0  S2 near-boundary
                    DC-112|qp43.2   taoyuan           0.0           2.0     S3 M1-failure
    NTP-newtaipei-idx6919-0-0|qp9 newtaipei           5.0           6.0     S3 M1-failure
                    DC-111|qp32.4   taoyuan           0.0           2.0     S3 M1-failure
      SEA-seattle-5426480-0-0|qp9   seattle           6.0           8.0     S3 M1-failure
      TPE-taipei-idx12521-0-5|qp9    taipei           5.0           7.0     S3 M1-failure
```

E4: existing exact per-seed outcomes sufficient; no new simulation.

E5: scripts, fixed config, aggregate synthetic grid, prior audits and provenance records available. Chronology/independence cannot be proved where records are absent; no simulation needed.

Total: 64 new 30-seed groups = 1920 expected seed runs. Estimated simulator sum 2.59 hours; about 0.65 hours with four workers, plus XML parsing and disk I/O. Estimate uses per-scenario historical median runtime; congested runs can take longer. A full original-study reconstruction is unnecessary. This is within the authorized 15-scenario replication and exact-flow sweep scope.
