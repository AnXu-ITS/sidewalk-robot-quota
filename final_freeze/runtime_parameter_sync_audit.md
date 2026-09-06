# Runtime Parameter Sync Audit

> Purpose (Part D): make paper parameters == frozen config == runtime parameters,
> and stop any default code path from reading the old `27.166 / -0.933` values.

---

## 1. What the runtime read BEFORE this freeze

| Component | Reads | Values | Problem |
|---|---|---|---|
| `build_final_model.py::load_seedwise_model()` | `quota_params_seedwise.json` | `c=27.166, p=-0.933` | old pre-D2 |
| `build_final_model.py::final_predict()` | hardcoded `QLOW_*`, `SHARP_DEG`, `VBAR_MIN` | — | no margin, no base_pass gate |
| `external_ground_truth.py` / `external_analysis.py` | seedwise/final JSON | `c=27.166, p=-0.933` | old pre-D2 |

The frozen values `c=24.37, p=-0.945, Δ80=3.1068` were **not** present anywhere in
the runtime path, and neither the additive Q80 margin nor the `base_pass=0 ⇒ 0`
gate were implemented in `final_predict`.

## 2. What was changed (this freeze)

1. **Single source of truth created:**
   - `final_freeze/final_quota_method_config.yaml` (human-readable, full schema)
   - `final_freeze/final_quota_method_config.json` (identical runtime twin)
2. **Frozen runtime created:** `final_freeze/src/operational_quota.py` reads the
   JSON twin and implements the exact frozen order
   `OOD → base_pass → zero_guards → nominal → margin → Q_low → q_max → floor`,
   with `c=24.37`, `p=-0.945`, `Δ80=3.1068`.
3. **Legacy parameters marked:** `quota_params/SUPERSEDED_DO_NOT_USE.md` flags the
   three old JSON files as pre-D2 and points to the frozen config.

## 3. Final runtime constants (verified)

| Constant | Value | Source |
|---|---|---|
| `c` | 24.37 | `final_quota_method_config.json → nominal_model.c` |
| `p` | -0.945 | `… → nominal_model.p` |
| `Δ80` | 3.1068 (additive) | `… → safety_margin.delta` |
| `W_min` | 1.6 | `… → guardrails.W_min` |
| `x_crit` | 33.3333 | `… → guardrails.x_crit` |
| `q_max` | 20.0 | `… → guardrails.q_max` |
| `Q_low(W)` | knots [1.5..3.0]→[0,5,6,8,10,18,20,20] | `… → guardrails.Q_low` |
| `C(W)` | knots [1.5..3.0]→[10,35,35,45,45,55,90,90] | `… → guardrails.C_W` |
| `base_pass` gate | `base_pass==0 ⇒ 0` | `… → execution_order[1]` |
| floor rule | `floor(q_hat)` | `… → execution_order[7]` |

## 4. Runtime self-test (mechanical)

`operational_quota.py` self-test outputs (verified):

```
W=2.5 qp=12 base_pass=1 -> 10.0   (nominal 13.84 -> -3.1068 -> floor 10)
W=2.5 qp=12 base_pass=0 ->  0.0   (base_pass gate)
W=1.4 qp=12 base_pass=1 -> None   (OOD: W < 1.6 domain lower bound)
W=5.0 qp=60 base_pass=1 -> None   (OOD: W > 3.0)
W=2.5 qp=200 base_pass=1 -> None  (OOD: qp > 60)
```

## 5. Residual notes (not blockers)

- `build_final_model.py` remains a **pre-freeze fitting script** (it re-fits from
  the sweep CSVs and writes `quota_params_final.json`). It is NOT the frozen
  runtime. The frozen runtime is `operational_quota.py`.
- Because `W_min = 1.6` equals the applicability-domain lower bound `W_lo = 1.6`,
  the OOD gate (Step 0) subsumes the `W < W_min` zero-guard for `W < 1.6`; the
  `W_min` guard is retained in the ordering for robustness and spec completeness.
- The additive margin is applied **before** the `Q_low`/`q_max` ceilings (see
  `final_operational_rule.md` §6).

## 6. Verdict

The runtime is fully switched to `c=24.37, p=-0.945, Δ=3.1068`, and no default
code path reads the old values. Paper parameters == frozen config == runtime
parameters.
