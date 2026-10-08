"""Reproduce CICTP2027 results from real archived seed evidence; no simulation."""
from pathlib import Path
import argparse, hashlib, json, math, sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'src'))
from sidewalk_admission import predict,seed_pass
KEY=['dataset','tag','configuration','qr','seed_block']

def read(path):return pd.read_csv(ROOT/path,low_memory=False)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,default=ROOT/'outputs/reproduced')
    args=ap.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    cfg=json.loads((ROOT/'configs/admission.json').read_text(encoding='utf-8'))
    expected=json.loads((ROOT/'data/admission_results/FINAL_RESULTS.json').read_text(encoding='utf-8'))
    ref=read('data/reference_flows/reference_dataset_original_block_v3.csv')
    frozen=read('data/admission_results/loco_predictions_v3.csv')
    pars=read('data/admission_results/fit_parameters_v3.csv').set_index(['city','method'])
    assert len(ref)==400 and ref.tag.is_unique and ref.cell_id.nunique()==140
    a=read('data/seed_evidence/original_seed_metrics.csv');b=read('data/seed_evidence/previous_independent_seed_metrics.csv')
    b['configuration']=b.entrance_version.fillna('historical')
    n=read('data/seed_evidence/extension_seed_metrics.csv')
    assert len(n)==1920 and n.status.eq('COMPLETED_DIAGNOSTIC').all()
    raw=pd.concat([a,b,n],ignore_index=True)
    raw['seed_block']=np.where(raw.seed.between(0,29),'0-29',np.where(raw.seed.between(10000,10029),'10000-10029','other'))
    assert raw.seed_block.ne('other').all()
    assert not raw.duplicated(KEY[:-1]+['seed']).any()
    bases={k:z for k,z in raw[raw.qr.eq(0)].groupby(['dataset','tag','configuration','seed_block'])}
    scores={};scored_seeds={}
    for key,z in raw.groupby(KEY):
        required=set(range(30)) if key[-1]=='0-29' else set(range(10000,10030))
        base=bases.get((key[0],key[1],key[2],key[4]),pd.DataFrame())
        if len(z)!=30 or set(z.seed)!=required or len(base)!=30 or set(base.seed)!=required:
            scores[key]=dict(status='MISSING_EVIDENCE',passing=np.nan);continue
        if not z.status.eq('COMPLETED_DIAGNOSTIC').all() or not base.status.eq('COMPLETED_DIAGNOSTIC').all():
            scores[key]=dict(status='TECHNICAL_FAILURE',passing=np.nan);continue
        v=float(base.mean_speed.mean())
        if v<=0:scores[key]=dict(status='INVALID_BASELINE',passing=np.nan);continue
        flags=seed_pass(z,v,cfg['service'])
        passing=int(flags.sum());scores[key]=dict(status='PASS' if passing>=29 else 'FAIL',passing=passing,baseline_mean_speed=v)
        scored_seeds[key]=z.assign(baseline_mean_speed=v,speed_retention=z.mean_speed/v,
                                   throughput_ratio=z.outflow_ped/z.inflow_ped.replace(0,np.nan),seed_PASS=flags)
    def hit(tag,q,block='0-29',dataset='Development',configuration='historical'):
        key=(dataset,tag,configuration,float(q),block)
        assert key in scores and scores[key]['status'] in ['PASS','FAIL'],('Incomplete direct evidence',key)
        return scores[key]
    # Check archived configuration identity rather than merely reusing a nearby flow.
    specs=json.loads((ROOT/'configs/run_specs.json').read_text(encoding='utf-8'));identities={}
    for r in specs:
        s=r['spec'];k=(s['dataset'],s['tag'],r['configuration'])
        science={x:v for x,v in s.items() if x not in ['qr','seed','simulator_source_hash','config_hash','instrumentation_version']}
        h=hashlib.sha256(json.dumps(science,sort_keys=True).encode()).hexdigest()
        if k in identities:assert identities[k]==h
        identities[k]=h
    def matched(tag,q,block='0-29',dataset='Development',configuration='historical'):
        assert (dataset,tag,configuration) in identities
        return hit(tag,q,block,dataset,configuration)
    for r in frozen.itertuples():
        pa=pars.loc[(r.city,r.method)]
        q,reason=predict(ref.set_index('tag').loc[r.tag].to_dict(),r.method,json.loads(pa.coefficients),pa.margin,cfg)
        assert (q is None and pd.isna(r.quota)) or q==r.quota
        assert reason==r.reason
    mainrows=[]
    for method,z in frozen.groupby('method'):
        eligible=z[z.quota.notna()];pos=eligible[eligible.quota.gt(0)]
        tests=[matched(r.tag,r.quota) for r in pos.itertuples()]
        stats=dict(method=method,n=len(eligible),positive=len(pos),zero=int(eligible.quota.eq(0).sum()),
                   PASS=sum(r['status']=='PASS' for r in tests),FAIL=sum(r['status']=='FAIL' for r in tests),
                   util=float((eligible[eligible.q_star.gt(0)].quota/eligible[eligible.q_star.gt(0)].q_star).median()),
                   mae=float((eligible.quota-eligible.q_star).abs().mean()))
        for field in ['n','positive','zero','PASS','FAIL','util','mae']:assert np.isclose(stats[field],expected['loco'][method][field],rtol=1e-10)
        assert stats['n']==164;mainrows.append(stats)
    pd.DataFrame(mainrows).to_csv(out/'main_comparison.csv',index=False)
    # Refit only the six training cities for each prespecified quantile.
    candidates=[];parameters=[]
    for city in sorted(ref.city.unique()):
        train=ref[ref.city.ne(city)&ref.q_star.notna()];test=ref[ref.city.eq(city)]
        assert len(set(train.city))==6 and city not in set(train.city)
        assert not set(train.cell_id)&set(test.cell_id)
        fit=train[train.fit_eligible&train.q_star.between(0,20,inclusive='neither')&train.qp.gt(0)&train.W.gt(0)]
        coef=np.linalg.lstsq(np.c_[np.ones(len(fit)),np.log(fit.x)],np.log(fit.q_star/fit.W),rcond=None)[0]
        assert np.allclose(coef,json.loads(pars.loc[(city,'M0')].coefficients),rtol=1e-10)
        residual=np.maximum(np.exp(coef[0])*train.W*train.x**coef[1]-train.q_star,0)
        for tau in [0,.5,.65,.8,.9]:
            delta=0. if tau==0 else float(np.quantile(residual,tau,method='linear'))
            parameters.append(dict(city=city,tau=tau,margin=delta,fit_n=len(fit),calibration_n=len(train),training_cities='|'.join(sorted(train.city.unique()))))
            for r in test.itertuples():
                q,reason=predict(r._asdict(),'M0',coef,delta,cfg)
                evidence=matched(r.tag,q) if q is not None and q>0 else None
                candidates.append(dict(tau=tau,tag=r.tag,city=city,quota=q,reason=reason,q_star=r.q_star,
                                       status=evidence['status'] if evidence else 'ZERO' if q==0 else 'ABSTAIN',
                                       passing=evidence['passing'] if evidence else np.nan))
    c=pd.DataFrame(candidates);stored=read('experiments/E2_margin_sweep/E2_MARGIN_SWEEP_SCENARIOS.csv')
    assert len(c[c.quota.gt(0)][['tag','quota']].drop_duplicates())==463
    j=c.merge(stored,on=['tau','tag'],suffixes=('','_stored'),validate='one_to_one')
    assert len(j)==2000 and np.allclose(j.quota,j.quota_stored,equal_nan=True)
    assert j[j.quota.gt(0)].status.eq(j[j.quota.gt(0)].service_status).all()
    c.to_csv(out/'margin_candidates.csv',index=False);pd.DataFrame(parameters).to_csv(out/'margin_parameters.csv',index=False)
    rows=[];cities=[];zero=c[c.tau.eq(0)].set_index('tag')
    def summary(tau,z,city):
        q=z[z.quota.notna()];p=q[q.quota.gt(0)];rr=q[q.q_star.gt(0)]
        withheld=q[q.quota.eq(0)&q.tag.map(zero.quota).gt(0)]
        return dict(tau=tau,city=city,evaluable=len(q),positive_recommendations=len(p),zero_recommendations=int(q.quota.eq(0).sum()),
                    PASS=int(p.status.eq('PASS').sum()),FAIL=int(p.status.eq('FAIL').sum()),
                    median_reference_utilization=float((rr.quota/rr.q_star).median()),mae_to_reference=float((q.quota-q.q_star).abs().mean()),
                    reference_exceedance_count=int(q.quota.gt(q.q_star).sum()),mean_positive_candidate_flow=float(p.quota.mean()),
                    withheld_relative_to_tau0=len(withheld),withheld_tau0_flow_PASS=int(zero.loc[withheld.tag].status.eq('PASS').sum()))
    for tau,z in c.groupby('tau'):
        rows.append(summary(tau,z,'ALL'))
        cities.extend(summary(tau,part,city) for city,part in z.groupby('city'))
    margins=pd.DataFrame(rows);old=read('experiments/E2_margin_sweep/E2_MARGIN_SWEEP_RESULTS.csv')
    for field in margins.columns:
        if field!='city':assert np.allclose(margins[field],old[field],rtol=1e-10)
    assert margins.positive_recommendations.tolist()==[136,129,122,98,58]
    assert margins.FAIL.tolist()==[18,10,5,0,0]
    margins.to_csv(out/'margin_sweep.csv',index=False);pd.DataFrame(cities).to_csv(out/'margin_by_city.csv',index=False)
    rep=read('experiments/E3_replication/E3_INDEPENDENT_SEED_RESULTS.csv');repnew=[]
    for r in rep.itertuples():
        old=matched(r.tag,r.candidate_flow);new=matched(r.tag,r.candidate_flow,'10000-10029')
        assert old['passing']==r.original_pass_count and new['passing']==r.independent_pass_count
        assert old['status']==r.original_status and new['status']==r.independent_status
        repnew.append(dict(tag=r.tag,method=r.method,stratum=r.selection_stratum,original=old['passing'],independent=new['passing'],
                           original_status=old['status'],independent_status=new['status'],unchanged=old['status']==new['status'],
                           independent_baseline_mean_speed=new['baseline_mean_speed']))
    repnew=pd.DataFrame(repnew);assert len(repnew)==28
    rs=repnew.groupby('method').agg(decisions=('tag','size'),unchanged=('unchanged','sum')).reset_index()
    assert rs.set_index('method').loc['M0','unchanged']==13 and rs.set_index('method').loc['M1','unchanged']==7
    freeze=ROOT/'experiments/E3_replication/E3_REPLICATION_SAMPLE_FREEZE.csv'
    fh=json.loads((freeze.parent/'E3_SAMPLE_FREEZE_HASH.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(freeze.read_bytes()).hexdigest()==fh['sha256']
    assert len(pd.read_csv(freeze))==15
    repnew.to_csv(out/'replication_conditions.csv',index=False);rs.to_csv(out/'replication_summary.csv',index=False)
    failure=[]
    for r in frozen[frozen.method.eq('M1')&frozen.quota.gt(0)].itertuples():
        h=matched(r.tag,r.quota)
        if h['status']!='FAIL':continue
        s=scored_seeds[('Development',r.tag,'historical',r.quota,'0-29')]
        counts=dict(speed=int((~s.speed_retention.ge(.9)).sum()),density=int((~s.mean_density.le(1.2)).sum()),
                    flow=int((~(s.inflow_ped.gt(0)&s.throughput_ratio.between(.9,1.2))).sum()))
        failure.append(dict(tag=r.tag,passing=h['passing'],mode=' + '.join(k for k,v in counts.items() if v),
                            dominant=' + '.join(k for k,v in counts.items() if v==max(counts.values())),**counts))
    fd=pd.DataFrame(failure);assert len(fd)==18 and fd.speed.gt(0).all() and fd.dominant.eq('speed').sum()==17
    fd.to_csv(out/'failure_decomposition.csv',index=False)
    hk=read('data/hong_kong/hk_analysis_v3.csv');hkrows=[]
    assert hk[hk.configuration.eq('ORIGINAL')].tag.nunique()==13 and hk[hk.configuration.eq('REPAIRED')].tag.nunique()==5
    for r in hk[hk.quota.gt(0)].itertuples():
        h=matched(r.tag,r.quota,dataset='Hong Kong',configuration='historical' if r.configuration=='ORIGINAL' else 'nearest-safe-anchor-v1')
        assert h['status']==r.exact_flow_status
    for k,z in hk.groupby(['configuration','method']):
        hkrows.append(dict(configuration=k[0],method=k[1],scenarios=len(z),positive=int(z.quota.gt(0).sum()),
                           zero=int(z.quota.eq(0).sum()),PASS=int(z.exact_flow_status.eq('PASS').sum()),FAIL=int(z.exact_flow_status.eq('FAIL').sum())))
    hks=pd.DataFrame(hkrows);hks.to_csv(out/'hong_kong_summary.csv',index=False)
    # Baseline and mixed rows for every replicated condition are publicly present.
    replication_keys=set()
    for r in rep.itertuples():
        for block in ['0-29','10000-10029']:
            replication_keys.add(('Development',r.tag,'historical',float(r.candidate_flow),block));replication_keys.add(('Development',r.tag,'historical',0.,block))
    baseline_evidence=pd.concat([scored_seeds[k] for k in sorted(replication_keys)],ignore_index=True)
    baseline_evidence.to_csv(out/'replication_baselines_and_mixed_seeds.csv',index=False)
    technical=ref[ref.q_star_status.eq('TECHNICAL_INVALID')]
    technical.to_csv(out/'technical_exclusions.csv',index=False)
    demand=read('experiments/E1_demand_audit/E1_DEMAND_REALIZATION.csv')
    assert not demand.physical_insertion_time_available.any()
    demandrows=[]
    for key,z in demand.groupby(['dataset','scope','method','candidate_status']):
        demandrows.append(dict(dataset=key[0],scope=key[1],method=key[2],candidate_status=key[3],seed_rows=len(z),
                               groups=len(z[['tag','configuration','qr']].drop_duplicates()),
                               first_observed_ratio_min=float((z.ped_cohort_observed_by_end/z.ped_planned_window).min()),
                               window_completed_ratio_min=float((z.outflow_ped/z.ped_planned_window).min()),
                               passing_low_completion_seeds=int((z.seed_service_PASS&(z.outflow_ped/z.ped_planned_window).lt(.9)).sum())))
    ds=pd.DataFrame(demandrows);ds.to_csv(out/'demand_summary.csv',index=False)
    main_m0=ds[ds.dataset.eq('Development')&ds.method.eq('M0')]
    assert main_m0.iloc[0].seed_rows==2940 and np.isclose(main_m0.iloc[0].window_completed_ratio_min,11/12)
    grid=pd.read_csv(ROOT/'data/scenarios/development_guardrail_grid.tsv',sep='\t');assert len(grid)==48
    gate=[]
    for w,z in grid.groupby('W',sort=True):
        pos=z[z.qr_star.gt(0)].qp;zero=z[z.qr_star.eq(0)].qp
        cap=float(z.qp.min()) if not len(pos) else float(grid.qp.max()+30) if not len(zero) else float((pos.max()+zero.min())/2)
        gate.append(dict(W=w,C=cap,Q_low=float(z[z.qp.eq(10)].qr_star.iloc[0])))
    gr=pd.DataFrame(gate);gr['C']=np.maximum.accumulate(gr.C)
    assert np.allclose(gr.C,cfg['guardrails']['C_W']['C']) and np.allclose(gr.Q_low,cfg['guardrails']['Q_low']['Q'])
    assert np.isclose((grid[grid.base_pass.astype(bool)].qp/grid[grid.base_pass.astype(bool)].W).max(),cfg['guardrails']['x_crit'])
    gr.to_csv(out/'guardrail_reconstruction.csv',index=False)
    reports=dict(status='PASS',reference_scenarios=400,evaluated_scenarios=164,city_folds=7,heldout_leakage=False,
                 sweep_predictions=2000,positive_sweep_recommendations=543,unique_sweep_groups=463,
                 new_seed_records=1920,replicated_conditions=28,replication_m0_unchanged=13,replication_m1_unchanged=7,
                 failed_m1_groups=18,speed_involved_in_all_failed_groups=True,
                 hong_kong_original=13,hong_kong_repaired=5,demand_audit_seed_rows=len(demand),guardrail_knots_reconstructed=len(gr),new_simulations_executed=0)
    (out/'integrity.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
    print(json.dumps(reports,indent=2))

if __name__=='__main__':main()
