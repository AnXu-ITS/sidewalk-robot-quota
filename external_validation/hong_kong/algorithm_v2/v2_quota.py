# -*- coding: utf-8 -*-
"""v2 quota proposal (MODEL REVISION — separate from the frozen v1 runtime).

v2 differs from the frozen rule in exactly two places, per the research owner's
directive:

  1. Width handling (remove abstention for wide / complex):
       - Type A/B, W > 3.0 m        -> W_eff = 3.0 m (clamp to domain top).
       - Type C (complex polygon)   -> W_eff = width_p10 (bottleneck width).
       - W_eff < 1.6 m              -> still OOD (narrow lower bound unchanged).
  2. Guardrail segmentation: the deployment margin Delta is no longer the single
     global 3.1068; it is a per-width-bin margin fitted on the D2 training cities
     (NOT on Hong Kong) to keep 0% overprediction per bin while maximising
     utilisation.

Everything else (base_pass gate, C(W), Q_low(W), q_max, sharp-corner, vbar floor,
integer floor, execution order) is kept identical to the frozen rule.
"""
import json
import math
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_FREEZE = os.path.join(_REPO, "final_freeze")


def _interp(x, xs, ys):
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


class V2Quota:
    def __init__(self, margin_bins, cfg=None):
        cfg = cfg or json.load(open(os.path.join(
            _FREEZE, "final_quota_method_config.json"), encoding="utf-8"))
        self.c = float(cfg["nominal_model"]["c"])
        self.p = float(cfg["nominal_model"]["p"])
        g = cfg["guardrails"]
        self.W_min = float(g["W_min"])
        self.x_crit = float(g["x_crit"])
        self.q_max = float(g["q_max"])
        self.QW = [float(w) for w in g["Q_low"]["W"]]
        self.QQ = [float(q) for q in g["Q_low"]["Q"]]
        self.CW = [float(w) for w in g["C_W"]["W"]]
        self.CC = [float(c_) for c_ in g["C_W"]["C"]]
        self.sharp = {k: float(v) for k, v in g["sharp_corner_guard"].items()}
        self.vbar_min = float(g["absolute_speed_floor"]["vbar_min"])
        d = cfg["applicability_domain"]
        self.W_lo, self.W_hi = float(d["W_range"][0]), float(d["W_range"][1])
        self.qp_max = float(d["q_p_max"])
        self.type_b_sinuosity_max = float(d["type_b_sinuosity_max"])
        # margin bins: list of (w_lo, w_hi, delta); last tuple may have w_hi=inf
        self.margin_bins = sorted(margin_bins, key=lambda t: t[0])

    def margin_for(self, W):
        for lo, hi, d in self.margin_bins:
            if lo <= W < hi:
                return float(d)
        return float(self.margin_bins[-1][2])

    def quota(self, W, qp, base_pass, geom=None, vbar=None, geometry_type=None,
              width_p10=None):
        """Return v2 operational quota, or None when still OOD.

        Only THREE changes vs the frozen rule:
          1. wide W -> clamp W_eff to 3.0 (A/B) / bottleneck width_p10 (C)
          2. complex type C admitted via bottleneck width (instead of OOD)
          3. segmented per-bin margin replaces the single global delta
        Every other OOD gate (narrow <1.6, qp>60, x>=33.33, type-B sinuosity
        >1.05, sharp corner) is UNCHANGED and returns None (abstain).
        """
        # ---- v2 width resolution ----
        gtype = (geometry_type or (geom or {}).get("type") or "A")
        gtype = str(gtype).upper()
        if gtype == "C":
            W_eff = float(width_p10 if width_p10 is not None else W)
        else:
            W_eff = float(W)
        W_eff = min(W_eff, self.W_hi)  # clamp wide to 3.0 (all types)

        # ---- OOD gate (mirrors frozen in_domain, with v2 width resolution) ----
        if W_eff < self.W_lo:
            return None  # narrow lower bound still OOD
        if qp > self.qp_max:
            return None
        x = qp / W_eff
        if x >= self.x_crit:
            return None
        if gtype not in ("A", "B", "C"):
            return None
        if gtype == "B":
            sin = float((geom or {}).get("sinuosity", 0.0))
            if sin > self.type_b_sinuosity_max:
                return None  # sinuous B stays OOD (unchanged)
        if geom is not None:
            mt = float(geom.get("max_turn_deg", 0.0))
            cum = float(geom.get("cum_turn_deg", 0.0))
            conc = (mt / cum) if cum > 1e-6 else 0.0
            if mt >= self.sharp["max_turn_min_deg"] and \
               cum >= self.sharp["cum_turn_min_deg"] and \
               conc >= self.sharp["concentration_min"]:
                return None  # sharp corner stays OOD (unchanged)

        # ---- baseline qualification ----
        if int(base_pass) == 0:
            return 0.0
        # ---- hard admissibility zero-guards (unchanged) ----
        if qp >= _interp(W_eff, self.CW, self.CC):
            return 0.0
        if vbar is not None and float(vbar) < self.vbar_min:
            return 0.0
        # ---- nominal law on W_eff ----
        q = self.c * W_eff * (x ** self.p)
        # ---- segmented margin (replaces global 3.1068) ----
        q = max(0.0, q - self.margin_for(W_eff))
        q = min(q, _interp(W_eff, self.QW, self.QQ))
        q = min(q, self.q_max)
        return float(math.floor(q))
