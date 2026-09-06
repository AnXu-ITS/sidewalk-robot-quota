# -*- coding: utf-8 -*-
"""
fit_models.py — Phases 5-10: fit candidate formulae, LOCO-city validation,
identifiability comparison, residual diagnostics, physical audit, selection.

Models:
  A   q̂ = c * W * x^p                      (x = q_p/W)
  A+  q̂ = c * W^alpha * x^p
  L   q̂ = c * W^alpha * x^p * (L/L0)^gamma   (skipped w/ note if L has no variance)
  R   q̂ = C(W) * max(0, 1 - (x/x_crit)^beta) (C(W) interpolated from the final
      model's C_W table; beta fitted; x_crit from final model)
  B   SVR on (log W, log x) -> log q̂          (black-box benchmark only)

Input: a reference CSV with columns
  combo_id, cell_id, city, type, context, W, L, qp, x, qr_star, above_upper
(0/1), ood_flags(optional). Rows with qr_star==0 are capacity/guard cases and
are excluded from the interior-law fit (they belong to the guardrail, not the
power law) unless the model can represent them (Model R).
"""
import argparse
import json
import math
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)                     # pipeline/ -> repo root
FINAL_JSON = os.path.join(_REPO, "quota_params", "quota_params_final.json")


def load_final_guards():
    with open(FINAL_JSON, encoding="utf-8") as f:
        d = json.load(f)
    W = np.array(d["C_W"]["W"], dtype=float)
    C = np.array(d["C_W"]["C"], dtype=float)
    Wq = np.array(d["Q_low_W"]["W"], dtype=float)
    Ql = np.array(d["Q_low_W"]["Q"], dtype=float)
    return dict(x_crit=d["x_crit"], W_min=d["W_min"], q_max=d["q_max"],
                C_W=(W, C), Q_low=(Wq, Ql))


G = load_final_guards()


def cap_W(W):
    return np.interp(np.clip(W, G["C_W"][0][0], G["C_W"][0][-1]),
                     G["C_W"][0], G["C_W"][1])


def qlow_W(W):
    return np.interp(np.clip(W, G["Q_low"][0][0], G["Q_low"][0][-1]),
                     G["Q_low"][0], G["Q_low"][1])


def apply_guards(pred, W, x, floor=True):
    """Deployable rule: guards -> level = min(power, Q_low(W)) -> floor."""
    W = np.asarray(W, dtype=float)
    x = np.asarray(x, dtype=float)
    pred = np.asarray(pred, dtype=float)
    pred = np.where((W < G["W_min"]) | (x >= G["x_crit"]), 0.0, pred)
    pred = np.minimum(pred, qlow_W(W))
    pred = np.minimum(pred, G["q_max"])
    return np.floor(pred) if floor else pred


def fit_ols(df, Xcols, ycol):
    """log-log OLS; returns params dict + cov-based SE."""
    X = df[Xcols].values
    y = df[ycol].values
    A = np.hstack([np.ones((len(y), 1)), X])
    (beta, res, rank, sv) = np.linalg.lstsq(A, y, rcond=None)
    resid = y - A @ beta
    n, k = A.shape
    dof = n - k
    s2 = float(resid @ resid) / dof if dof > 0 else np.nan
    cov = s2 * np.linalg.inv(A.T @ A)
    se = np.sqrt(np.diag(cov))
    return beta, se, cov, resid


def model_A(df):
    d = df[(df["qr_star"] > 0) & (df["above_upper"] == 0)].copy()
    d["y"] = np.log(d["qr_star"] / d["W"])
    d["lx"] = np.log(d["x"])
    beta, se, cov, resid = fit_ols(d, ["lx"], "y")
    c, p = math.exp(beta[0]), beta[1]
    se_p = se[1]
    return dict(name="A", params={"c": c, "p": p},
                se={"c": c * se[0], "p": se_p},
                ci95_p=(p - 1.96 * se_p, p + 1.96 * se_p),
                cov=float(cov[0, 1]), n=d.shape[0],
                predict=lambda dd: np.clip(c * dd["W"] * dd["x"] ** p,
                                           0, G["q_max"]))


def model_Aplus(df):
    d = df[(df["qr_star"] > 0) & (df["above_upper"] == 0)].copy()
    d["y"] = np.log(d["qr_star"])
    d["lW"] = np.log(d["W"])
    d["lx"] = np.log(d["x"])
    beta, se, cov, resid = fit_ols(d, ["lW", "lx"], "y")
    c, alpha, p = math.exp(beta[0]), beta[1], beta[2]
    se_alpha = se[1]
    return dict(name="A+", params={"c": c, "alpha": alpha, "p": p},
                se={"c": c * se[0], "alpha": se_alpha, "p": se[2]},
                ci95_alpha=(alpha - 1.96 * se_alpha, alpha + 1.96 * se_alpha),
                ci95_p=(p - 1.96 * se[2], p + 1.96 * se[2]),
                cov=float(cov[1, 2]), n=d.shape[0],
                predict=lambda dd: np.clip(c * dd["W"] ** alpha * dd["x"] ** p,
                                           0, G["q_max"]))


def model_L(df):
    d = df[(df["qr_star"] > 0) & (df["above_upper"] == 0)].copy()
    if "L" not in d.columns or d["L"].nunique() <= 1 or d["L"].std() < 1e-9:
        return dict(name="L", not_identifiable=True,
                    reason="L has no variance under the frozen protocol "
                           "(all cells 50 m; the simulator is length-insensitive "
                           "by construction: per-minute flows + fixed [15,35] m "
                           "measure zone). gamma cannot be estimated.",
                    predict=None)
    L0 = d["L"].median()
    d["y"] = np.log(d["qr_star"])
    d["lW"] = np.log(d["W"])
    d["lx"] = np.log(d["x"])
    d["lL"] = np.log(d["L"] / L0)
    beta, se, cov, resid = fit_ols(d, ["lW", "lx", "lL"], "y")
    c, alpha, p, gamma = math.exp(beta[0]), beta[1], beta[2], beta[3]
    return dict(name="L", params={"c": c, "alpha": alpha, "p": p, "gamma": gamma},
                se={"gamma": se[3]},
                ci95_gamma=(gamma - 1.96 * se[3], gamma + 1.96 * se[3]),
                n=d.shape[0], L0=L0,
                predict=lambda dd: np.clip(
                    c * dd["W"] ** alpha * dd["x"] ** p
                    * (dd["L"] / L0) ** gamma, 0, G["q_max"]))


def model_R(df):
    """Residual-capacity form. C(W) fixed from final model; beta by grid search
    minimizing MAE over interior rows. Represents qr*=0 rows naturally."""
    W = df["W"].values
    C = cap_W(W)
    x = df["x"].values
    xc = G["x_crit"]
    q = df["qr_star"].values
    best = None
    for beta in np.arange(0.1, 8.01, 0.1):
        pred = C * np.clip(1 - (x / xc) ** beta, 0, None)
        mae = float(np.mean(np.abs(pred - q)))
        if best is None or mae < best[1]:
            best = (beta, mae)
    beta = best[0]
    return dict(name="R", params={"beta": beta, "x_crit": xc, "C_W": "final"},
                fit_mae=best[1], n=df.shape[0],
                predict=lambda dd, _beta=beta: cap_W(dd["W"].values)
                * np.clip(1 - (dd["x"].values / xc) ** _beta, 0, None))


def model_SVR(df):
    from sklearn.svm import SVR
    d = df[(df["qr_star"] > 0) & (df["above_upper"] == 0)].copy()
    X = np.column_stack([np.log(d["W"]), np.log(d["x"])])
    y = np.log(d["qr_star"])
    m = SVR(C=10.0, gamma=0.5, epsilon=0.1)
    m.fit(X, y)
    return dict(name="SVR", params={"sv": len(m.support_)}, n=d.shape[0],
                predict=lambda dd: np.clip(
                    np.exp(m.predict(np.column_stack(
                        [np.log(dd["W"]), np.log(dd["x"])]))), 0, G["q_max"]))


def evaluate(model, df):
    if model.get("predict") is None:
        return dict(model=model["name"], not_identifiable=True,
                    reason=model.get("reason", ""))
    pred = np.asarray(model["predict"](df), dtype=float)
    pred = apply_guards(pred, df["W"].values, df["x"].values)
    q = df["qr_star"].values
    e = q - pred
    over = pred > q + 1e-9
    under = pred < q - 1e-9
    ss = 1 - float(np.sum(e ** 2)) / max(1e-12, float(np.sum((q - q.mean()) ** 2)))
    return dict(model=model["name"],
                mae=float(np.mean(np.abs(e))),
                rmse=float(np.sqrt(np.mean(e ** 2))),
                medae=float(np.median(np.abs(e))),
                r2=ss,
                over_rate=float(over.mean()),
                under_rate=float(under.mean()),
                over_mae=float(np.mean(np.abs(e[over]))) if over.any() else 0.0,
                max_over=float(np.max(pred - q)))


def loco(model_fn, df):
    cities = sorted(df["city"].unique())
    rows = []
    for held in cities:
        tr = df[df["city"] != held]
        te = df[df["city"] == held]
        m = model_fn(tr)
        rows.append(evaluate(m, te))
    out = pd.DataFrame(rows)
    out.insert(0, "held_city", cities)
    return out


def resid_diag(model, df):
    pred = np.asarray(model["predict"](df), dtype=float)
    df = df.copy()
    df["e"] = df["qr_star"] - pred
    out = {}
    for col in ["W", "qp", "x"]:
        a = df[[col, "e"]].dropna()
        out[f"pearson_e_{col}"] = float(stats.pearsonr(a[col], a["e"])[0]) \
            if len(a) > 2 else np.nan
        out[f"spearman_e_{col}"] = float(stats.spearmanr(a[col], a["e"])[0]) \
            if len(a) > 2 else np.nan
    if "L" in df.columns and df["L"].nunique() > 1:
        a = df[["L", "e"]].dropna()
        out["pearson_e_L"] = float(stats.pearsonr(a["L"], a["e"])[0])
    else:
        out["pearson_e_L"] = "N/A (no L variance)"
    out["mean_abs_e_by_type"] = df.groupby("type")["e"].apply(
        lambda v: float(np.abs(v).mean())).to_dict()
    out["mean_abs_e_by_city"] = df.groupby("city")["e"].apply(
        lambda v: float(np.abs(v).mean())).to_dict()
    return out


def identifiability(df1, df2):
    rows = []
    for tag, df in (("D1_280", df1), ("D2_280+120", df2)):
        for fn in (model_A, model_Aplus):
            m = fn(df)
            rows.append(dict(dataset=tag, model=m["name"],
                             p=round(m["params"].get("p", np.nan), 4),
                             se_p=round(m["se"].get("p", np.nan), 4),
                             ci95_p=[round(v, 4) for v in m.get("ci95_p",
                                                               (np.nan, np.nan))],
                             cov_cp=round(m.get("cov", np.nan), 4),
                             n=m.get("n")))
    return pd.DataFrame(rows)


def selection_table(loco_rows, models_meta):
    lr = loco_rows.copy()
    if "not_identifiable" not in lr.columns:
        lr["not_identifiable"] = False
    ok = lr[~lr["not_identifiable"].fillna(False).astype(bool)]
    summ = ok.groupby("model").agg(
        loco_mae=("mae", "mean"), loco_rmse=("rmse", "mean"),
        loco_over=("over_rate", "mean")).reset_index()
    t = []
    for m in models_meta:
        row = dict(model=m["name"], params=json.dumps(m.get("params", {})))
        s = summ[summ["model"] == m["name"]]
        if len(s):
            row.update(loco_mae=round(s["loco_mae"].iloc[0], 3),
                       loco_rmse=round(s["loco_rmse"].iloc[0], 3),
                       loco_over=round(s["loco_over"].iloc[0], 3))
        else:
            row.update(loco_mae=None, loco_rmse=None, loco_over=None,
                       note=m.get("reason", "not identifiable"))
        row["physical"] = m.get("physical", "check")
        row["interpretable"] = m.get("interpretable", True)
        t.append(row)
    return pd.DataFrame(t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True, help="reference CSV (main, merged)")
    ap.add_argument("--ref2", default=None, help="second dataset (280+120)")
    ap.add_argument("--outdir", default=".")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    df = pd.read_csv(args.ref)
    print(f"loaded {len(df)} rows from {args.ref}; cities="
          f"{sorted(df['city'].unique())}")
    print(f"qr* distribution: {df['qr_star'].value_counts().sort_index().to_dict()}")
    print(f"above_upper: {int(df['above_upper'].sum())} | qr*=0: "
          f"{int((df['qr_star']==0).sum())}")

    models = []
    for fn in (model_A, model_Aplus, model_L, model_R, model_SVR):
        try:
            m = fn(df)
            models.append(m)
            print(f"[{m['name']}] {m.get('params', m.get('reason', ''))}")
        except Exception as e:
            print(f"[{fn.__name__}] FAILED: {type(e).__name__}: {e}")
            models.append(dict(name=fn.__name__, not_identifiable=True,
                               reason=str(e), predict=None))

    loco_rows = []
    for m in models:
        lr = loco(lambda df_, m_=m: refit(m_["name"], df_), df)
        lr["model"] = m["name"]
        loco_rows.append(lr)
        if "mae" in lr.columns:
            print(f"[{m['name']}] LOCO: "
                  f"mae={lr['mae'].mean():.3f} rmse={lr['rmse'].mean():.3f} "
                  f"over={lr['over_rate'].mean():.3f}")
        else:
            print(f"[{m['name']}] LOCO: not identifiable "
                  f"({m.get('reason', '')[:80]})")
    loco_df = pd.concat(loco_rows, ignore_index=True)
    loco_df.to_csv(os.path.join(args.outdir, "loco_city_results.csv"),
                   index=False)

    # identifiability
    idf = identifiability(df, pd.read_csv(args.ref2) if args.ref2 else df)
    idf.to_csv(os.path.join(args.outdir, "identifiability_comparison.csv"),
               index=False)

    # candidate model parameters (required output)
    param_rows = []
    for m in models:
        for k, v in m.get("params", {}).items():
            se = m.get("se", {}).get(k)
            ci = m.get("ci95_p" if k == "p" else "ci95_alpha" if k == "alpha"
                       else "ci95_gamma", None)
            param_rows.append(dict(model=m["name"], param=k, estimate=v,
                                   se=se, ci95=ci))
        if m.get("not_identifiable"):
            param_rows.append(dict(model=m["name"], param="note",
                                   estimate=m.get("reason", ""), se=None,
                                   ci95=None))
    pd.DataFrame(param_rows).to_csv(
        os.path.join(args.outdir, "candidate_model_parameters.csv"),
        index=False)

    # residual diagnostics for the simplest model A (required output CSV)
    ma = next(m for m in models if m["name"] == "A" and m.get("predict"))
    pred = apply_guards(np.asarray(ma["predict"](df), dtype=float),
                        df["W"].values, df["x"].values)
    rdf = df[["combo_id", "cell_id", "city", "type", "context", "W", "L",
              "qp", "x", "qr_star"]].copy()
    rdf["qhat_A_guarded"] = np.round(pred, 3)
    rdf["e"] = rdf["qr_star"] - rdf["qhat_A_guarded"]
    rdf.to_csv(os.path.join(args.outdir, "residual_diagnostics.csv"),
               index=False)
    rd = resid_diag(ma, df)
    with open(os.path.join(args.outdir, "residual_diagnostics.json"),
              "w", encoding="utf-8") as f:
        json.dump(rd, f, ensure_ascii=False, indent=1, default=str)
    print("residual diagnostics:", json.dumps(rd, ensure_ascii=False,
                                              default=str)[:600])

    sel = selection_table(loco_df, models)
    sel.to_csv(os.path.join(args.outdir, "formula_selection_table.csv"),
               index=False)
    print(sel.to_string(index=False))


def refit(name, df):
    fn = {"A": model_A, "A+": model_Aplus, "L": model_L, "R": model_R,
          "SVR": model_SVR}[name]
    m = fn(df)
    if name == "A+":
        m["name"] = "A+"
    return m


if __name__ == "__main__":
    main()
