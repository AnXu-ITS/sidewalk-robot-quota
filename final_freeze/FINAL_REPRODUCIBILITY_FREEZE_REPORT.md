# FINAL REPRODUCIBILITY FREEZE REPORT

> Scope: housekeeping + repository freeze. No model development.
> Verdict is honest: the method and runtime are frozen and self-consistent; one
> data-restore action remains for a fully self-contained reproducible release.

---

## Q1 — Is `base_pass(q_p)` monotonic enough to compress to `q_{p,base}^max`?

**Not directly verifiable in this checkout; Outcome B removes the need for a
strong monotonicity claim.**

- The frozen criterion (`density ≤ 1.20` AND `0.90 ≤ flow_ratio ≤ 1.20`) is built
  from two terms that cross their thresholds in one direction only, so the pass
  set is *expected* to be a prefix (`1,1,…,1,0,0,…,0`).
- **Existing proxy evidence was consistent with monotonic baseline feasibility,
  but the final D2 baseline table was unavailable for direct verification.** The
  proxy is P1b `qr_star` (not D2 `base_pass`), so it is supporting evidence only,
  never a verified monotonicity result.

**Decision — Outcome B:**

$$
\boxed{
\text{Use discrete offline qualification lookup; do not compress to one threshold}
}
$$

The lookup is represented as a per-sidewalk interval
`[q_{p,last pass}, q_{p,first fail})`, never a fabricated point scalar. This is
strictly honest given sparse `q_p` levels and the absent D2 confirmation.

## Q2 — Online deployment inputs

Outcome B applies, so the **offline lookup** is used as follows:

- Offline: precompute `base_pass` per `(cell, q_p)` and store the per-sidewalk
  interval `[q_{p,last pass}, q_{p,first fail})`.
- Online gate: `q_p ≥ q_{p,first fail} ⇒ q_r^op = 0`; otherwise run the
  closed-form law.
- Online inputs: `(W, q_p, base_pass)` plus the applicability flag and (when the
  geometry/speed guards are active) the corner and `vbar` metadata.

## Q3 — Final D2 dataset

| Field | Value |
|---|---|
| path | `data/final/full_reference_dataset.csv` (source `D:\quota_experiment`) |
| row count | **400** (main 280 + decoupled 120) |
| cities | 7 (amsterdam/melbourne/newtaipei/nyc/taipei 58; seattle/taoyuan 55) |
| base_pass | 349 pass / 51 fail |
| qr_star | 0 in 194 rows, >0 in 206 rows |
| SHA-256 | `b2b6743d22b3fe4496cc11022c65eaf7b80508efa2996cb8f5538049fc4144e9` |

Provenance verified (see `D2_RECONSTRUCTION_VERIFICATION.md`): `qr_star` uses the
corrected per-seed **≥29/30** rule (independent recompute PASS, 349/349).

## Q4 — Is the runtime fully switched to `c=24.37, p=-0.945, Δ=3.1068`?

**Yes.** The frozen runtime `final_freeze/src/operational_quota.py` reads
`final_quota_method_config.json` and applies the frozen order with those constants.
Verified by the mechanical self-test.

## Q5 — Is `27.166 / -0.933` no longer called by default code?

**Yes for the runtime.** The frozen runtime never reads the legacy JSON files.
`quota_params/*.json` are flagged `SUPERSEDED_DO_NOT_USE`. The only remaining
reference is `build_final_model.py` (a pre-freeze fitting script, not the runtime),
which is documented as superseded in `runtime_parameter_sync_audit.md`.

## Q6 — Does the smoke test exactly reproduce `25.75 → 6.75 → 2.75` and `19 → 16 → 7`?

**YES — reproduced exactly.** `src/reproduce_frozen_chain.py` (rule extracted
verbatim from `guardrail_form_audit.py`) on the 400-row table yields:

| Variant | overprediction | max |
|---|---|---|
| G0 nominal | **25.75%** | **19** |
| G1 + Q80 (LOCO fold margins) | **6.75%** | **16** |
| G1 + base_pass==0 → 0 | **2.75%** | **7** |

The authoritative `guardrail_form_audit.py` also re-ran to completion (exit 0)
with its built-in assertions passing (`D80 = 3.1068`, `0.0675/16`,
`0.0275/7`). See `D2_RECONSTRUCTION_VERIFICATION.md`.

## Q7 — Are code, data, config, and paper text fully consistent?

- **Code == config == paper:** YES. `paper_methods_ready.md`,
  `paper_results_ready.md`, `paper_limitations_ready.md`, `claims_boundary.md`
  all use `24.37 / -0.945 / 3.1068` and `25.75 → 6.75 → 2.75`. No stale value
  appears in any paper file.
- **Data:** YES. The D2 table + raw baseline/sweep/refinement CSVs are now in
  `data/final/` (copied from `D:\quota_experiment`), hashes recorded, provenance
  verified.

## Q8 — Is the repository at the "reproducible frozen release" standard?

$$
\boxed{\text{YES — reproducible frozen release}}
$$

The D2 data is present, correct (qr_star = corrected ≥29/30), and the frozen
operational pipeline reproduces `25.75 → 6.75 → 2.75` and `19 → 16 → 7` exactly.
Scientific law, margin, guardrail ordering, runtime, config, hashes, and paper
text are all self-consistent.

Two on-the-record nuances (no action required; see
`D2_RECONSTRUCTION_VERIFICATION.md` §5): (1) `base_pass` is mean-based and differs
from per-seed ≥29/30 in 8/400 decoupled high-q_p rows; (2) the `+Q80` margin is
LOCO fold-calibrated, with `Δ80 = 3.1068` as the pooled representative value.

---

## Final principle

Data restore + verification are **complete** (`D2_DATA_RESTORE_PLAN.md` is now
historical; `D2_RECONSTRUCTION_VERIFICATION.md` is the record). The reproduction
matches `25.75% → 6.75% → 2.75%` and `19 → 16 → 7`.

Project status:

- **Algorithm development: DONE.**
- **Paper writing: can start immediately** (frozen numbers are final and verified).
- **Repository release: READY to tag** (D2 data restored, smoke test PASS).

$$
\boxed{
\text{FREEZE THE REPOSITORY AND MOVE TO PAPER WRITING}
}
$$
