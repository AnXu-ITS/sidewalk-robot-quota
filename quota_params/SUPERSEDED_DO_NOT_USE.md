# SUPERSEDED — DO NOT USE (pre-D2 calibration parameters)

The JSON files in this directory predate the final D2 (280+120=400 combo) fit and
must NOT be cited as the final quota-law parameters.

| File | Contents | Status |
|---|---|---|
| `quota_params_final.json` | `c=27.1659, p=-0.9334` (synthetic-line seedwise model) | SUPERSEDED_DO_NOT_USE |
| `quota_params_seedwise.json` | `c=27.1659, p=-0.9334` | SUPERSEDED_DO_NOT_USE |
| `quota_params.json` | `c=28.2216, p=-0.8281` (mean-based) | SUPERSEDED_DO_NOT_USE |

**Authoritative final parameters** (frozen, D2 fit):

```
c = 24.37
p = -0.945
Delta_80 = 3.1068   (additive Q80 margin)
```

These live in the single source of truth:

- `final_freeze/final_quota_method_config.yaml`  (human-readable)
- `final_freeze/final_quota_method_config.json`  (runtime-readable twin)
- `final_freeze/src/operational_quota.py`        (frozen runtime)

The frozen runtime reads the config twin, NOT these legacy JSON files. The legacy
files are retained for provenance of the pre-D2 calibration only.
