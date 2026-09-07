# -*- coding: utf-8 -*-
"""
Section 9 — read-only operational-rule check for the HK external test.

Loads the FROZEN runtime and config, verifies the frozen constants and city
list (HK must be absent), then evaluates the HK micro-cells through the frozen
rule WITHOUT modifying anything. No re-fitting, no parameter tuning.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
FREEZE = os.path.join(REPO, "final_freeze")
sys.path.insert(0, os.path.join(FREEZE, "src"))

import operational_quota as oq  # noqa: E402

CONFIG_YAML = os.path.join(FREEZE, "final_quota_method_config.yaml")
CONFIG_JSON = os.path.join(FREEZE, "final_quota_method_config.json")

FROZEN_C = 24.374155890965095
FROZEN_P = -0.9454494315945483
FROZEN_DELTA = 3.1068


def main():
    out = {}
    m = oq.OperationalQuota()

    # 1) frozen constants
    out["constants"] = dict(c=m.c, p=m.p, delta=m.delta)
    ok_const = (abs(m.c - FROZEN_C) < 1e-12 and
                abs(m.p - FROZEN_P) < 1e-12 and
                abs(m.delta - FROZEN_DELTA) < 1e-9)
    out["constants_match_frozen"] = bool(ok_const)

    # 2) city list / HK absence
    cfg = oq.load_config(os.path.join(FREEZE, "final_quota_method_config.json"))
    cities = cfg.get("dataset", {}).get("cities")
    out["config_cities"] = cities
    out["hongkong_absent"] = (isinstance(cities, list) and "hongkong" not in
                              [str(c).lower() for c in cities])
    out["dataset_ref"] = dict(
        path=cfg.get("dataset", {}).get("path"),
        sha256=cfg.get("dataset", {}).get("sha256"),
        rows=cfg.get("dataset", {}).get("rows"),
    )
    bq = cfg.get("baseline_qualification", {})
    out["baseline_qualification_frozen"] = dict(
        engine=bq.get("engine"), seeds=bq.get("seeds"),
        pass_threshold=bq.get("pass_threshold"),
        density_limit=bq.get("density_limit"),
        flow_ratio=[bq.get("flow_ratio_min"), bq.get("flow_ratio_max")],
    )

    # 3) HK cells through the frozen rule (read-only)
    cells = {
        "HK-ST-01": dict(W=2.331, qp=20.0, geom=dict(type="A", sinuosity=1.0)),
        "HK-ST-02": dict(W=2.657, qp=20.0, geom=dict(type="A", sinuosity=1.0)),
        "HK-ST-03": dict(W=0.921, qp=20.0, geom=dict(type="C", sinuosity=1.0176)),
    }
    out["cells"] = {}
    for cid, d in cells.items():
        W, qp, geom = d["W"], d["qp"], d["geom"]
        in_dom = m.in_domain(W, qp, geom)
        x = qp / W
        q_bp1 = m.quota(W, qp, 1, geom, vbar=None)
        q_bp0 = m.quota(W, qp, 0, geom, vbar=None)
        out["cells"][cid] = dict(
            W=W, qp=qp, x=round(x, 4), in_domain=in_dom,
            quota_base_pass_1=q_bp1, quota_base_pass_0=q_bp0,
        )

    # 4) execution-order audit (frozen order string, unchanged)
    out["execution_order_frozen"] = (
        "OOD -> base_pass -> zero_guards -> nominal -> margin -> "
        "Q_low -> q_max -> floor")
    out["guardrails_frozen"] = dict(
        W_min=m.W_min, x_crit=m.x_crit, q_max=m.q_max,
        Q_low_W=m.QW, Q_low_Q=m.QQ, C_W=m.CW, C_C=m.CC,
        sharp=m.sharp, vbar_min=m.vbar_min,
        W_domain=[m.W_lo, m.W_hi], qp_max=m.qp_max,
        type_in_domain=m.type_in_domain,
        type_b_sinuosity_max=m.type_b_sinuosity_max,
    )

    with open(os.path.join(HERE, "reports", "hk_operational_rule_check.json"),
              "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False, default=str)

    print(json.dumps(out, indent=2, default=str))
    print("\nconstants_match_frozen:", ok_const)
    print("hongkong_absent_from_D2:", out["hongkong_absent"])


if __name__ == "__main__":
    main()
