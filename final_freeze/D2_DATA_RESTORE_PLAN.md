# D2 Data Restore Plan (the only release gate)

> **RESOLVED.** The data was found on this machine at `D:\quota_experiment` and
> copied into `data/final/`; the frozen chain was reproduced exactly
> (25.75→6.75→2.75, 19→16→7). See `D2_RECONSTRUCTION_VERIFICATION.md`. This plan
> is now historical.

> This was a **data-restore + verification** task, not research. No formula,
> margin, or guardrail is touched. The frozen numbers are final.

---

## 1. Files to restore from the analysis machine (full archive, not a trimmed CSV)

Bring back the **authoritative D2 full table** plus the **raw provenance CSVs**:

| # | File | Purpose |
|---|---|---|
| 1 | `full_reference_dataset.csv` | authoritative D2 table (280 + 120 = 400 combos) |
| 2 | `main_280_reference_table.csv` | D1 (280 combos) |
| 3 | `decoupled_120_reference_table.csv` | decoupled supplement (120 combos) |
| 4 | `refined_quota_reference_table.csv` | borderline refinement (corrected PASS_RULE) |
| 5 | `baseline_results.csv` | per-seed pedestrian-only baseline (source of `base_pass`, `pass_frac`) |
| 6 | `sweep_results.csv` | per-seed robot-flow sweep (source of `qr_star`) |

## 2. Required columns in the authoritative D2 table

```
cell_id
city
W
L                      (if present)
qp
x                      (= qp / W)
qr_star                (29/30 corrected)
base_pass
geometry / context / type   (if present)
refinement / source         (if present)
```

Minimum columns consumed by `src/reproduce_metrics.py`: `city, W, qp, qr_star, base_pass`.
The extra columns are retained so that provenance, the Amsterdam failure analysis,
and the in-domain/OOD statistics can all be reproduced — not only the headline chain.

## 3. Restore → verify → freeze flow

```
copy D2 data  →  SHA-256  →  run reproduce_metrics.py  →  verify metrics  →  freeze release
```

1. Copy the files into the repo (e.g. `data/final/`).
2. Record SHA-256 in `SHA256SUMS.txt` and in the `dataset:` block of
   `final_quota_method_config.{yaml,json}`.
3. Run the offline reproduction:
   ```
   python final_freeze/src/reproduce_metrics.py --input <full_reference_dataset.csv>
   ```
4. Verify `REPRODUCTION: PASS` with the exact chain
   `25.75% → 6.75% → 2.75%` and `19 → 16 → 7`.
5. (Recommended) run the direct D2 base_pass monotonicity audit:
   ```
   python final_freeze/src/base_pass_monotonicity.py --input <full_reference_dataset.csv>
   ```
6. Freeze the release and flip Q8 to **YES — reproducible frozen release**.

## 4. Failure discipline (if the reproduction is a MISMATCH)

Do **not** edit the frozen numbers to fit. Investigate, in order:

1. **data version** — is this the corrected 29/30 `PASS_RULE` table? any residual
   `pass_frac > 0.5` contamination from the old rule?
2. **guardrail ordering** — margin applied before `Q_low`/`q_max`?
3. **floor logic** — integer `floor`, not round-to-0.5?
4. **OOD / base_pass logic** — which rows are excluded; `base_pass == 0 ⇒ 0`?
5. **denominator** — held-out-city pooled vs in-domain-only split?

## 5. Project status after this plan

- **Algorithm development: DONE.**
- **Paper writing: can start immediately** (frozen numbers are final; only data
  provenance and per-split denominators are pending the restore).
- **Repository release: waits** for the D2 restore + smoke-test `PASS`, then tag.
