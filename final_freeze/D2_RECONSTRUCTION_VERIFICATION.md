# D2 Reconstruction & Verification — COMPLETE

> The final D2 dataset was located on this machine and verified. No SUMO re-run
> was needed; no rows were fabricated. This replaces the earlier "D2 absent"
> blocker.

---

## 1. Source artifacts found (whole-machine search)

The full analysis-machine directory is present at `D:\quota_experiment` (not in
the OneDrive working tree). All required artifacts exist:

| Artifact | Location (source) | SHA-256 |
|---|---|---|
| `full_reference_dataset.csv` (400 rows) | `pipeline\cells\` | `b2b6743d…4144e9` |
| `main_280_reference_table.csv` | `pipeline\cells\` | `36c8474f…9541f2` |
| `decoupled_120_reference_table.csv` | `pipeline\cells\` | `c74b16d7…b8ac7a` |
| `refined_quota_reference_table.csv` | `pipeline\sim\outputs\refinement\` | `4b9372ee…8f794c` |
| `multicity_baseline.csv` (raw, q_r=0) | `pipeline\sim\outputs\p1_multicity\` | `04a4ee1e…daa271f` |
| `multicity_sweep.csv` (raw sweep) | `pipeline\sim\outputs\p1_multicity\` | `a97556e2…6c89f6` |
| `decoupled_baseline.csv` / `decoupled_sweep.csv` | `pipeline\sim\outputs\decoupled\` | `f4036493…cb3c988` / `c646044d…928456` |
| `refinement_sweep.csv` | `pipeline\sim\outputs\refinement\` | `c711bdc3…ab8f1f7` |

All 11 files were copied into `data/final/` of this repo (hashes preserved;
see `data/final/SHA256SUMS.txt`).

## 2. Dataset reconstruction (from source) — NOT needed, but re-verified

`full_reference_dataset.csv` was rebuilt by `merge_datasets.py` =
`main_280 (280)` + `decoupled (120)` with `qr_star` overwritten by the refinement
table where `changed`:

```
consolidate_reference.py   ->  main_280 / decoupled_120  (per-seed pass_frac >= 29/30)
refine_boundary.py         ->  refined_quota_reference_table (127 rows, 64 changed)
merge_datasets.py          ->  full_reference_dataset (400 rows)
```

Independent recomputation from the RAW sweep/baseline CSVs
(`verify_qrstar_provenance.py`, run fresh) gives **VERDICT: PASS**:

- deployed `qr_star` agrees with the independent **≥29/30** recompute on
  **349/349** tags.
- deployed `qr_star` agrees with the old **>0.5** (buggy) rule on only 134/349.
- 215 tags exist where the 29/30 and >0.5 rules differ — i.e. where the bug
  *would* have mattered. The deployed table uses the corrected 29/30 rule.

**Dataset structure (400 rows):** 7 cities (amsterdam/melbourne/newtaipei/nyc/
taipei 58 each; seattle/taoyuan 55 each); types A 232 / C 140 / B 28;
`base_pass`: 349 pass / 51 fail; `qr_star == 0`: 194, `qr_star > 0`: 206.

## 3. Frozen model parameters — confirmed

- `c = 24.374155890965095`, `p = -0.9454494315945483` (model A).
- `α = 0.992213958115989` (model A+), LOCO MAE = **2.189**.
- `Δ80 = D80_FROZEN = Q0.80(max(0, q_nom − qr*)) = 3.106757 ≈ 3.1068`.

## 4. Frozen chain reproduced (the acceptance test)

Using `src/reproduce_frozen_chain.py` (rule extracted verbatim from
`guardrail_form_audit.py`), on the 400-row table:

| Variant | overprediction | max overprediction |
|---|---|---|
| G0 nominal | **25.75%** | **19** |
| G1 + Q80 (additive, LOCO fold margins) | **6.75%** | **16** |
| G1 + base_pass==0 → 0 | **2.75%** | **7** |

The authoritative `guardrail_form_audit.py` also re-ran to completion (exit 0)
and its built-in assertions passed (`D80 = 3.1068`, Q80 pooled `0.0675 / 16`,
`util_median 0.25`, base_pass guard `0.0275 / 7`).

$$
\boxed{25.75\% \to 6.75\% \to 2.75\% \quad\text{and}\quad 19 \to 16 \to 7\ \text{REPRODUCED}}
$$

## 5. Two nuances recorded (no action required, but on the record)

1. **`base_pass` is mean-based, not per-seed 29/30.** The deployed `base_pass`
   column follows `mean_density ≤ 1.20 AND 0.90 ≤ mean_flow_ratio ≤ 1.20` over the
   q_r=0 seeds (400/400 match). It differs from the per-seed ≥29/30 baseline rule
   in **8/400** rows — all `decoupled` high-q_p cells where the mean passes but
   per-seed noise drops the fraction below 29/30. `qr_star` itself is correctly
   29/30. This does not affect the headline (which was computed with the deployed
   column and reproduces exactly).
2. **The `+Q80` margin is LOCO fold-calibrated.** Each held-out city uses
   `Q0.80(positive residuals over the 6 training cities)`. The single pooled value
   `Δ80 = 3.1068` applied uniformly gives 6.5%, not the frozen 6.75%; the frozen
   6.75% is the fold-calibrated result. `Δ80 = 3.1068` is the representative
   pooled quantity.

## 6. Verdict

The D2 dataset is **present, correct (29/30 for qr_star), and fully verifiable**
without any SUMO re-run. The frozen operational pipeline reproduces the headline
chain exactly. The earlier Q8 blocker is **cleared**.
