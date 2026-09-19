from pathlib import Path
import json
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
REV=HERE/'submission_final'
raw=pd.read_csv(REV/'raw_final.csv'); raw=raw[raw.configuration.eq('historical')].drop_duplicates(['dataset','tag','qr','seed'])
raw=raw[(raw.status=='COMPLETED_DIAGNOSTIC') & raw.seed.between(0,29)].copy()
raw['zero_denominator']=raw.inflow_ped.fillna(0).le(0)
raw['ratio_defined']=~raw.zero_denominator
# Keep diagnostics tied to log fields; avoid coding undefined ratio as pass.
raw['planned_minus_observed']=raw.ped_planned_window.fillna(0)-raw.ped_cohort_observed_by_end.fillna(0)
raw['window_unobserved']=raw.ped_cohort_observed_by_end.fillna(0).lt(raw.ped_planned_window.fillna(0))
raw['throughput_undefined_reason']=np.select([
    ~raw.zero_denominator,
    raw.zero_denominator & raw.window_unobserved,
    raw.zero_denominator & raw.ped_planned_window.fillna(0).gt(0) & ~raw.window_unobserved,
    raw.zero_denominator & raw.ped_planned_window.fillna(0).le(0),
],['defined','window_or_entry_shortfall','completed_departure_counter_zero','no_planned_pedestrian_demand'],default='other')
# method outputs and direct-flow statuses
pred=pd.read_csv(REV/'loco_predictions_v3.csv')
ex=pd.read_csv(REV/'exact_flow_validation_v3.csv')
hk=pd.read_csv(REV/'hk_analysis_v3.csv')
rows=[]
for m,g in pred.groupby('method'):
    a=g[g.quota.notna()].copy(); pos=a.quota.gt(0)
    ee=ex[ex.method.eq(m)]
    exact_counts=ee.exact_flow_status.value_counts().to_dict()
    err=(a.quota-a.q_star)
    ratios=a.loc[a.q_star.gt(0)].quota/a.loc[a.q_star.gt(0)].q_star
    rows.append(dict(method=m,evaluable=int(len(a)),abstentions=int(g.quota.isna().sum()),positive=int(pos.sum()),zero=int((a.quota==0).sum()),
                     pass_n=int(exact_counts.get('PASS',0)),fail_n=int(exact_counts.get('FAIL',0)),untested_n=int(exact_counts.get('UNTESTED',0)),incomplete_n=int(exact_counts.get('INCOMPLETE',0)),
                     exceed=int((err>0).sum()),mae=float(err.abs().mean()),median_utilization=float(ratios.median()),utilization_n=int(len(ratios)),mean_positive_quota=float(a.loc[pos,'quota'].mean()),median_positive_quota=float(a.loc[pos,'quota'].median())))
method=pd.DataFrame(rows); method.to_csv(REV/'method_results_v3.csv',index=False)
# paired scenario decomposition
wide=pred.pivot_table(index=['tag','cell_id','city'],columns='method',values='quota',aggfunc='first')
# direct status lookup by tag/method; only positive rows exist
st=ex.pivot_table(index='tag',columns='method',values='exact_flow_status',aggfunc='first')
groups=[]
for name,mask in [('M0>0 and M1>0',(wide.M0>0)&(wide.M1>0)),('M0=0 and M1>0',(wide.M0==0)&(wide.M1>0)),('M0=0 and M1=0',(wide.M0==0)&(wide.M1==0))]:
    tags=set(wide.index[mask].get_level_values('tag'))
    rec={'group':name,'scenarios':len(tags)}
    for m in ['M0','M1']:
        ee=ex[(ex.method==m)&ex.tag.isin(tags)]
        rec[f'{m}_positive']=int(len(ee)); rec[f'{m}_PASS']=int((ee.exact_flow_status=='PASS').sum()); rec[f'{m}_FAIL']=int((ee.exact_flow_status=='FAIL').sum()); rec[f'{m}_UNTESTED']=int((ee.exact_flow_status=='UNTESTED').sum())
        rec[f'{m}_mean_quota']=float(wide.loc[mask,m].mean()) if (wide.loc[mask,m]>0).any() else 0.0
    groups.append(rec)
dec=pd.DataFrame(groups); dec.to_csv(REV/'decomposition_v3.csv',index=False)
# continuous service among directly tested development positives; speed retention uses baseline mean per scenario.
baseline=raw[raw.qr.eq(0)].groupby(['dataset','tag']).mean(numeric_only=True).mean_speed.rename('vbar')
cont=[]
for r in ex.itertuples():
    if r.exact_flow_status not in ('PASS','FAIL'): continue
    s=raw[(raw.dataset==r.dataset)&(raw.tag==r.tag)&raw.qr.eq(r.quota)]
    vb=baseline.get((r.dataset,r.tag),np.nan)
    if len(s)!=30 or not np.isfinite(vb) or vb<=0: continue
    ret=s.mean_speed/vb
    cont.append(dict(method=r.method,tag=r.tag,flow=r.quota,status=r.exact_flow_status,median_speed_retention=float(ret.median()),mean_speed_retention=float(ret.mean()),min_speed_retention=float(ret.min()),median_density=float(s.mean_density.median()),median_flow_ratio=float((s.outflow_ped/s.inflow_ped.replace(0,np.nan)).median())))
cont=pd.DataFrame(cont); cont.to_csv(REV/'service_continuous_v3.csv',index=False)
cont_summary=[]
for m,g in cont.groupby('method'):
    cont_summary.append(dict(method=m,groups=len(g),median_of_group_medians=float(g.median_speed_retention.median()),median_of_group_means=float(g.mean_speed_retention.median()),median_of_group_minima=float(g.min_speed_retention.median()),worst_group_minimum=float(g.min_speed_retention.min())))
pd.DataFrame(cont_summary).to_csv(REV/'service_continuous_summary_v3.csv',index=False)
# diagnostics counts and cause split
den=raw.groupby(['dataset',raw.qr.eq(0).map({True:'baseline',False:'mixed'})]).agg(rows=('seed','size'),denominator_zero=('zero_denominator','sum'),planned_pedestrians=('ped_planned_window','sum'),observed_pedestrians=('ped_cohort_observed_by_end','sum'),never_observed=('ped_never_observed','sum')).reset_index().rename(columns={'qr':'flow_group'})
den.to_csv(REV/'denominator_zero_diagnostics_v3.csv',index=False)
cause=raw[raw.zero_denominator].groupby(['dataset','throughput_undefined_reason']).agg(rows=('seed','size'),tags=('tag','nunique'),planned=('ped_planned_window','sum'),observed=('ped_cohort_observed_by_end','sum'),mean_speed=('mean_speed','mean'),mean_density=('mean_density','mean')).reset_index();cause.to_csv(REV/'denominator_zero_causes_v3.csv',index=False)
# affected reference tags from original block correction
cmp=pd.read_csv(REV/'reference_block_comparison_v3.csv'); changes=cmp[cmp.q_star_changed].copy(); changes.to_csv(REV/'reference_qstar_changes_v3.csv',index=False)
summary={'reference_counts':pd.read_csv(REV/'reference_dataset_original_block_v3.csv').q_star_status.value_counts().to_dict(),'method_results':rows,'decomposition':groups,'denominator':den.to_dict('records'),'denominator_causes':cause.to_dict('records'),'q_star_changes':changes[['tag','q_star_frozen','q_star_v3']].to_dict('records'),'exact_flow_counts':ex.exact_flow_status.value_counts().to_dict(),'hk_counts':{'|'.join(map(str,k)):int(v) for k,v in hk.groupby(['configuration','method','exact_flow_status']).size().to_dict().items()}}
(REV/'reviewer_summary_v3.json').write_text(json.dumps(summary,indent=2,default=str),encoding='utf-8')
print(json.dumps(summary,indent=2,default=str))
