# Reproduction Smoke Test

> Purpose (Part G): reproduce the frozen headline numbers offline (no SUMO).

## 1. Mechanical runtime self-test — PASSED

`src/operational_quota.py` (frozen runtime) self-test:

```
W=2.5 qp=12 base_pass=1 -> 10.0   (nominal 13.84 -> -3.1068 -> floor 10)
W=2.5 qp=12 base_pass=0 ->  0.0   (base_pass gate)
W=1.4 qp=12 base_pass=1 -> None   (OOD: W < 1.6 domain lower bound)
W=5.0 qp=60 base_pass=1 -> None   (OOD: W > 3.0)
W=2.5 qp=200 base_pass=1 -> None  (OOD: qp > 60)
```

The frozen order (`OOD → base_pass → zero_guards → nominal → margin → Q_low →
q_max → floor`) executes correctly and the constants (`c=24.37, p=-0.945,
Δ80=3.1068`) load from the frozen config twin.

## 2. Metric reproduction (25.75 → 6.75 → 2.75; 19 → 16 → 7) — BLOCKED

The offline metric reproduction (`src/reproduce_metrics.py`) is written and ready,
but it requires the final D2 reference table
(`full_reference_dataset.csv`, 400 combos), which is **not in this checkout**
(see `final_d2_provenance.txt`). Running it now exits with status `BLOCKED`
rather than fabricating numbers.

```
$ python src/reproduce_metrics.py --input full_reference_dataset.csv
[BLOCKED] D2 reference table not found: full_reference_dataset.csv
```

## 3. What must happen to unblock

1. Copy `full_reference_dataset.csv` (400 rows, columns
   `city, W, qp, qr_star, base_pass`) from the analysis machine into this repo.
2. Re-run:
   ```
   python final_freeze/src/reproduce_metrics.py --input <path>
   ```
3. The script compares against the frozen chain and prints
   `REPRODUCTION: PASS` or `MISMATCH`.

## 4. Failure discipline

If the reproduction returns `MISMATCH`, we do **not** edit the frozen numbers.
We diagnose, in order: config mismatch, dataset mismatch, ordering mismatch,
floor logic, guardrail mismatch. Only a config/code/dataset correction that is
consistent with the frozen freeze is acceptable; the frozen constants are not
changed to fit the expectation.
