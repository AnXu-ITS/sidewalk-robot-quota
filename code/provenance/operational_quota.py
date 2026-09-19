# -*- coding: utf-8 -*-
"""
operational_quota.py  —  FROZEN RUNTIME (no SUMO, no re-fitting)

Single runtime implementation of the frozen operational quota rule.
Reads final_quota_method_config.json (the machine twin of the frozen YAML).

Frozen execution order (must NOT be reordered):

    OOD -> base_pass -> zero_guards -> nominal -> margin -> Q_low -> q_max -> floor

Pure stdlib (no numpy/pandas) so it runs anywhere.
"""
import json
import math
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "final_quota_method_config.json")


def load_config(path=CONFIG_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _interp(x, xs, ys):
    """Linear interpolation / flat extension (np.interp behaviour)."""
    x = float(x)
    if x <= xs[0]:
        return float(ys[0])
    if x >= xs[-1]:
        return float(ys[-1])
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            t = (x - xs[i]) / (xs[i + 1] - xs[i])
            return ys[i] + t * (ys[i + 1] - ys[i])
    return float(ys[-1])


class OperationalQuota:
    def __init__(self, config=None):
        self.cfg = config or load_config()
        self.c = float(self.cfg["nominal_model"]["c"])
        self.p = float(self.cfg["nominal_model"]["p"])
        self.delta = float(self.cfg["safety_margin"]["delta"])
        g = self.cfg["guardrails"]
        self.W_min = float(g["W_min"])
        self.x_crit = float(g["x_crit"])
        self.q_max = float(g["q_max"])
        self.QW = [float(w) for w in g["Q_low"]["W"]]
        self.QQ = [float(q) for q in g["Q_low"]["Q"]]
        self.CW = [float(w) for w in g["C_W"]["W"]]
        self.CC = [float(c_) for c_ in g["C_W"]["C"]]
        self.sharp = {k: float(v) for k, v in g["sharp_corner_guard"].items()}
        self.vbar_min = float(g["absolute_speed_floor"]["vbar_min"])
        d = self.cfg["applicability_domain"]
        self.W_lo, self.W_hi = [float(v) for v in d["W_range"]]
        self.qp_max = float(d["q_p_max"])
        self.type_in_domain = [str(t).upper()
                               for t in d.get("type_in_domain", ["A", "B"])]
        self.type_b_sinuosity_max = float(d.get("type_b_sinuosity_max", 1.05))

    # ---- Step 0: OOD ------------------------------------------------------
    def in_domain(self, W, qp, geom=None):
        if not (self.W_lo <= W <= self.W_hi):
            return False
        if qp > self.qp_max:
            return False
        if (qp / W) >= self.x_crit:
            return False
        if geom is not None:
            # geometry type / sinuosity gate: Type A, or Type B with
            # sinuosity <= type_b_sinuosity_max (per the frozen applicability
            # domain). Type C and sinuous Type B are out-of-domain.
            gtype = geom.get("type")
            if gtype is not None:
                gtype = str(gtype).upper()
                if gtype not in self.type_in_domain:
                    return False
                if gtype == "B" and \
                        float(geom.get("sinuosity", 0.0)) > self.type_b_sinuosity_max:
                    return False
            # sharp-corner guard
            mt = float(geom.get("max_turn_deg", 0.0))
            cum = float(geom.get("cum_turn_deg", 0.0))
            conc = (mt / cum) if cum > 1e-6 else 0.0
            if mt >= self.sharp["max_turn_min_deg"] and \
               cum >= self.sharp["cum_turn_min_deg"] and \
               conc >= self.sharp["concentration_min"]:
                return False
        return True

    # ---- full frozen rule -------------------------------------------------
    def quota(self, W, qp, base_pass, geom=None, vbar=None):
        """Return the frozen operational quota q_r^op (float, floored).

        OOD returns None (fallback: no closed-form recommendation).
        """
        # Step 0: OOD gate
        if not self.in_domain(W, qp, geom):
            return None
        # Step 1: baseline qualification
        if int(base_pass) == 0:
            return 0.0
        # Step 2: hard admissibility zero-guards
        if W < self.W_min:
            return 0.0
        x = qp / W
        if x >= self.x_crit:
            return 0.0
        if qp >= _interp(W, self.CW, self.CC):
            return 0.0
        if geom is not None:
            mt = float(geom.get("max_turn_deg", 0.0))
            cum = float(geom.get("cum_turn_deg", 0.0))
            conc = (mt / cum) if cum > 1e-6 else 0.0
            if mt >= self.sharp["max_turn_min_deg"] and \
               cum >= self.sharp["cum_turn_min_deg"] and \
               conc >= self.sharp["concentration_min"]:
                return 0.0
        if vbar is not None and float(vbar) < self.vbar_min:
            return 0.0
        # Step 3: nominal law
        q = self.c * W * (x ** self.p)
        # Step 4: Q80 additive margin
        q = max(0.0, q - self.delta)
        # Step 5: low-flow ceiling
        q = min(q, _interp(W, self.QW, self.QQ))
        # Step 6: sweep ceiling
        q = min(q, self.q_max)
        # Step 7: integer floor
        return float(math.floor(q))


def operational_quota(W, qp, base_pass, geom=None, vbar=None, config=None):
    return OperationalQuota(config).quota(W, qp, base_pass, geom, vbar)


if __name__ == "__main__":
    # mechanical self-test (no claim about D2 numbers)
    m = OperationalQuota()
    cases = [
        # (W, qp, base_pass, geom, vbar) -> expected
        (2.5, 12, 1, None, None, 10),          # nominal(13.84) -> -3.1068 -> floor = 10
        (2.5, 12, 0, None, None, 0),           # base_pass gate
        (1.4, 12, 1, None, None, None),        # OOD: W < 1.6 domain lower bound (Step 0)
        (5.0, 60, 1, None, None, None),        # OOD: W > 3.0
        (2.5, 200, 1, None, None, None),       # OOD: qp > 60
    ]
    for W, qp, bp, geom, vbar, exp in cases:
        got = m.quota(W, qp, bp, geom, vbar)
        print(f"W={W:>4} qp={qp:>4} base_pass={bp} -> {got} (expected {exp})")
    print("runtime self-test complete")
