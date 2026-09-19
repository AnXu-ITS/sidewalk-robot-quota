"""Reviewer-driven reanalysis using original seed blocks and explicit flow denominators.

This file writes only new derived products under writing_v2/reviewer_revision.
Frozen V2 exports, models, thresholds, and raw logs are never modified.
"""
from __future__ import annotations
import json, math, sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REV = HERE / "reviewer_revision"
ROOT = HERE.parents[1]
OUT = ROOT / "revision_review"
FREEZE = ROOT / "final_freeze_29of30_corrected"
REV.mkdir(exist_ok=True)
sys.path.insert(0, str(OUT))
sys.path.insert(0, str(FREEZE / "src"))
from runner import fit_model, nominal  # noqa: E402
from operational_quota import OperationalQuota  # noqa: E402

CONF = 29
SEEDS = set(range(30))
SPEED_FLOOR, DENSITY_FLOOR = 0.90, 1.20
FLOW_LO, FLOW_HI = 0.90, 1.20
METHODS = ["M0", "M1", "M2", "M3"]
CFG = json.loads((FREEZE / "final_quota_method_config.json").read_text(encoding="utf-8"))
G = CFG["guardrails"]
TIMEOUT = {
    "TAO-taoyuan-idx6656-0-0|qp75", "TAO-taoyuan-idx6656-0-0|qp125",
    "DC-117|qp90.0", "DC-118|qp120.0", "DC-119|qp150.0",
}


def flow_ok(df: pd.DataFrame, vbar: float) -> pd.Series:
    """Service flag with undefined throughput denominators treated as invalid."""
    defined = df["inflow_ped"].fillna(0).gt(0)
    ratio = df["outflow_ped"] / df["inflow_ped"].replace(0, np.nan)
    return (defined & (df["mean_speed"] / vbar >= SPEED_FLOOR)
            & df["mean_density"].le(DENSITY_FLOOR)
            & ratio.between(FLOW_LO, FLOW_HI))


def load_raw() -> pd.DataFrame:
    d = pd.read_csv(OUT / "revised_analysis/raw_rebuilt_service_per_seed.csv")
    # raw_rebuilt_service_per_seed contains only completed diagnostic runs.
    d = d[d.status.eq("COMPLETED_DIAGNOSTIC")].copy()
    d["seed_block"] = np.where(d.seed.between(0, 29), "original",
                               np.where(d.seed.between(10000, 10029), "independent", "other"))
    return d


def geometry_set() -> set[str]:
    p = OUT / "revised_analysis/geometry_feasibility_v2.csv"
    g = pd.read_csv(p)
    return set(g.loc[g.status.eq("OUT_OF_DOMAIN_GEOMETRY"), "scenario_id"])


def rebuild_reference(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Recompute references from original seed block only and retain exclusions."""
    meta = pd.read_csv(OUT / "reference_dataset_raw_verified_v2.csv")
    geo = geometry_set()
    rows, audit = [], []
    for tag, g in raw[raw.dataset.eq("Development") & raw.seed_block.eq("original")].groupby("tag"):
        b = g[g.qr.eq(0)].copy()
        if tag in geo:
            rows.append(dict(tag=tag, q_star=np.nan, q_star_status="OUT_OF_DOMAIN_GEOMETRY",
                             base_pass=np.nan, baseline_pass_frac=np.nan, vbar=np.nan,
                             baseline_density=np.nan, baseline_flow_ratio=np.nan,
                             n_baseline_seeds=int(b.seed.nunique())))
            continue
        if tag in TIMEOUT:
            rows.append(dict(tag=tag, q_star=np.nan, q_star_status="TECHNICAL_INVALID",
                             base_pass=np.nan, baseline_pass_frac=np.nan, vbar=np.nan,
                             baseline_density=np.nan, baseline_flow_ratio=np.nan,
                             n_baseline_seeds=int(b.seed.nunique())))
            continue
        vbar = float(b.mean_speed.mean()) if len(b) else np.nan
        bok = flow_ok(b, vbar) if len(b) and vbar > 0 else pd.Series(False, index=b.index)
        base_pass = bool(len(b) == 30 and b.seed.nunique() == 30 and bok.sum() >= CONF)
        q_star = 0.0
        flow_rows = []
        for qr, s in g[g.qr.gt(0)].groupby("qr"):
            ok = flow_ok(s, vbar) if vbar > 0 else pd.Series(False, index=s.index)
            complete = len(s) == 30 and s.seed.nunique() == 30
            passing = int(ok.sum())
            if base_pass and complete and passing >= CONF:
                q_star = max(q_star, float(qr))
            flow_rows.append(dict(tag=tag, qr=float(qr), n=len(s), unique_seeds=int(s.seed.nunique()),
                                  denominator_zero=int(s.inflow_ped.fillna(0).le(0).sum()),
                                  passing=passing, status="PASS" if complete and passing >= CONF else "FAIL"))
        status = "CEILING_CENSORED" if q_star >= 20 else ("POSITIVE" if q_star > 0 else "ZERO")
        rows.append(dict(tag=tag, q_star=q_star, q_star_status=status,
                         base_pass=int(base_pass), baseline_pass_frac=float(bok.mean()) if len(b) else np.nan,
                         vbar=vbar, baseline_density=float(b.mean_density.mean()) if len(b) else np.nan,
                         baseline_flow_ratio=float((b.outflow_ped / b.inflow_ped.replace(0, np.nan)).mean()) if len(b) else np.nan,
                         n_baseline_seeds=int(b.seed.nunique())))
        audit.extend(flow_rows)
    # Add excluded tags absent from completed raw logs.
    present = {r["tag"] for r in rows}
    for tag in sorted(TIMEOUT - present):
        rows.append(dict(tag=tag, q_star=np.nan, q_star_status="TECHNICAL_INVALID",
                         base_pass=np.nan, baseline_pass_frac=np.nan, vbar=np.nan,
                         baseline_density=np.nan, baseline_flow_ratio=np.nan, n_baseline_seeds=0))
    r = pd.DataFrame(rows)
    r = meta.rename(columns={"combo_id": "tag"}).drop(
        columns=["q_star", "q_star_status", "base_pass", "baseline_pass_frac", "vbar",
                 "baseline_density", "baseline_flow_ratio", "n_baseline_seeds"], errors="ignore"
    ).merge(r, on="tag", how="left")
    r["fit_eligible_v3"] = r.q_star.between(0, 20, inclusive="neither")
    r["fit_eligible"] = r["fit_eligible_v3"]
    r["qr_star"] = r.q_star
    r.to_csv(REV / "reference_dataset_original_block_v3.csv", index=False)
    pd.DataFrame(audit).to_csv(REV / "reference_flow_audit_v3.csv", index=False)

    old = meta[["combo_id", "q_star", "q_star_status", "base_pass", "n_baseline_seeds"]].rename(columns={"combo_id": "tag"})
    comp = old.merge(r[["tag", "q_star", "q_star_status", "base_pass", "n_baseline_seeds"]], on="tag", suffixes=("_frozen", "_v3"))
    comp["q_star_changed"] = ~np.isclose(comp.q_star_frozen.fillna(-1), comp.q_star_v3.fillna(-1))
    comp["baseline_pass_changed"] = comp.base_pass_frozen.fillna(-1) != comp.base_pass_v3.fillna(-1)
    comp.to_csv(REV / "reference_block_comparison_v3.csv", index=False)
    return r, pd.DataFrame(audit)


def predict(df: pd.DataFrame, method: str, coef, margin: float) -> list[tuple[float | None, str]]:
    nom = nominal(df, method, coef)
    out = []
    oq = OperationalQuota(CFG)
    for i, row in enumerate(df.itertuples()):
        if row.q_star_status == "OUT_OF_DOMAIN_GEOMETRY":
            out.append((np.nan, "OUT_OF_DOMAIN_GEOMETRY")); continue
        if row.q_star_status == "TECHNICAL_INVALID":
            out.append((np.nan, "TECHNICAL_INVALID")); continue
        geom = dict(type=getattr(row, "type", "A"), sinuosity=row.sinuosity,
                    max_turn_deg=getattr(row, "max_turn_deg", 0), cum_turn_deg=getattr(row, "cum_turn_deg", 0))
        if not oq.in_domain(row.W, row.qp, geom):
            out.append((np.nan, "DOMAIN")); continue
        if pd.isna(row.vbar) or pd.isna(row.base_pass):
            out.append((np.nan, "INSUFFICIENT_INPUT")); continue
        if row.base_pass == 0 or row.vbar < .8 or row.qp >= np.interp(row.W, G["C_W"]["W"], G["C_W"]["C"]):
            out.append((0.0, "SERVICE")); continue
        q = math.floor(min(20, np.interp(row.W, G["Q_low"]["W"], G["Q_low"]["Q"]),
                           max(0, nom.iloc[i] - margin)))
        out.append((float(q), "ADMITTED" if q > 0 else "MARGIN_FLOOR"))
    return out


def fit_margin(train: pd.DataFrame, method: str):
    coef, n, rank, cond = fit_model(train, method)
    nt = nominal(train, method, coef)
    if method in ("M0", "M1"):
        nt = np.exp(coef[0]) * train.W * train.x ** coef[1]
    margin = 0.0 if method == "M1" else float(np.quantile(np.maximum(nt - train.q_star, 0), .8))
    return coef, n, rank, cond, margin


def run_loco(ref: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows, pars, assigns = [], [], []
    for city in sorted(ref.city.dropna().unique()):
        train = ref[(ref.city != city) & ref.q_star.notna()]
        test = ref[ref.city == city]
        # Cells remain grouped by city as in the frozen LOCO protocol.
        assert not set(train.cell_id) & set(test.cell_id)
        assigns.extend(dict(combo_id=r.tag, cell_id=r.cell_id, heldout_city=city) for r in test.itertuples())
        for m in METHODS:
            c, n, rank, cond, de = fit_margin(train, m)
            pars.append(dict(city=city, method=m, coefficients=json.dumps(np.asarray(c).tolist()),
                             margin=de, fit_n=n, rank=rank, condition_number=cond,
                             training_cities="|".join(sorted(train.city.unique()))))
            for r, (q, reason) in zip(test.itertuples(), predict(test, m, c, de)):
                rows.append(dict(dataset="Development", scope="LOCO", method=m, tag=r.tag,
                                 cell_id=r.cell_id, city=r.city, quota=q, reason=reason,
                                 q_star=r.q_star, q_star_status=r.q_star_status))
    train = ref[ref.q_star.notna()]
    pooled = {}
    for m in METHODS:
        c, n, rank, cond, de = fit_margin(train, m)
        pooled[m] = (c, de)
        pars.append(dict(city="ALL_DEVELOPMENT", method=m, coefficients=json.dumps(np.asarray(c).tolist()),
                         margin=de, fit_n=n, rank=rank, condition_number=cond,
                         training_cities="|".join(sorted(train.city.unique()))))
    pred = pd.DataFrame(rows)
    metrics = []
    for m, z in pred.groupby("method"):
        a = z[z.quota.notna()].copy(); ex = a.quota - a.q_star
        pos = a.q_star > 0
        ratios = a.loc[a.q_star.gt(0), "quota"] / a.loc[a.q_star.gt(0), "q_star"]
        metrics.append(dict(dataset="Development", scope="LOCO", method=m, total=len(z), n=len(a),
                            abstain=int(z.quota.isna().sum()), positive_recommendations=int((a.quota > 0).sum()),
                            zero=int((a.quota == 0).sum()), reference_exceedance=int((ex > 0).sum()),
                            max_exceedance=float(max(0, ex.max())), mae=float(abs(ex).mean()),
                            median_utilization=float(np.median(ratios)), utilization_n=int(len(ratios)),
                            positive_reference_n=int(pos.sum())))
    out = REV / "loco_predictions_v3.csv"; pred.to_csv(out, index=False)
    mdf = pd.DataFrame(metrics); mdf.to_csv(REV / "loco_metrics_v3.csv", index=False)
    pd.DataFrame(pars).to_csv(REV / "fit_parameters_v3.csv", index=False)
    pd.DataFrame(assigns).to_csv(REV / "fold_assignments_v3.csv", index=False)
    return pred, mdf, pd.DataFrame(pars)


def validate_exact(pred: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for r in pred[pred.quota.gt(0)].itertuples():
        b = raw[(raw.dataset == "Development") & raw.tag.eq(r.tag) & raw.qr.eq(0) & raw.seed.isin(SEEDS)]
        s = raw[(raw.dataset == "Development") & raw.tag.eq(r.tag) & raw.qr.eq(r.quota) & raw.seed.isin(SEEDS)]
        complete = len(b) == 30 and b.seed.nunique() == 30 and len(s) == 30 and s.seed.nunique() == 30
        if not complete:
            status, passing = "UNTESTED", np.nan
        else:
            ok = flow_ok(s, float(b.mean_speed.mean())); passing = int(ok.sum())
            status = "PASS" if passing >= CONF else "FAIL"
        rows.append(dict(dataset="Development", scope="LOCO", method=r.method, tag=r.tag,
                         quota=r.quota, q_star=r.q_star, exact_flow_status=status,
                         passing=passing, reference_exceedance=bool(r.quota > r.q_star)))
    v = pd.DataFrame(rows); v.to_csv(REV / "exact_flow_validation_v3.csv", index=False)
    return v


def hk_references_and_predictions(ref: pd.DataFrame, raw: pd.DataFrame, pars: pd.DataFrame) -> pd.DataFrame:
    """Apply corrected pooled development fits to the 13 original + 5 repaired configs."""
    hk_old = pd.read_csv(OUT / "revised_analysis/HK_COMBINED_ANALYSIS_V2.csv")
    hk_tags = hk_old[["tag", "configuration"]].drop_duplicates()
    hk_idx = pd.read_csv(HERE / "raw_index_writing.csv")[["spec_hash", "configuration"]]
    hkraw = raw[raw.dataset.eq("Hong Kong")].merge(hk_idx, on="spec_hash", how="left")
    valid_meta = pd.read_csv(FREEZE / "data/hk_original_valid.csv").set_index("cell_id")
    repaired_meta = pd.read_csv(ROOT / "external_validation/hong_kong/sites/HONG_KONG_FORMAL_SAMPLE_FREEZE.csv").set_index("cell_id")
    repaired_ref = pd.read_csv(ROOT / "external_validation/hong_kong/runs/formal/hk_reference_qr_star.csv").set_index("cell_id")
    pooled = {r.method: (np.array(json.loads(r.coefficients)), float(r.margin))
              for r in pars[pars.city.eq("ALL_DEVELOPMENT")].itertuples()}
    out = []
    for conf in ["ORIGINAL", "REPAIRED"]:
        for tag in sorted(hk_tags.loc[hk_tags.configuration.eq(conf), "tag"]):
            entrance = "historical" if conf == "ORIGINAL" else "nearest-safe-anchor-v1"
            z = hkraw[hkraw.tag.eq(tag) & hkraw.configuration.eq(entrance) & hkraw.seed.isin(SEEDS)]
            b = z[z.qr.eq(0)]; vbar = float(b.mean_speed.mean()) if len(b) else np.nan
            bok = flow_ok(b, vbar) if len(b) and vbar > 0 else pd.Series(False, index=b.index)
            bp = int(len(b) == 30 and b.seed.nunique() == 30 and bok.sum() >= CONF)
            qstar = 0.0
            for qr, s in z[z.qr.gt(0)].groupby("qr"):
                ok = flow_ok(s, vbar) if vbar > 0 else pd.Series(False, index=s.index)
                if len(s) == 30 and s.seed.nunique() == 30 and ok.sum() >= CONF and bp:
                    qstar = max(qstar, float(qr))
            meta = valid_meta.loc[tag] if conf == "ORIGINAL" else repaired_meta.loc[tag]
            qp = float(meta.qp) if hasattr(meta, "qp") else float(repaired_ref.loc[tag, "qp"])
            one = pd.DataFrame([dict(combo_id=tag, cell_id=tag, W=float(meta.W), qp=qp, x=qp/float(meta.W),
                                     sinuosity=float(getattr(meta, "sinuosity", 1.0)), max_turn_deg=float(getattr(meta, "max_turn_deg", 0.0)),
                                     cum_turn_deg=float(getattr(meta, "cum_turn_deg", 0.0)), type="A", vbar=vbar, base_pass=bp,
                                     q_star=qstar, q_star_status="CEILING_CENSORED" if qstar >= 20 else ("POSITIVE" if qstar > 0 else "ZERO"))])
            for m, (c, de) in pooled.items():
                q, reason = predict(one, m, c, de)[0]
                if q is None or (isinstance(q, float) and np.isnan(q)):
                    status = "ABSTAIN"
                elif q == 0:
                    status = "ZERO"
                else:
                    s = z[z.qr.eq(q)]
                    complete = len(s) == 30 and s.seed.nunique() == 30
                    ok = flow_ok(s, vbar) if complete else pd.Series(False, index=s.index)
                    status = "PASS" if complete and ok.sum() >= CONF else ("FAIL" if complete else "UNTESTED")
                out.append(dict(tag=tag, method=m, quota=q, reason=reason, q_star=qstar,
                                configuration=conf, exact_flow_status=status, baseline_pass=bp, baseline_n=int(len(b)),
                                baseline_denominator_zero=int(b.inflow_ped.fillna(0).le(0).sum())))
    h = pd.DataFrame(out); h.to_csv(REV / "hk_analysis_v3.csv", index=False); return h


def main():
    raw = load_raw()
    ref, flow_audit = rebuild_reference(raw)
    pred, met, pars = run_loco(ref)
    exact = validate_exact(pred, raw)
    hk = hk_references_and_predictions(ref, raw, pars)
    # Quantify denominator-zero incidence for the reviewer response.
    d = raw[raw.seed_block.eq("original")].copy()
    d["zero_denominator"] = d.inflow_ped.fillna(0).le(0)
    den = d.groupby(["dataset", d.qr.eq(0).map({True: "baseline", False: "mixed"})]).agg(
        rows=("seed", "size"), denominator_zero=("zero_denominator", "sum"), tags=("tag", "nunique"))
    den.to_csv(REV / "denominator_zero_diagnostics_v3.csv")
    comp = pd.read_csv(REV / "reference_block_comparison_v3.csv")
    summary = dict(reference_counts=ref.q_star_status.value_counts().to_dict(),
                   q_star_changes=comp.loc[comp.q_star_changed, ["tag", "q_star_frozen", "q_star_v3"]].to_dict("records"),
                   baseline_pass_changes=int(comp.baseline_pass_changed.sum()),
                   denominator_zero=den.reset_index().to_dict("records"),
                   loco=met.to_dict("records"),
                   exact=exact.exact_flow_status.value_counts().to_dict(),
                   hk={"|".join(map(str, k)): int(v) for k, v in hk.groupby(["configuration", "method", "exact_flow_status"]).size().to_dict().items()})
    (REV / "reviewer_reanalysis_v3.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
