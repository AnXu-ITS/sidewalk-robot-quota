# Final Consistency Audit

> Scope: search the checkout for stale values, conflicting order, and forbidden
> wording; list every finding; record the correction. Nothing is silently patched:
> corrections are recorded here and in `final_quota_method_config.yaml`.

---

## 1. Stale parameter values (old c / p)

| File | Stale value | Final (frozen) value | Status |
|---|---|---|---|
| `quota_params/quota_params_final.json` | `c=27.1659, p=-0.9334` | `c=24.37, p=-0.945` | STALE (synthetic-line seedwise model) |
| `quota_params/quota_params_seedwise.json` | `c=27.1659, p=-0.9334` | `c=24.37, p=-0.945` | STALE |
| `quota_params/quota_params.json` | `c=28.2216, p=-0.8281` | `c=24.37, p=-0.945` | STALE (mean-based) |
| `pipeline/audit_design.py` | `C_TRUE=27.166, P_TRUE=-0.9334` | — | synthetic preview generator (by design) |
| `pipeline/synthetic_D2_preview.py` | `c=27.166, p=-0.9334` | — | synthetic preview generator (by design) |
| `pipeline/dryrun/candidate_model_parameters.csv` | `c=32.648, p=-0.871, α=0.331` | `c=24.37, p=-0.945, α=0.992±0.154` | STALE (P1b dry-run, not D2) |
| `pipeline/dryrun/formula_selection_table.csv` | `c=32.648, p=-0.871` | `c=24.37, p=-0.945` | STALE (P1b dry-run) |
| `README.md` L57 | `27.17 · (q_p/W)^−0.933` | `24.37 · (q_p/W)^−0.945` | STALE |
| `ground_truth_design_audit_2026-09-03.md` L6 | `c=27.17/p=-0.933` | `24.37/-0.945` | STALE (pre-D2 audit) |

**Correction:** the only authoritative final constants are `c=24.37`, `p=-0.945`
(D2 fit) and `Δ80=3.1068`, recorded in `final_quota_method_config.yaml`. The
`quota_params/*.json` files in this checkout predate the D2 fit and must not be
cited as the final parameters. A reproducibility pass on the machine holding the
D2 reference table should regenerate `quota_params_final.json` from the D2 fit so
the file and the frozen config agree.

## 2. Old D1-only parameters

| File | Stale value | Final value | Status |
|---|---|---|---|
| `pipeline/quota_law_experiment_report.md` L99 | `D1 p̂ = −0.968` (synthetic) | `D1 p = −0.804` (real) | STALE |

The report's D1 exponent is from the synthetic preview, not the real D1 run. The
real chain is `D1 p = −0.804 → D2 p = −0.945`.

## 3. Stale / missing guardrail elements in code

| Issue | Location | Finding |
|---|---|---|
| No additive Q80 margin | `build_final_model.py` `final_predict` | The frozen `Δ80 = 3.1068` subtract is not implemented; the code returns `min(power_law, Q_low)` with no margin. |
| No `base_pass=0⇒0` gate | `build_final_model.py` `final_predict` | The frozen baseline-feasibility guard is absent; the code relies on `x_crit`/`C(W)` proxies only. |
| `estimate_capacity(margin=30.0)` | `fit_quota.py` | This is the **C(W) censoring** margin, unrelated to the Q80 residual margin `Δ80`. Do not confuse the two. |
| Round-to-0.5 deployment | `extend_experiment.py` L296; `rescore_seedwise_full.py` L328–329 | Superseded by `floor`. The frozen deployment is integer `floor`. |

**Correction:** the frozen execution order (see `final_operational_rule.md` §4)
supersedes the code; the code is a pre-freeze snapshot. The exact frozen order is
normative: OOD → `base_pass` → hard zero-guards → nominal → `−Δ80` → `Q_low` →
`q_max` → `floor`.

## 4. Guardrail ordering

No conflicting order exists in the frozen artifacts. The one outcome-relevant
degree of freedom (additive margin vs `Q_low`/`q_max` ceilings) is resolved as
"margin before ceilings" and documented in `final_operational_rule.md` §6.

## 5. "real ground truth" wording

The term appears in internal docs (`README.md`, `实验进度…md`, `配送机器人…md`,
`ground_truth_design_audit…md`, `pipeline/README.md`) and in code identifiers
(`ground_truth.py`, `external_ground_truth.py`, `ground_truth.csv`).

**Correction:** code identifiers may stay, but no paper text may call `q_r*`
"ground truth" / "true quota" / "real capacity". Paper terminology is frozen to
"simulation-derived feasible quota reference" (`claims_boundary.md`).

## 6. Other findings

- `archive/2026-09-03_旧实验与旧数据/` and `CICTP2027/` referenced by `README.md`
  do not exist in this checkout (archived on the prior machine). Not blocking.
- `pipeline/sim/data/cells.json` and `pipeline/cells/selected_cells.json` are
  byte-identical (SHA-256 `7B3C45…`), confirming the copy is in sync.
- The D2 400-combo reference table is not in this checkout; its SHA-256 should be
  recorded from the analysis machine and appended to the frozen config.

## 7. Verdict

No *critical* inconsistency blocks the freeze: the scientific law, the margin, the
guardrails, and the terminology are now fixed in `final_quota_method_config.yaml`
and the freeze documents. The stale JSON/CSV values are **documented, not
silently reused**; they must not appear in the paper.
