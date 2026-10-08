# Research versions and parameter lineage

These snapshots belong to different fitting stages. Do not combine an earlier
coefficient or baseline convention with the current CICTP references/margins.

| Snapshot | c | p | pooled Delta (robots/min) | Role |
|---|---:|---:|---:|---|
| D2, September 2026 |24.374155890965095|−0.9454494315945483|3.1068|Earlier400-scenario development freeze |
| Criterion correction,11 September 2026 |25.399038511341633|−0.9612709429477008|3.1163273712933957|Intermediate criterion-consistent calibration |
| CICTP primary plus E1–E5 |23.841787076606813|−0.9302944983824531|3.3759218049780055|Current full-development geometry-transfer parameters |

`D2_202609/` preserves the exact earlier model values and real original reference,
baseline/sweep/refinement tables. Its archived deployed baseline gate used a
mean-based convention; that convention must not be substituted for the current
CICTP block-specific qualification. Scalar evidence includes historical parsing
behavior and is retained as an observational record, not re-certified here.

`criterion_correction_20260911/` retains the intervening calibration/reference
snapshot. Subsequent primary-block and undefined-denominator corrections,
geometry exclusions and final direct-flow completion produced the CICTP version.

The current CICTP reproduction reads only `paper_CICTP2027/` inputs. It estimates
each outer fold on six cities and uses the separate pooled fit only for Hong Kong
transfer. E1–E5 adds diagnostic/direct-test evidence without changing the frozen
CICTP references or recommendations. Historical D2 data have not been deleted or
silently overwritten. Local paths in exported metadata are redacted; source and
export hashes are recorded in the CICTP input manifest.

The root `paper/` folder remains the 19 September 2026 submission snapshot. The
latest refined manuscript is in `paper_CICTP2027/manuscript/`.
