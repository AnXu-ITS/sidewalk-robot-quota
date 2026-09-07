"""Independent, offline paper-readiness audit. Does not modify frozen inputs."""
from pathlib import Path
import contextlib
import importlib.util
import io
import json
import math

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
DATA = ROOT / 'data/final'
df = pd.read_csv(DATA / 'full_reference_dataset.csv')
base = pd.concat([pd.read_csv(DATA / f'{p}_baseline.csv') for p in ['multicity', 'decoupled']], ignore_index=True)
sweep = pd.concat([pd.read_csv(DATA / f'{p}_sweep.csv') for p in ['multicity', 'decoupled']] + [pd.read_csv(DATA / 'refinement_sweep.csv')], ignore_index=True)
df['in_domain'] = (df.W.between(1.6, 3.0) & (df.qp <= 60) & (df.x < 33.333333333333336)
                   & ((df.type == 'A') | ((df.type == 'B') & (df.sinuosity <= 1.05))))

def fit(d, plus=False):
    d = d[(d.qr_star > 0) & (d.above_upper == 0)]
    if plus:
        X = np.column_stack([np.ones(len(d)), np.log(d.W), np.log(d.x)])
        y = np.log(d.qr_star)
    else:
        X = np.column_stack([np.ones(len(d)), np.log(d.x)])
        y = np.log(d.qr_star/d.W)
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    err = y-X@beta
    se = np.sqrt(np.diag((err@err)/(len(d)-len(beta))*np.linalg.inv(X.T@X)))
    return beta, se, len(d)

def predict(d, beta):
    return np.exp(beta[0])*d.W.to_numpy()*(d.x.to_numpy()**beta[1])

def guards(d, q):
    return np.floor(np.maximum(0, np.minimum(np.minimum(np.where((d.W<1.6)|(d.x>=33.333333333333336), 0, q),
        np.interp(d.W, [1.5,1.6,1.7,1.8,2.1,2.4,2.7,3.0], [0,5,6,8,10,18,20,20])),20)))

def metrics(d, pred):
    q=d.qr_star.to_numpy(); pred=np.asarray(pred); pos=q>0; e=pred-q
    return dict(n=len(d), n_positive=int(pos.sum()), n_over=int((e>1e-9).sum()),
        over_pct=float(100*np.mean(e>1e-9)), max_over=float(max(0,e.max())),
        mae=float(np.mean(abs(e))), zero_pct=float(100*np.mean(pred==0)),
        mean_loss_all=float(np.maximum(0,-e).mean()),
        mean_loss_positive=float(np.maximum(0,-e[pos]).mean()) if pos.any() else None,
        median_util_positive=float(np.median(pred[pos]/q[pos])) if pos.any() else None,
        positive_reference_zero_pct=float(100*np.mean(pred[pos]==0)) if pos.any() else None)

def loco(d):
    d=d.copy().reset_index(drop=True); g0=np.zeros(len(d)); g1=g0.copy(); folds=[]
    for city in sorted(d.city.unique()):
        tr=d[d.city!=city]; test=d.city==city; te=d[test]
        b,_,n=fit(tr); margin=float(np.quantile(np.maximum(0,predict(tr,b)-tr.qr_star),.8))
        g0[test]=guards(te,predict(te,b)); g1[test]=guards(te,predict(te,b)-margin)
        folds.append(dict(city=city,c=float(np.exp(b[0])),p=float(b[1]),delta=margin,fit_n=n))
    d['G0']=g0; d['G1']=g1; d['G1b']=np.where(d.base_pass==0,0,g1)
    return d,folds

dl,folds=loco(df)
rows=[]
for scope,mask in [('all',np.ones(len(dl),bool)),('in_domain',dl.in_domain),('OOD',~dl.in_domain)]:
    for variant in ['G0','G1','G1b']:
        rows.append(dict(scope=scope,variant=variant,**metrics(dl[mask],dl.loc[mask,variant])))
pd.DataFrame(rows).to_csv(OUT/'strict_loco_metrics.csv',index=False)
pd.DataFrame(folds).to_csv(OUT/'strict_loco_folds.csv',index=False)
city_metrics=[]
for (city,ind),d in dl.groupby(['city','in_domain']):
    city_metrics.append(dict(city=city,in_domain=bool(ind),**metrics(d,d.G1b)))
pd.DataFrame(city_metrics).to_csv(OUT/'city_domain_metrics.csv',index=False)

bg=base.groupby('tag').agg(n=('seed','size'),n_seeds=('seed','nunique'),timeouts=('timed_out','sum'),
    mean_inflow=('inflow_ped','mean'),mean_outflow=('outflow_ped','mean'),
    mean_speed=('mean_speed','mean'),mean_density=('mean_density','mean'),mean_flow_ratio=('flow_ratio','mean'))
bg['mean_based']=((bg.mean_density<=1.2)&bg.mean_flow_ratio.between(.9,1.2)).astype(int)
base['pass']=((base.mean_density<=1.2)&base.flow_ratio.between(.9,1.2))
bg['per_seed']=(base.groupby('tag')['pass'].sum()>=29).astype(int)
valid=df.merge(bg,left_on='combo_id',right_index=True)
valid['zero_recorded_flow']=valid.mean_inflow<1e-9
valid['timeout_any']=valid.timeouts>0
valid['baseline_rule_disagreement']=valid.base_pass!=valid.per_seed
valid['inflow_vs_requested']=valid.mean_inflow/(valid.qp*4)
valid.to_csv(OUT/'baseline_validity.csv',index=False)

vb=base.groupby('tag').mean_speed.mean()
sweep['baseline_mean_speed']=sweep.tag.map(vb)
sweep['pass']=((sweep.mean_speed/sweep.baseline_mean_speed>=.9)&sweep.flow_ratio.between(.9,1.2)&(sweep.mean_density<=1.2))
sg=sweep.groupby(['tag','qr']).agg(n=('seed','size'),n_seeds=('seed','nunique'),passing=('pass','sum'),timeouts=('timed_out','sum'))
sg['accepted']=(sg.passing>=29)&(sg.n_seeds==30)
recomputed=sg[sg.accepted].reset_index().groupby('tag').qr.max()
valid['qr_recomputed']=valid.combo_id.map(recomputed).fillna(0)
nonmono=[]
for tag,g in sg.reset_index().groupby('tag'):
    g=g.sort_values('qr'); a=g.accepted.astype(int).to_numpy()
    if (np.diff(a)>0).any():
        nonmono.append(dict(combo_id=tag,levels=';'.join(map(str,g.qr)),passing=';'.join(map(str,g.passing)),
            accepted=';'.join(map(str,a))))
pd.DataFrame(nonmono).to_csv(OUT/'nonmonotonic_quota_levels.csv',index=False)

fit_rows=[]
original_main=pd.read_csv(DATA/'main_280_reference_table.csv')
original_main['qr_star']=original_main.qr_star_per_seed
for name,d in [('D1_before_refinement',original_main),('D1_final_main',df[df.source=='main']),('D2',df),('D2_in_domain',df[df.in_domain])]:
    for plus in [False,True]:
        b,se,n=fit(d,plus); row=dict(dataset=name,model='A+' if plus else 'A',n=n,c=float(np.exp(b[0])),p=float(b[-1]),se_p=float(se[-1]))
        if plus: row.update(alpha=float(b[1]),se_alpha=float(se[1]),ci95_alpha_lo=float(b[1]-1.96*se[1]),ci95_alpha_hi=float(b[1]+1.96*se[1]))
        fit_rows.append(row)
pd.DataFrame(fit_rows).to_csv(OUT/'independent_formula_fits.csv',index=False)

# Candidate comparison uses exactly the same rows, folds and hard guards.
# A+ is a nested scientific comparison; SVR is not audited without its dependency.
comparison=[]
for model in ['A','A+']:
    pred=np.zeros(len(df))
    for city in sorted(df.city.unique()):
        tr=df[df.city!=city]; mask=df.city==city; te=df[mask]
        b,_,_=fit(tr,plus=model=='A+')
        q=np.exp(b[0])*(te.W**b[1])*(te.x**b[2]) if model=='A+' else predict(te,b)
        pred[mask]=guards(te,q)
    for scope,mask in [('all',np.ones(len(df),bool)),('in_domain',df.in_domain)]:
        comparison.append(dict(model=model,scope=scope,**metrics(df[mask],pred[mask])))
pd.DataFrame(comparison).to_csv(OUT/'A_Aplus_comparison.csv',index=False)

# Observed-prefix sensitivity is diagnostic, not a replacement of the frozen label.
prefix_quota={}
for tag,g in sg.reset_index().groupby('tag'):
    last=0.0
    for r in g.sort_values('qr').itertuples():
        if not r.accepted:
            break
        last=float(r.qr)
    prefix_quota[tag]=last
prefix_df=df.copy(); prefix_df['qr_star']=prefix_df.combo_id.map(prefix_quota).fillna(0)
changed=prefix_df.qr_star!=df.qr_star
change_table=df.loc[changed,['combo_id','in_domain','qr_star']].copy()
change_table['prefix_quota']=prefix_df.loc[changed,'qr_star']
change_table.to_csv(OUT/'observed_prefix_label_changes.csv',index=False)
prefix_loco,_=loco(prefix_df)
prefix_metrics=[]
for scope,mask in [('all',np.ones(len(df),bool)),('in_domain',df.in_domain)]:
    prefix_metrics.append(dict(scope=scope,**metrics(prefix_loco[mask],prefix_loco.loc[mask,'G1b'])))
pd.DataFrame(prefix_metrics).to_csv(OUT/'observed_prefix_sensitivity.csv',index=False)

# Isolate the two in-domain overpredictions and baseline criterion differences.
dl[dl.in_domain & (dl.G1b>dl.qr_star)].to_csv(OUT/'in_domain_overpredictions.csv',index=False)
bp_strict=valid.set_index('combo_id').per_seed
dl['G1b_perseed_baseline']=np.where(dl.combo_id.map(bp_strict)==0,0,dl.G1)
bp_compare=[]
for scope,mask in [('all',np.ones(len(dl),bool)),('in_domain',dl.in_domain)]:
    bp_compare.append(dict(scope=scope,changed=int((dl.loc[mask,'G1b']!=dl.loc[mask,'G1b_perseed_baseline']).sum()),
        **metrics(dl[mask],dl.loc[mask,'G1b_perseed_baseline'])))
pd.DataFrame(bp_compare).to_csv(OUT/'baseline_rule_sensitivity.csv',index=False)

spec=importlib.util.spec_from_file_location('operational',ROOT/'final_freeze/src/operational_quota.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
runtime=mod.OperationalQuota()
rv=[]
for r in df.itertuples():
    rv.append(runtime.quota(r.W,r.qp,r.base_pass,{'type':r.type,'sinuosity':r.sinuosity},r.vbar))
df['runtime_quota']=rv
df.to_csv(OUT/'runtime_predictions.csv',index=False)
runtime_valid=df.runtime_quota.notna()

sensitivity=[]
for name,bad in [('exclude_timeout',valid.timeout_any),('exclude_zero_recorded_flow',valid.zero_recorded_flow),
    ('exclude_either',valid.timeout_any|valid.zero_recorded_flow)]:
    ids=set(valid.loc[bad,'combo_id']); cleaned=df[~df.combo_id.isin(ids)]
    r,_=loco(cleaned)
    b,_,n=fit(cleaned)
    for scope,mask in [('all',np.ones(len(r),bool)),('in_domain',r.in_domain)]:
        sensitivity.append(dict(analysis=name,scope=scope,excluded=len(ids),c=float(np.exp(b[0])),p=float(b[1]),fit_n=n,**metrics(r[mask],r.loc[mask,'G1b'])))
pd.DataFrame(sensitivity).to_csv(OUT/'exclusion_sensitivity.csv',index=False)

summary=dict(rows=len(df),cities=int(df.city.nunique()),cell_ids=int(df.cell_id.nunique()),
    in_domain=int(df.in_domain.sum()),ood=int((~df.in_domain).sum()),
    raw_baseline_rows=len(base),raw_sweep_including_refinement_rows=len(sweep),
    baseline_duplicate_seeds=int(base.duplicated(['tag','qr','seed']).sum()),
    sweep_duplicate_seeds=int(sweep.duplicated(['tag','qr','seed']).sum()),
    baseline_groups_not_30=int(((bg.n!=30)|(bg.n_seeds!=30)).sum()),
    sweep_groups_not_30=int(((sg.n!=30)|(sg.n_seeds!=30)).sum()),
    qr_star_reconstruction_match=int((valid.qr_star==valid.qr_recomputed).sum()),
    baseline_timeout_seeds=int(base.timed_out.sum()),sweep_timeout_seeds=int(sweep.timed_out.sum()),
    zero_recorded_flow_combos=int(valid.zero_recorded_flow.sum()),
    zero_recorded_flow_baseline_pass_combos=int((valid.zero_recorded_flow&(valid.base_pass==1)).sum()),
    zero_recorded_flow_in_domain=int((valid.zero_recorded_flow&valid.in_domain).sum()),
    timeout_combos=int(valid.timeout_any.sum()),timeout_in_domain=int((valid.timeout_any&valid.in_domain).sum()),
    baseline_rule_disagreement=int(valid.baseline_rule_disagreement.sum()),
    baseline_rule_disagreement_in_domain=int((valid.baseline_rule_disagreement&valid.in_domain).sum()),
    nonmonotonic_robot_flow_combos=len(nonmono),
    strict_loco_macro_city_mae_G0=float(dl.groupby('city').apply(lambda d: np.abs(d.G0-d.qr_star).mean(),include_groups=False).mean()),
    runtime_coverage=int(runtime_valid.sum()),runtime_metrics=metrics(df[runtime_valid],df.loc[runtime_valid,'runtime_quota']),
    runtime_missing_features='turn-angle metadata unavailable in final CSV; vbar is rounded baseline mean, geometry type/sinuosity supplied',
    runtime_diff_from_loco_in_domain=int((np.array(rv,dtype=float)[dl.in_domain]!=dl.loc[dl.in_domain,'G1b']).sum()),
    baseline_zero_rate_G1=float(100*(dl.G1==0).mean()),baseline_zero_rate_G1b=float(100*(dl.G1b==0).mean()))
(OUT/'audit_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(summary,indent=2,ensure_ascii=False))
print(pd.DataFrame(rows).to_string(index=False))
print(pd.DataFrame(fit_rows).to_string(index=False))
print(pd.DataFrame(sensitivity).to_string(index=False))
