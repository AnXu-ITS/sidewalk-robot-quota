# Amsterdam Long-Tail: Failure-Mode Case Study (FROZEN)

> This is a **failure analysis**, not a main performance result, and it is **not** a
> license to add a geometry variable to the main formula. No re-optimization of
> Amsterdam is performed.

---

## 1. Frozen observations (Amsterdam top-tail)

| Observation | Value |
|---|---|
| `q_r* = 0` in the top-tail | **95%** |
| `base_pass = 0` | **90%** |
| Passed original W / x guardrails | **100%** |
| Type-B curved-chain geometry | **100%** |
| Sinuosity | **1.20 – 1.40** |
| Comparison cities' sinuosity | **≤ 1.004** |
| Matched W, x → Amsterdam `q_r*` | **≈ 0.45** |
| Matched W, x → other cities `q_r*` | **≈ 5.90** |

## 2. Interpretation

The Amsterdam tail cells sit at moderate `(W, x)` that the **original W/x
guardrails accept** (hence 100% pass), but whose **pedestrian-only baseline already
fails** (90% `base_pass = 0`) because of the highly sinuous, curved-chain geometry.
Under the frozen method this is caught by the **baseline-feasibility guard**
(`base_pass = 0 ⇒ q_r^op = 0`), which is why Amsterdam held-out overprediction
drops to ≈ 1.7%.

The matched-`(W, x)` contrast — Amsterdam ≈ 0.45 vs other cities ≈ 5.90 — shows the
residual is **not** a scale/calibration error of `(c, p)`: the power law itself is
not the source of the tail. The source is that these cells are geometrically
outside the law's applicability domain.

## 3. Conclusion

$$
\boxed{
\text{the failure is primarily an applicability/geometry issue, not a scale-error issue}
}
$$

## 4. What is NOT concluded

- Sinuosity is **not** added to the main formula (Critical Rule 6).
- Amsterdam geometry is **not** claimed to prove sinuosity is causal (claims boundary).
- No re-fit of `(c, p)` is triggered by this case.
