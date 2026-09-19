"""Read-only raw-log diagnostics, uncertainty, and secondary rescoring."""
import json,re,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
import pandas as pd
from runner import ROOT,OUT,js,md,csv,evidence,score,data,fit_model,nominal,predict
def window_stock(entry,exit,start=100.,end=340.):
 # Stocks just before half-open boundaries; boundary events belong to the following window.
 n0=int(((entry<start)&((exit>=start)|exit.isna())).sum())
 n1=int(((entry<end)&((exit>=end)|exit.isna())).sum())
 ni=int(entry.between(start,end,inclusive='left').sum());no=int(exit.between(start,end,inclusive='left').sum())
 return dict(stock_start=n0,stock_end=n1,entry_proxy_window=ni,exit_window=no,conservation_residual=n0+ni-no-n1)

def inspect_raw(folder):
 cache=folder/'insertion_audit_v1.json'
 if cache.exists():
  try:json.loads(cache.read_text())
  except json.JSONDecodeError:cache.rename(folder/'insertion_audit_v1.interrupted.json')
 if cache.exists():
  result=json.loads(cache.read_text());spec=json.loads((folder/'spec.json').read_text())
  agents=pd.read_csv(folder/'agent_insertion_audit_v1.csv')
  for row in result.get('rows',[]):
   row.update(configuration=spec.get('entrance_version','historical'),seed_block='independent' if spec['seed']>=10000 else 'original',spec_hash=result['spec_hash'])
   a=agents[agents.type==row['type']];stock=window_stock(a.first_position_update,a.arrival);row.update(stock_start=stock['stock_start'],stock_end=stock['stock_end'],conservation_residual=stock['conservation_residual'],counting_revision='half-open-boundary-v2')
  (folder/'counting_audit_v2.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
  return result
 res=json.loads((folder/'result.json').read_text());spec=json.loads((folder/'spec.json').read_text())
 if res['status']!='COMPLETED_DIAGNOSTIC':return res
 initial={};first={};last={};move={};kind={};states={}
 for _,el in ET.iterparse(folder/'personfcd.xml',events=('end',)):
  if el.tag!='timestep':continue
  t=float(el.get('time'))
  for a in el.iter('person'):
   ident=a.get('id');pos=(float(a.get('x')),float(a.get('y')));initial.setdefault(ident,pos);first.setdefault(ident,t);last[ident]=t;kind[ident]=a.get('type')
   if pos!=initial[ident] and ident not in move:move[ident]=t
  el.clear()
 agents=pd.read_csv(folder/'arrival_schedule_and_observation.csv');agents['first_position_update']=agents.id.map(move);agents['entry_delay_upper_proxy']=agents.first_position_update-agents.scheduled
 try:completed=pd.read_csv(folder/'completed_personinfo.csv')
 except pd.errors.EmptyDataError:completed=pd.DataFrame()
 if len(completed):agents['arrival']=agents.id.map(completed.set_index('id').walk_arrival)
 else:agents['arrival']=np.nan
 err=(folder/'sumo.err').read_text(encoding='utf-8',errors='replace');boundary=set(re.findall(r"adding person '([^']+)'.*(?:geometry boundaries|not inside walkable area)",err));neighbors=set(re.findall(r"adding person '([^']+)'.*too close to agent",err))
 rows=[]
 for typ in ['ped','robot']:
  a=agents[agents.type==typ];cohort=a.scheduled.between(100,340,inclusive='left');unmoved=a.first_position_update.isna();persistent=set(a.loc[unmoved,'id'])
  row=dict(dataset=res['dataset'],tag=res['tag'],qr=res['qr'],seed=res['seed'],type=typ,planned_total=len(a),planned_window=int(cohort.sum()),sumo_visible_window=int(a.first_fcd.between(100,340,inclusive='left').sum()),jps_entry_position_proxy_window=int(a.first_position_update.between(100,340,inclusive='left').sum()),cohort_entered_by_end=int((cohort&~unmoved).sum()),never_position_updated=int(unmoved.sum()),persistent_boundary_rejection=len(persistent&boundary),persistent_neighbor_rejection=len(persistent&neighbors),max_entry_delay_upper=float(a.entry_delay_upper_proxy.max()) if len(a) and a.entry_delay_upper_proxy.notna().any() else None,actual_exit_window=int(a.arrival.between(100,340,inclusive='left').sum()),entry_time_exact=False,stock_start=int(((a.first_position_update<=100)&((a.arrival>100)|a.arrival.isna())).sum()),stock_end=int(((a.first_position_update<340)&((a.arrival>=340)|a.arrival.isna())).sum()))
  # A persistent rejection is not automatically a data exclusion. Geometry evidence versus interaction evidence are separate.
  row['integrity']='PERSISTENT_BOUNDARY_INSERTION_FAILURE' if row['persistent_boundary_rejection'] else ('PERSISTENT_INTERACTION_OR_UNRESOLVED' if row['never_position_updated'] else 'ALL_SCHEDULED_AGENTS_POSITION_UPDATED')
  row.update(configuration=spec.get('entrance_version','historical'),seed_block='independent' if spec['seed']>=10000 else 'original',spec_hash=res['spec_hash']);rows.append(row)
 agents.to_csv(folder/'agent_insertion_audit_v1.csv',index=False);result=dict(spec_hash=res['spec_hash'],rows=rows);cache.write_text(json.dumps(result,indent=2),encoding='utf-8');return inspect_raw(folder)
def raw():
 from concurrent.futures import ProcessPoolExecutor
 rows=[]
 folders=[folder for folder in sorted((OUT/'runs').iterdir()) if (folder/'result.json').exists()]
 with ProcessPoolExecutor(max_workers=4) as pool:
  for i,r in enumerate(pool.map(inspect_raw,folders,chunksize=4),1):
   rows.extend(r.get('rows',[]))
   if i%250==0:print('raw audited',i,'/',len(folders),flush=True)
 d=pd.DataFrame(rows);csv('revised_analysis/new_inflow_per_seed.csv',d)
 if len(d):
  csv('revised_analysis/new_inflow_by_scenario.csv',d.groupby(['dataset','tag','qr','type','configuration','seed_block']).agg(seeds=('seed','size'),planned=('planned_window','sum'),entry_proxy=('jps_entry_position_proxy_window','sum'),cohort_entered=('cohort_entered_by_end','sum'),persistent_boundary_rejections=('persistent_boundary_rejection','sum'),never_updated=('never_position_updated','sum')).reset_index())
 print('raw audited',len(d)//2,flush=True)
def uncertainty():
 p=pd.read_csv(OUT/'revised_analysis/loco_predictions_all_methods.csv');h=pd.read_csv(OUT/'revised_analysis/pooled_and_HK_frozen_predictions.csv');p=pd.concat([p,h[h.dataset=='Hong Kong']]);rng=np.random.default_rng(2026091501);records=[];differences=[]
 for dataset,z in p.groupby('dataset'):
  z=z[z.quota.notna()];cells=sorted(z.cell_id.unique());methods=sorted(z.method.unique());draws={m:[] for m in methods}
  arrays={m:{c:a[['quota','q_star_frozen']].to_numpy() for c,a in z[z.method==m].groupby('cell_id')} for m in methods}
  for _ in range(5000):
   sample=rng.choice(cells,len(cells),replace=True)
   for m in methods:
    a=np.concatenate([arrays[m][c] for c in sample]);q,r=a.T;pos=r>0;draws[m].append([np.mean(q>r),np.median(q[pos]/r[pos]) if pos.any() else np.nan,np.mean(abs(q-r))])
  for m in methods:
   for j,metric in enumerate(['reference_exceedance_rate','median_utilization','mae']):
    a=np.array(draws[m])[:,j];lo,hi=np.nanquantile(a,[.025,.975]);records.append(dict(dataset=dataset,method=m,metric=metric,low=lo,high=hi,replicates=5000,kind='fixed-prediction cell composition'))
  for j,metric in enumerate(['reference_exceedance_rate','median_utilization','mae']):
   a=np.array(draws['M0'])[:,j]-np.array(draws['M3'])[:,j];lo,hi=np.nanquantile(a,[.025,.975]);differences.append(dict(dataset=dataset,contrast='M0-M3',metric=metric,low=lo,high=hi))
 csv('revised_analysis/paired_bootstrap_intervals.csv',pd.DataFrame(records));csv('revised_analysis/paired_bootstrap_differences.csv',pd.DataFrame(differences));print('5000 paired cell bootstraps per dataset complete',flush=True)
def sensitivity():
 e=evidence();d=data();out=[];cause=[]
 for name,k,rho,speed in [('main',29,1.2,.9),('k27',27,1.2,.9),('k30',30,1.2,.9),('rho1.0',29,1.,.9),('rho1.4',29,1.4,.9),('speed.95',29,1.2,.95)]:
  se,g=score(e,k,rho,speed);q=g[(g.dataset=='Development')&(g.status=='PASS')].groupby('tag').qr.max();z=d.copy();z['qr_star']=z.combo_id.map(q).fillna(0);bad=set(se[(se.dataset=='Development')&(se.qr==0)&se.technical_invalid].tag)|set(pd.read_csv(OUT/'revised_analysis/narrow_robot_geometric_feasibility.csv').tag);z.loc[z.combo_id.isin(bad),'qr_star']=np.nan;z['fit_eligible']=z.qr_star.between(0,20,inclusive='neither');c,n,rank,cond=fit_model(z,'M0')
  out.append(dict(setting=name,zero_reference=int((z.qr_star==0).sum()),unresolved=int(z.qr_star.isna().sum()),censored=int((z.qr_star==20).sum()),fit_n=n,c=float(np.exp(c[0])),p=float(c[1]),reference_recomputed=True,fit_recomputed=True,margin_recomputed=False,guardrails_recomputed=False,scan='existing selected flows only'))
  s=se[(se.dataset=='Development')&(se.qr>0)];sp=(s.mean_speed/s.baseline_speed<speed);den=s.mean_density>rho;flow=~s.flow_ratio.between(.9,1.2)
  for mask,count in pd.DataFrame(dict(speed=sp,density=den,flow=flow)).value_counts().items():cause.append(dict(setting=name,speed_failure=mask[0],density_failure=mask[1],flow_failure=mask[2],seeds=count))
 csv('sensitivity/threshold_rescoring.csv',pd.DataFrame(out));csv('sensitivity/service_constraint_joint_triggers.csv',pd.DataFrame(cause))
 b=e[(e.dataset=='Development')&(e.qr==0)].copy();b['pass_flag']=(b.mean_density<=1.2)&b.flow_ratio.between(.9,1.2)&b.timed_out.eq(0);bg=b.groupby('tag').pass_flag.sum();z=d.copy();z.base_pass=z.combo_id.map(bg).ge(29).astype(int);c,_,_,_=fit_model(d,'M0');cal=json.loads((ROOT/'final_freeze_29of30_corrected/calibration/calibration.json').read_text());base=[]
 for m,de in [('M0',cal['delta']),('M1',0)]:
  old=np.array([x[0] for x in predict(d,m,c,de)]);new=np.array([x[0] for x in predict(z,m,c,de)]);base.append(dict(method=m,label_changes=int((d.base_pass!=z.base_pass).sum()),recommendation_changes=int((old[np.isfinite(old)]!=new[np.isfinite(old)]).sum())))
 csv('sensitivity/baseline_29of30.csv',pd.DataFrame(base));md('sensitivity/REPORT.md','# Secondary archive rescoring\n\n'+pd.DataFrame(out).to_string(index=False)+'\n\nThese are reference/conditional-fit diagnostics, not full recalibration: margins, demand gates, caps remain fixed. Technical timeout baselines are unresolved, so corrected zero counts differ by five from the old manuscript. No new physical-size or direction-share simulation is claimed.\n');print(pd.DataFrame(out).to_string(index=False),flush=True)
def domain_margin():
 d=pd.read_csv(OUT/'revised_analysis/reference_status.csv');rows=[];pars=[]
 for city in sorted(d.city.unique()):
  tr=d[(d.city!=city)&d.qr_star.notna()];te=d[d.city==city]
  for method in ['M0','M2','M3']:
   c,_,_,_=fit_model(tr,method);z=tr[tr.operational_member];nom=nominal(z,method,c)
   if method=='M0':nom=np.exp(c[0])*z.W*z.x**c[1]
   margin=float(np.quantile(np.maximum(nom-z.qr_star,0),.8));pars.append(dict(city=city,method=method,margin=margin,calibration_n=len(z)))
   for r,(q,reason) in zip(te.itertuples(),predict(te,method,c,margin)):rows.append(dict(city=city,method=method,tag=r.combo_id,quota=q,reference=r.qr_star,reason=reason))
 pred=pd.DataFrame(rows);csv('sensitivity/domain_margin_predictions.csv',pred);csv('sensitivity/domain_margin_parameters.csv',pd.DataFrame(pars));metrics=[]
 for method,z in pred.groupby('method'):
  z=z[z.quota.notna()];pos=z.reference>0;metrics.append(dict(method=method,n=len(z),positive_reference_n=int(pos.sum()),exceedance=int((z.quota>z.reference).sum()),zero=int((z.quota==0).sum()),mae=float(abs(z.quota-z.reference).mean()),utilization=float(np.median(z.loc[pos,'quota']/z.loc[pos,'reference']))))
 csv('sensitivity/domain_margin_metrics.csv',pd.DataFrame(metrics));print(pd.DataFrame(metrics).to_string(index=False))
if __name__=='__main__':
 import sys
 for step in sys.argv[1:]:globals()[step]()
