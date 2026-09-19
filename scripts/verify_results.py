"""Reproduce final predictions, direct tests and summary tables without SUMO."""
from pathlib import Path
import sys, json, hashlib
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from sidewalk_admission import predict, seed_pass


def main():
    data = ROOT/'data/submission'
    cfg = json.loads((ROOT/'configs/admission.json').read_text(encoding='utf8'))
    expected = json.loads((data/'FINAL_RESULTS.json').read_text(encoding='utf8'))
    ref = pd.read_csv(data/'reference_dataset_original_block_v3.csv').set_index('tag')
    pred = pd.read_csv(data/'loco_predictions_v3.csv')
    pars = pd.read_csv(data/'fit_parameters_v3.csv').set_index(['city','method'])
    assert len(ref) == 400 and ref.cell_id.nunique() == 140
    regenerated = []
    for row in pred.itertuples():
        pa = pars.loc[(row.city,row.method)]
        q, reason = predict(ref.loc[row.tag].to_dict(),row.method,json.loads(pa.coefficients),pa.margin,cfg)
        assert (q is None and pd.isna(row.quota)) or q == row.quota, (row.tag,row.method,q,row.quota)
        assert reason == row.reason, (row.tag,row.method,reason,row.reason)
        regenerated.append(dict(tag=row.tag,method=row.method,quota=q,reason=reason))
    raw = pd.read_csv(data/'matched_raw_primary.csv',low_memory=False)
    seed = pd.read_csv(data/'exact_seed_service_final.csv',low_memory=False)
    keys = ['dataset','tag','configuration']
    assert raw.seed.between(0,29).all() and seed.seed.between(0,29).all()
    baselines = raw[raw.qr.eq(0)]
    assert not baselines.duplicated(keys+['seed']).any()
    vb = baselines.groupby(keys).mean_speed.mean()
    assert baselines.groupby(keys).seed.nunique().eq(30).all()
    groups = []
    for key,z in seed.groupby(keys+['qr']):
        assert set(z.seed)==set(range(30)) and len(z)==30
        base = vb.loc[key[:3]]
        assert np.allclose(z.baseline_mean_speed,base,rtol=1e-12)
        flags = seed_pass(z,base,cfg['service'])
        assert flags.equals(z.seed_PASS)
        groups.append(dict(zip(keys+['quota'],key),passing=int(flags.sum()),exact_flow_status='PASS' if flags.sum()>=cfg['service']['passing_seeds'] else 'FAIL'))
    group = pd.DataFrame(groups)
    ex = pd.read_csv(data/'exact_flow_validation_v3.csv')
    merged = ex.merge(group,on=keys+['quota'],suffixes=('_stored',''),validate='many_to_one')
    assert len(merged)==len(ex) and merged.exact_flow_status.eq(merged.exact_flow_status_stored).all()
    summaries = []
    for m,z in pred.groupby('method'):
        a=z[z.quota.notna()];e=ex[ex.method.eq(m)];s=expected['loco'][m]
        got=dict(method=m,n=len(a),positive=int(a.quota.gt(0).sum()),zero=int(a.quota.eq(0).sum()),PASS=int(e.exact_flow_status.eq('PASS').sum()),FAIL=int(e.exact_flow_status.eq('FAIL').sum()),exceed=int(a.quota.gt(a.q_star).sum()),mae=float((a.quota-a.q_star).abs().mean()),util=float((a[a.q_star.gt(0)].quota/a[a.q_star.gt(0)].q_star).median()),mean_positive_quota=float(a[a.quota.gt(0)].quota.mean()))
        assert a.cell_id.nunique()==64 and got['PASS']+got['FAIL']==got['positive']
        for k,v in got.items():
            if k!='method':assert np.isclose(v,s[k],rtol=1e-12), (m,k,v,s[k])
        summaries.append(got)
    hk=pd.read_csv(data/'hk_analysis_v3.csv');hs=[]
    for r in hk[hk.quota.gt(0)].itertuples():
        conf='historical' if r.configuration=='ORIGINAL' else 'nearest-safe-anchor-v1'
        z=group[group.dataset.eq('Hong Kong')&group.tag.eq(r.tag)&group.configuration.eq(conf)&group.quota.eq(r.quota)]
        assert len(z)==1 and z.iloc[0].exact_flow_status==r.exact_flow_status
    for exp in expected['hong_kong']:
        a=hk[hk.configuration.eq(exp['configuration'])&hk.method.eq(exp['method'])]
        got=dict(configuration=exp['configuration'],method=exp['method'],n=len(a),positive=int(a.quota.gt(0).sum()),zero=int(a.quota.eq(0).sum()),PASS=int(a.exact_flow_status.eq('PASS').sum()),FAIL=int(a.exact_flow_status.eq('FAIL').sum()),exceed=int(a.quota.gt(a.q_star).sum()),util=float((a[a.q_star.gt(0)].quota/a[a.q_star.gt(0)].q_star).median()))
        for k,v in got.items():
            if k not in ['configuration','method']:assert np.isclose(v,exp[k]),(k,v,exp[k])
        hs.append(got)
    wide=pred.pivot(index='tag',columns='method',values='quota');decomp=[]
    for name,mask in [('M0>0 and M1>0',(wide.M0>0)&(wide.M1>0)),('M0=0 and M1>0',(wide.M0==0)&(wide.M1>0)),('M0=0 and M1=0',(wide.M0==0)&(wide.M1==0))]:
        z=ex[ex.tag.isin(wide.index[mask])];row={'group':name,'scenarios':int(mask.sum())}
        for m in ['M0','M1']:
            for status in ['PASS','FAIL']:row[m+'_'+status]=int((z.method.eq(m)&z.exact_flow_status.eq(status)).sum())
        decomp.append(row)
    old=pd.read_csv(data/'decomposition_v3.csv').set_index('group')
    for r in decomp:
        for k,v in r.items():
            if k!='group':assert old.loc[r['group'],k]==v
    out=ROOT/'outputs';out.mkdir(exist_ok=True)
    pd.DataFrame(regenerated).to_csv(out/'predictions_reproduced.csv',index=False)
    pd.DataFrame(summaries).to_csv(out/'development_results.csv',index=False)
    pd.DataFrame(hs).to_csv(out/'hong_kong_results.csv',index=False)
    pd.DataFrame(decomp).to_csv(out/'paired_access.csv',index=False)
    report={'status':'PASS','prediction_rows':len(pred),'unique_positive_groups':len(group),'positive_seed_records':len(seed),'independent_seeds_in_primary':0,'UNTESTED':0,'reference_refit':False,'simulation_launched':False}
    (out/'verification.json').write_text(json.dumps(report,indent=2))
    print(pd.DataFrame(summaries).to_string(index=False));print(json.dumps(report,indent=2))


if __name__=='__main__':main()
