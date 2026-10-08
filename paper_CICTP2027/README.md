# CICTP 2027: pedestrian service and robot access

**Balancing Pedestrian Service and Robot Access: An Interpretable Admission Framework for Sidewalk Delivery Robots**

How much robot traffic should an individual sidewalk admit while maintaining
acceptable walking service? This research treats robot admission as a local
allocation decision. Geometry and pedestrian-only service checks precede a
width–demand estimate. A conservative margin changes the offered rate and which
sidewalk conditions receive access. Every positive recommendation has an exact
scenario, entrance, integer-flow and seed-block service test.

The manuscript emphasizes the access–service finding; this package retains the
detailed experimental record. [Manuscript](manuscript/ascexmpl-new.pdf) ·
[Reproduction](REPRODUCE.md) · [Data dictionary](DATA_DICTIONARY.md) ·
[Version history](../research_versions/README.md)

## What the evidence shows

The common city-held-out evaluation contains **164 scenarios / 64 cells**.
Coefficients and residual margins use six training cities per fold; the admission
guardrails are previously developed fixed rules.

| Margin setting | Positive recommendations | Failed direct tests |
|---|---:|---:|
| None (M1) | 136 | 18 |
| 0.50 | 129 | 10 |
| 0.65 | 122 | 5 |
| 0.80 (M0) | 98 | 0 |
| 0.90 | 58 | 0 |

Of the 38 opportunities withheld by M0 relative to M1, **32 pass** at their tested
zero-margin rates. Conservative admission protects the stated service target in
this sample, while stronger conservativeness can remove useful access.

Independent replication on 15 deliberately stratified scenarios preserves
**13/13 M0** and **7/15 M1** positive decisions. These are condition-level sample
results, not population reliability estimates. Speed contributes to all 18
original M1 failure groups and dominates 17. Hong Kong transfer separates **13
original and five entrance-repaired configurations**. Robot-size and direction
tests illustrate sensitivity to changed operating conditions.

## Evidence organization

- `data/`: scenario/fold definitions, frozen references, M0–M3 recommendations,
  complete scalar seed evidence, Hong Kong and operating-condition results.
- `experiments/E1_demand_audit/` through `E5_rule_provenance/`: detailed diagnostics,
  all margin candidates/city summaries, immutable replication selection and
  transitions, component failures and rule provenance.
- `configs/`: frozen admission rules, 467 configuration templates, the original
  1,920-job extension queue and exact parameter-version table.
- `src/`: portable frozen inference/service layer and preserved simulation engine.
- `scripts/`: numerical reproduction, figure/table generation, optional explicit
  simulation reruns and manuscript compilation.
- `reports/`: historical final experiment report, compute accounting and validation.

```bash
python -m pip install -r requirements.txt
python scripts/reproduce.py
python scripts/build_assets.py
```

Run these commands inside `paper_CICTP2027`, or prefix the script paths from the
repository root. Numerical/figure reproduction does not require SUMO. Outputs
are written to ignored `outputs/`; archived data are not overwritten.

## Scientific version and interpretation

The CICTP full-development transfer parameters are **c=23.841787076606813**,
**p=−0.9302944983824531**, **Delta=3.3759218049780055 robots/min**. Fold-specific
values are supplied separately. Earlier D2 and intermediate calibration values
are retained under `research_versions/`; they are not inputs to this workflow.

Service requires 29/30 seeds meeting speed retention ≥0.90, density ≤1.20 ped/m²,
and completed-record flow ratio in [0.90,1.20]. Zero denominators fail the flow
component. Completed-record balance is not scheduled-demand fulfillment, and
visibility/movement proxies are not exact insertion timestamps. Rule provenance
identifies historical city-informed development choices; whole-architecture
independence is not claimed. Reference flows are finite-scan observations, not
universal capacities or guarantees for all lower rates.

See [data rights](DATA_RIGHTS.md) for source attribution and withheld material.
