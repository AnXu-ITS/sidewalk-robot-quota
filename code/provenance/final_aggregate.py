"""Score exact candidate tests only. Frozen references/parameters/predictions are copied, never refit."""
from pathlib import Path
import json,shutil,hashlib
import numpy as np
import pandas as pd
from final_complete import O,V,F,RR,physical,sha
for p,h in json.loads((F/'frozen_hashes.json').read_text()).items():assert sha(p)==h,p
new=pd.DataFrame(json.loads((F/'new_runs.json').read_text()));assert len(new)==len(json.loads((F/'tasks.json').read_text()))
assert new.status.eq('COMPLETED_DIAGNOSTIC').all() and new.exit_code.eq(0).all()
new['configuration']=new.entrance_version
raw=pd.concat([pd.read_csv(F/'raw_index_before.csv'),new.drop(columns=['raw_hashes'],errors='ignore')],ignore_index=True).drop_duplicates('spec_hash')
raw=raw[raw.seed.between(0,29)&raw.status.eq('COMPLETED_DIAGNOSTIC')].copy()
new.to_csv(F/'new_run_registry.csv',index=False)
manifest=[]
for r in new.itertuples():
 p=RR/'runs'/r.spec_hash; s=json.loads((p/'spec.json').read_text())
 for n,h in r.raw_hashes.items():
  assert sha(p/n)==h,(r.spec_hash,n)
  manifest.append(dict(spec_hash=r.spec_hash,file=n,sha256=h))
pd.DataFrame(manifest).to_csv(F/'NEW_RAW_HASH_MANIFEST.csv',index=False)
for n in ['loco_predictions_v3.csv','reference_dataset_original_block_v3.csv','fit_parameters_v3.csv','reference_block_comparison_v3.csv','reference_qstar_changes_v3.csv']:shutil.copy2(V/n,F/n)
groups=pd.read_csv(F/'ALL_POSITIVE_GROUPS.csv'); scored=[];seedrows=[]; used=[]
for r in groups.itertuples():
 z=raw[raw.dataset.eq(r.dataset)&raw.tag.eq(r.scenario)&raw.configuration.eq(r.configuration)&raw.qr.isin([0,r.flow])].copy()
 z=z.sort_values('spec_hash').drop_duplicates(['qr','seed'])
 b=z[z.qr.eq(0)];m=z[z.qr.eq(r.flow)].copy()
 assert set(b.seed)==set(range(30)) and set(m.seed)==set(range(30)),r
 sb=json.loads((RR/'runs'/b.iloc[0].spec_hash/'spec.json').read_text())
 for row in z.itertuples():
  s=json.loads((RR/'runs'/row.spec_hash/'spec.json').read_text());assert physical(s)==physical(sb),(r,row.spec_hash)
 vbar=float(b.mean_speed.mean());assert np.isfinite(vbar) and vbar>0
 ratio=m.outflow_ped/m.inflow_ped.replace(0,np.nan); retention=m.mean_speed/vbar
 flags=m.inflow_ped.gt(0)&ratio.between(.9,1.2)&m.mean_density.le(1.2)&retention.ge(.9)
 m['baseline_mean_speed']=vbar;m['speed_retention']=retention;m['throughput_ratio_final']=ratio;m['seed_PASS']=flags
 m['baseline_spec_hash']=m.seed.map(b.set_index('seed').spec_hash);m['methods_using_this_flow']=r.methods_using_this_flow
 seedrows.append(m);used.extend(z.spec_hash)
 scored.append(dict(dataset=r.dataset,tag=r.scenario,configuration=r.configuration,quota=r.flow,passing=int(flags.sum()),n=len(m),exact_flow_status='PASS' if flags.sum()>=29 else 'FAIL',baseline_n=len(b)))
score=pd.DataFrame(scored);score.to_csv(F/'unique_exact_flow_results.csv',index=False)
pd.concat(seedrows,ignore_index=True).to_csv(F/'exact_seed_service_final.csv',index=False)
raw[raw.spec_hash.isin(set(used))].to_csv(F/'matched_raw_primary.csv',index=False)
raw.to_csv(F/'raw_final.csv',index=False)
ex=pd.read_csv(V/'exact_flow_validation_v3.csv');ex['configuration']='historical'
ex=ex.drop(columns=['passing','exact_flow_status']).merge(score,on=['dataset','tag','configuration','quota'],how='left',validate='many_to_one');assert ex.exact_flow_status.isin(['PASS','FAIL']).all()
ex.to_csv(F/'exact_flow_validation_v3.csv',index=False)
hk=pd.read_csv(V/'hk_analysis_v3.csv');old=hk.copy();hk['match_config']=hk.configuration.map({'ORIGINAL':'historical','REPAIRED':'nearest-safe-anchor-v1'})
lookup=score[score.dataset.eq('Hong Kong')].set_index(['tag','configuration','quota'])
for i,r in hk.iterrows():
 if r.quota>0:
  sc=lookup.loc[(r.tag,r.match_config,r.quota)];hk.loc[i,'exact_flow_status']=sc.exact_flow_status;hk.loc[i,'passing']=sc.passing
hk=hk.drop(columns='match_config');assert hk.loc[hk.quota.gt(0),'exact_flow_status'].isin(['PASS','FAIL']).all()
assert hk.drop(columns=['exact_flow_status','passing']).equals(old.drop(columns=['exact_flow_status']))
hk.to_csv(F/'hk_analysis_v3.csv',index=False)
changed=ex.merge(pd.read_csv(V/'exact_flow_validation_v3.csv')[['method','tag','exact_flow_status']],on=['method','tag'],suffixes=('','_before'))
changed[changed.exact_flow_status.ne(changed.exact_flow_status_before)].to_csv(F/'STATUS_UPDATES.csv',index=False)
# Adapt the established descriptive summarizer. The independent blocks and sensitivity configurations never enter primary summaries.
source=(O/'reviewer_summary_v3.py').read_text()
source=source.replace("REV=HERE/'reviewer_revision'","REV=HERE/'submission_final'")
source=source.replace("abstentions=int(a.quota.isna().sum())","abstentions=int(g.quota.isna().sum())")
source=source.replace("raw=pd.read_csv(HERE.parent/'revised_analysis/raw_rebuilt_service_per_seed.csv')","raw=pd.read_csv(REV/'raw_final.csv'); raw=raw[raw.configuration.eq('historical')].drop_duplicates(['dataset','tag','qr','seed'])")
(O/'final_summary.py').write_text(source)
print(score.groupby(['dataset','exact_flow_status']).size().to_string());print('All frozen inputs unchanged; all positives directly tested.')
