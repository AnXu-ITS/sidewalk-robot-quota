"""Versioned sidewalk review. Never writes historical inputs."""
from pathlib import Path
import sys, json, hashlib, shutil, os, time, subprocess, math, importlib.util, copy
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]; OUT=Path(__file__).resolve().parent
FREEZE=ROOT/'final_freeze_29of30_corrected'
for n in ['original_reproduction','revised_analysis','sensitivity','scripts','runs','paper','reports']:(OUT/n).mkdir(exist_ok=True)
sys.path.insert(0,str(FREEZE/'src'))
from operational_quota import OperationalQuota
CFG=json.loads((FREEZE/'final_quota_method_config.json').read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def js(p,x):
 p=OUT/p;p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(x,indent=2,default=str),encoding='utf-8');tmp.replace(p)
def md(p,x):(OUT/p).write_text(x,encoding='utf-8')
def csv(p,d):d.to_csv(OUT/p,index=False)
def read(p):return pd.read_csv(ROOT/p)
def data():
 d=read('final_freeze_29of30_corrected/data/corrected_reference_dataset.csv')
 geometry=json.loads((ROOT/'pipeline/cells/selected_cells.json').read_text(encoding='utf-8'))['cells'];lookup={r['cell_id']:r for r in geometry}
 for field in ['max_turn_deg','cum_turn_deg']:d[field]=d.cell_id.map({k:v[field] for k,v in lookup.items()})
 return d
def evidence():
 frames=[]
 for f in ['multicity_baseline','decoupled_baseline','multicity_sweep','decoupled_sweep','refinement_sweep']:
  d=read('data/final/'+f+'.csv');d['source_file']='data/final/'+f+'.csv';d['dataset']='Development';frames.append(d)
 h=read('external_validation/hong_kong/runs/formal/seed_results.csv').rename(columns={'cell_id':'tag'});h['dataset']='Hong Kong';h['source_file']='external_validation/hong_kong/runs/formal/seed_results.csv';frames.append(h)
 return pd.concat(frames,ignore_index=True)
def score(e,k=29,rho=1.2,speed=.9):
 e=e.copy();base=e[e.qr==0].groupby(['dataset','tag']).mean_speed.mean()
 e['baseline_speed']=[base.get((r.dataset,r.tag),np.nan) for r in e.itertuples()]
 e['technical_invalid']=e.timed_out.fillna(0).ne(0)|e[['mean_speed','mean_density','flow_ratio']].isna().any(axis=1)
 e['pass_flag']=(~e.technical_invalid)&(e.mean_speed/e.baseline_speed>=speed)&(e.mean_density<=rho)&e.flow_ratio.between(.9,1.2)
 g=e[e.qr>0].groupby(['dataset','tag','qr']).agg(n=('seed','size'),unique_seeds=('seed','nunique'),passing=('pass_flag','sum'),invalid=('technical_invalid','sum')).reset_index()
 g['status']=np.where((g.n!=30)|(g.unique_seeds!=30)|(g.invalid>0),'INCOMPLETE_OR_INVALID',np.where(g.passing>=k,'PASS','FAIL'))
 return e,g
def audit():
 paths=[]
 for base in ['data/final','final_freeze_29of30_corrected','pipeline/cells','pipeline/sim/scripts','external_validation/hong_kong/sites','external_validation/hong_kong/runs/formal','CICPT2027']:
  for p in (ROOT/base).rglob('*'):
   if p.is_file() and not any(x in p.parts for x in ['.git','.build','__pycache__']) and p.suffix.lower() in ['.csv','.json','.yaml','.py','.tex','.bib','.cls','.bst','.pdf','.md']:
    paths.append(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,mtime=p.stat().st_mtime,sha256=sha(p)))
 csv('ASSET_MANIFEST.csv',pd.DataFrame(paths))
 for n in ['ascexmpl-new.tex','ascexmpl-new.pdf','README.md']:shutil.copy2(ROOT/'CICPT2027'/n,OUT/'original_reproduction'/n)
 e,g=score(evidence());csv('original_reproduction/flow_qualification.csv',g)
 d=data();bg=e[(e.dataset=='Development')&(e.qr==0)].groupby('tag').agg(vbar=('mean_speed','mean'),density=('mean_density','mean'),flow=('flow_ratio','mean'))
 q=g[(g.dataset=='Development')&(g.status=='PASS')].groupby('tag').qr.max()
 checks=[]
 for label,old,new in [('scenarios',400,len(d)),('cells',140,d.cell_id.nunique()),('zero',194,(d.qr_star==0).sum()),('ceiling',17,(d.qr_star==20).sum()),('fit',189,d.fit_eligible.sum()),('reference_mismatches',0,(d.qr_star!=d.combo_id.map(q).fillna(0)).sum())]:checks.append(dict(item=label,manuscript=old,reproduced=new,difference=new-old))
 cal=json.loads((FREEZE/'calibration/calibration.json').read_text());f=d[d.fit_eligible];a,p=np.linalg.lstsq(np.c_[np.ones(len(f)),np.log(f.x)],np.log(f.qr_star/f.W),rcond=None)[0];c=np.exp(a);de=np.quantile(np.maximum(c*d.W*d.x**p-d.qr_star,0),.8)
 for label,new in [('c',c),('p',p),('delta',de)]:checks.append(dict(item=label,manuscript=cal[label],reproduced=new,difference=new-cal[label]))
 matches=[]
 for dataset,fn,idcol in [('Development','seven_city_paired.csv','combo_id'),('Hong Kong','hong_kong_paired.csv','cell_id')]:
  z=pd.read_csv(FREEZE/'experiments'/fn)
  for method,col in [('M0','conservative'),('M1','zero_margin')]:
   for _,r in z.iterrows():
    hit=g[(g.dataset==dataset)&(g.tag==r[idcol])&(g.qr==r[col])]
    matches.append(dict(dataset=dataset,scope='Frozen pooled',method=method,tag=r[idcol],quota=r[col],q_star_frozen=r.qr_star,status='ZERO' if r[col]==0 else (hit.iloc[0].status if len(hit) else 'UNTESTED')))
 m=pd.DataFrame(matches);csv('original_reproduction/exact_flow_matches.csv',m);csv('original_reproduction/exact_flow_summary.csv',m.groupby(['dataset','method','status']).size().rename('n').reset_index());csv('REPRODUCTION_DIFF.csv',pd.DataFrame(checks))
 e['planned_pedestrian_window']=np.nan;e['actual_robot_entries']=np.nan;e['planned_robot_window']=np.nan
 e['legacy_recorded_pedestrian_entries']=e.inflow_ped;e['legacy_recorded_pedestrian_exits']=e.outflow_ped
 e['pedestrian_recorded_rate']=e.inflow_ped/4;e['nominal_count_ratio_diagnostic']=e.inflow_ped/(4*e.qp)
 e['inflow_audit_status']=np.where(e.technical_invalid,'TECHNICALLY_INVALID','UNRESOLVED_NO_RAW_ARRIVAL_LOG')
 e['reason']='Completed-personinfo counts only; archived XML removed; actual insertion and robot counts not retained.'
 csv('inflow_integrity_per_seed.csv',e)
 by=e.groupby(['dataset','tag','qr']).agg(seeds=('seed','size'),technical_invalid=('technical_invalid','sum'),mean_recorded_ped_entries=('inflow_ped','mean'),min_nominal_ratio=('nominal_count_ratio_diagnostic','min'),max_nominal_ratio=('nominal_count_ratio_diagnostic','max')).reset_index();by['status']='UNRESOLVED_NO_RAW_ARRIVAL_LOG';csv('inflow_integrity_by_scenario.csv',by);csv('invalid_or_unresolved_runs.csv',e[['dataset','tag','qr','seed','inflow_audit_status','reason','source_file']])
 hr=read('external_validation/hong_kong/runs/formal/hk_reference_qr_star.csv');csv('revised_analysis/HK_exclusions.csv',hr[hr.integrity!='ok'])
 md('SOURCE_OF_TRUTH.md','# Source of truth\n\nLatest editable manuscript: CICPT2027/ascexmpl-new.tex, 2026-09-15, newer than the reviewed draft and 61 seconds newer than the local PDF. Preserved before editing. Exact ascexmpl-new(3).pdf was not found by project file inventory; do not claim a binary match. Current manuscript uses results_corrected and conference_20260915 figures.\n\nAuthoritative numerical reproduction: final_freeze_29of30_corrected; raw seed data: data/final plus HK runs/formal. Root README is superseded (24.37 versus corrected 25.3990). The 21 stale censor flags were already corrected on September 11; retain that correction. No original inputs are changed. New LOCO analysis is conditional on archived labels pending demand integrity diagnosis. Guardrail construction scripts exist, but original synthetic seed labels are missing; independent origin is documented, numerical reconstruction remains unverified.\n')
 md('DEMAND_EXECUTION_AUDIT.md',f'# Demand execution audit\n\nAudited {len(e)} archived seed rows. {int(e.technical_invalid.sum())} explicit timeout/invalid rows. All historical actual robot entry counts and agent-level arrival plans are missing. Do not interpret that missingness as zero capacity or discard congested runs.\n\nRoutes use deterministic personsPerHour, not Poisson arrivals. Pedestrians are split equally across eA/eB and robots enter eA. Exact scheduled counts require generated route/simulator timing; q times duration is only a diagnostic here. FCD metric parser explicitly filters type=ped, so robots are excluded from density and speed. Baseline speed is the across-seed mean for the same scenario, not a seed-paired denominator. personinfo includes completed trips; the historical 100-second tail does not prove that every planned or inserted agent is counted. Historical success cleanup deletes the XML. Therefore entry waiting, end stock, actual robot entry and conservation cannot be reconstructed from the CSV alone. New diagnostics must retain all raw XML and compare scheduled IDs, walk departure, FCD and personinfo.\n\nTimeouts were historically encoded as speed=0, density=99; corrected analyses must classify these as technical failures, not valid service failures. HK runner additionally did not check subprocess return code. No 80% rule is imposed on mixed or robot flows.\n')
 md('HK_EXCLUSION_AUDIT.md','# Hong Kong exclusions\n\n'+hr[hr.integrity!='ok'].to_string(index=False)+'\n\nThese are legacy recorded-inflow exclusions, not established technical causes. ST-05/ST-24 zero counts and ST-16/ST-19/ST-22 partial counts require preserved-log diagnosis. Congestion is not a data-deletion justification. Original 32 selected / 18 in-domain / 13 retained remains a historical analysis subset, not an independently certified valid subset.\n')
 print(pd.DataFrame(checks).to_string(index=False));print(m.groupby(['dataset','method','status']).size().to_string());print('seed rows',len(e),'technical invalid',e.technical_invalid.sum(),flush=True)
def freeze():
 p=OUT/'analysis_protocol.yaml'
 if p.exists():print('Protocol already frozen',sha(p));return
 protocol=dict(version='2026-09-15-v1',created_utc=pd.Timestamp.now(tz='UTC').isoformat(),data_sha256=sha(FREEZE/'data/corrected_reference_dataset.csv'),config_sha256=sha(FREEZE/'final_quota_method_config.json'),primary='Fixed Q80 strict LOCO on archived labels; provisional until demand audit resolved',models={'M0':'log(q/W)=a+p log(x), Q80','M1':'M0 zero-margin ablation','M2':'log(q)=a+b log(W), Q80','M3':'log(q)=a+b log(W)+d log(qp), Q80'},fit='positive uncensored training only; archived rounded x for M0 reproduction',margin='quantile(max(nominal-reference,0), .80) all training rows',split='seven outer city folds; all cells grouped; no HK training',guardrails='frozen historical configuration; raw guardrail labels unavailable',seeds=list(range(30)),independent_seeds=list(range(10000,10030)),workers=min(4,max(1,(os.cpu_count() or 2)//2)),simulation_wall_budget_seconds=28800,qualification='30 unique seeds, same config, no technical invalid, >=29 pass',historical_reuse='legacy service metrics separately labelled; no claim of raw inflow verification',queue='union frozen M0/M1, all LOCO M0-M3, HK M0-M3 positive recommendations; config-key dedup; baseline diagnostics first',replication='all nonmonotone scenarios and M0 exact failures sorted dataset/tag; maximum first 3; low/high and neighboring integer flows; one independent block with paired baseline',sensitivity='after core: baseline29, qualification27/30, density1.0/1.4, speed.95, train-domain margin; model specification only if budget remains',stop='budget or technical blocker; retain unresolved and resumable jobs; no replacement seeds to improve outcomes',inflow='No new threshold; retain actual insertion/exit/stock and completed-trip counters separately. Congested valid failure retained.',reference_versions=['q_star_frozen','q_star_revised only after complete error-corrected rescan','q_star_observed_augmented selective tests never training'],bootstrap={'replicates':5000,'seed':2026091501,'unit':'cell with multiplicity','paired':True,'fixed_predictions':True})
 js('analysis_protocol.yaml',protocol);md('ANALYSIS_PROTOCOL.md','# Frozen analysis protocol\n\nJSON-compatible YAML in analysis_protocol.yaml is frozen before new simulations and baseline predictions. This is a session protocol, not preregistration or a new blinded HK test. Raw arrival evidence is missing historically; archival LOCO is provisional and must not be presented as a certified corrected model. Exact qualification and reference exceedance are separate. All positive references, including zero recommendations, enter utilization; no clipping. Shared gates are fixed; fit/margin use training data only. All planned flow groups retain 30 seeds. Maximum four workers and eight hours cumulative new simulation wall time. Measure pilot time and memory before bulk execution.\n');js('model_definitions.yaml',protocol['models'])
def fit_model(d,m):
 f=d[d.fit_eligible & d.qr_star.between(0,20,inclusive='neither') & (d.qp>0) & (d.W>0)]
 if m in ['M0','M1']:X=np.c_[np.ones(len(f)),np.log(f.x)];y=np.log(f.qr_star/f.W)
 elif m=='M2':X=np.c_[np.ones(len(f)),np.log(f.W)];y=np.log(f.qr_star)
 else:X=np.c_[np.ones(len(f)),np.log(f.W),np.log(f.qp)];y=np.log(f.qr_star)
 coef=np.linalg.lstsq(X,y,rcond=None)[0];return coef,len(f),np.linalg.matrix_rank(X),np.linalg.cond(X)
def nominal(d,m,c):
 if m in ['M0','M1']:return np.exp(c[0])*d.W*(d.qp/d.W)**c[1]
 if m=='M2':return np.exp(c[0])*d.W**c[1]
 return np.exp(c[0])*d.W**c[1]*d.qp**c[2]
def predict(d,m,c,de):
 g=CFG['guardrails'];nom=nominal(d,m,c);out=[]
 for i,r in enumerate(d.itertuples()):
  geom=dict(type=getattr(r,'type',getattr(r,'geometry_type','A')),sinuosity=r.sinuosity,max_turn_deg=getattr(r,'max_turn_deg',0),cum_turn_deg=getattr(r,'cum_turn_deg',0))
  dom=OperationalQuota(CFG).in_domain(r.W,r.qp,geom)
  if not dom:out.append((np.nan,'DOMAIN'))
  elif pd.isna(r.vbar) or pd.isna(r.base_pass):out.append((np.nan,'INSUFFICIENT_INPUT'))
  elif r.base_pass==0 or r.vbar<.8 or r.qp>=np.interp(r.W,g['C_W']['W'],g['C_W']['C']):out.append((0,'SERVICE'))
  else:
   q=math.floor(min(20,np.interp(r.W,g['Q_low']['W'],g['Q_low']['Q']),max(0,nom.iloc[i]-de)));out.append((q,'ADMITTED' if q>0 else 'MARGIN_FLOOR'))
 return out
def analyze():
 d=data();h=read('final_freeze_29of30_corrected/data/hk_original_valid.csv');rows=[];pars=[];assign=[]
 bad=set(evidence().query('dataset == "Development" and qr == 0 and timed_out != 0').tag)
 # Fixed-body corridor infeasibility is a development geometry audit, not an outcome-tuned threshold.
 if (OUT/'revised_analysis/narrow_robot_geometric_feasibility.csv').exists():
  infeasible=pd.read_csv(OUT/'revised_analysis/narrow_robot_geometric_feasibility.csv');bad |= set(infeasible[infeasible.robot_center_feasible_area==0].tag)
 d.loc[d.combo_id.isin(bad),'qr_star']=np.nan
 status=d.copy();status['q_star_frozen']=data().qr_star;status['q_star_revised']=np.nan;status['reference_status']=np.where(status.qr_star.isna(),'UNRESOLVED_BASELINE_TIMEOUT_OR_ROBOT_GEOMETRY','ARCHIVED_SERVICE_LABEL_INFLOW_UNVERIFIED');csv('revised_analysis/reference_status.csv',status)
 for city in sorted(d.city.unique()):
  tr=d[(d.city!=city)&d.qr_star.notna()];te=d[d.city==city];assert not set(tr.cell_id)&set(te.cell_id)
  assign.extend(dict(combo_id=r.combo_id,cell_id=r.cell_id,heldout_city=city) for r in te.itertuples())
  for m in ['M0','M1','M2','M3']:
   c,n,rank,cond=fit_model(tr,m);nt=nominal(tr,m,c)
   # Retain archived rounded x for calibration of the constrained historical estimator.
   if m in ['M0','M1']:nt=np.exp(c[0])*tr.W*tr.x**c[1]
   de=0 if m=='M1' else float(np.quantile(np.maximum(nt-tr.qr_star,0),.8))
   pars.append(dict(city=city,model=m,coefficients=json.dumps(c.tolist()),margin=de,fit_n=n,rank=rank,condition_number=cond,training_cities='|'.join(sorted(tr.city.unique()))))
   for r,(q,reason) in zip(te.itertuples(),predict(te,m,c,de)):rows.append(dict(dataset='Development',scope='LOCO',method=m,tag=r.combo_id,cell_id=r.cell_id,city=r.city,quota=q,reason=reason,q_star_frozen=r.qr_star))
 for m in ['M0','M1','M2','M3']:
  train=d[d.qr_star.notna()];c,n,rank,cond=fit_model(train,m);nt=nominal(train,m,c)
  if m in ['M0','M1']:nt=np.exp(c[0])*train.W*train.x**c[1]
  de=0 if m=='M1' else float(np.quantile(np.maximum(nt-train.qr_star,0),.8))
  pars.append(dict(city='ALL_DEVELOPMENT',model=m,coefficients=json.dumps(c.tolist()),margin=de,fit_n=n,rank=rank,condition_number=cond,training_cities='|'.join(sorted(d.city.unique()))))
  for dataset,z in [('Development',d),('Hong Kong',h)]:
   for r,(q,reason) in zip(z.itertuples(),predict(z,m,c,de)):rows.append(dict(dataset=dataset,scope='Frozen pooled',method=m,tag=getattr(r,'combo_id',r.cell_id),cell_id=r.cell_id,city=getattr(r,'city','Hong Kong'),quota=q,reason=reason,q_star_frozen=r.qr_star))
 pred=pd.DataFrame(rows);pred['reference_for_analysis']=pred.q_star_frozen;original=data().set_index('combo_id').qr_star;devmask=pred.dataset=='Development';pred.loc[devmask,'q_star_frozen']=pred.loc[devmask,'tag'].map(original);csv('revised_analysis/loco_predictions_all_methods.csv',pred[pred.scope=='LOCO']);csv('revised_analysis/pooled_and_HK_frozen_predictions.csv',pred[pred.scope!='LOCO']);csv('revised_analysis/loco_fit_and_margin_parameters.csv',pd.DataFrame(pars));csv('revised_analysis/fold_assignments.csv',pd.DataFrame(assign))
 metrics=[]
 for keys,z in pred.groupby(['dataset','scope','method']):
  a=z[z.quota.notna()];pos=a.q_star_frozen>0;ex=a.quota-a.q_star_frozen
  metrics.append(dict(zip(['dataset','scope','method'],keys),total=len(z),n=len(a),abstain=int(z.quota.isna().sum()),positive_reference_n=int(pos.sum()),positive_recommendations=int((a.quota>0).sum()),zero=int((a.quota==0).sum()),reference_exceedance=int((ex>0).sum()),exceedance_rate=float((ex>0).mean()),maximum_exceedance=float(max(0,ex.max())),mae=float(abs(ex).mean()),median_utilization=float(np.median(a.loc[pos,'quota']/a.loc[pos,'q_star_frozen']))))
 csv('revised_analysis/baseline_comparison_reference_metrics.csv',pd.DataFrame(metrics))
 newcfg=copy.deepcopy(CFG);newcfg['method_version']='M0-audited-390-20260915';newcfg['safety_margin']['delta']=next(r['margin'] for r in pars if r['city']=='ALL_DEVELOPMENT' and r['model']=='M0');newcfg['dataset']['path']='revised_analysis/reference_status.csv';newcfg['dataset']['sha256']=sha(OUT/'revised_analysis/reference_status.csv');newcfg['dataset']['note']='390 conditional archival labels; ten unresolved excluded; raw historical demand integrity not certified';newcfg['dataset_version']='400 archival records, 390 used in revised calibration, 10 unresolved';newcfg['dataset']['calibration_rows']=390;newcfg['dataset']['unresolved_rows']=10;newcfg['safety_margin']['note']='Development-only Q80 on 390 known archival references; historical input execution remains incompletely verified';js('revised_analysis/final_quota_config.json',newcfg)
 diag=d[['combo_id','cell_id','city','source','W','qp','x','qr_star','fit_eligible']].copy();diag['qp_over_W']=diag.qp/diag.W;csv('revised_analysis/powerlaw_structure_diagnostics.csv',diag);csv('revised_analysis/design_correlations.csv',diag[['W','qp','qp_over_W']].corr().reset_index())
 cc=d.groupby('city').agg(cells=('cell_id','nunique'),scenarios=('combo_id','size'),fit=('fit_eligible','sum'),evaluation=('operational_member','sum'));cc['main']=d[d.source=='main'].groupby('city').size();cc['additional']=cc.scenarios-cc['main'];csv('revised_analysis/city_counts.csv',cc.reset_index())
 md('BASELINE_AND_GENERALIZATION_REPORT.md','# Conditional archived-label comparison\n\n'+pd.DataFrame(metrics).to_string(index=False)+'\n\nAll coefficients and margins are training-only. HK has no training role. Rounded archived specific demand is retained in constrained-model fitting/margin to reproduce the frozen model; runtime uses qp/W. M2/M3 use width and actual nominal demand. Width exponent 1-p is imposed by b+d=1, not an independently estimated physical law. Results are provisional until demand audit is resolved; The author-supplied 48-row grid and 14,400 matching archived seed records reproduce all guardrail labels and knots; actual-entry XML remains unavailable.\n')
 print(pd.DataFrame(metrics).to_string(index=False),flush=True)
def queue():
 pred=pd.concat([pd.read_csv(OUT/'revised_analysis/loco_predictions_all_methods.csv'),pd.read_csv(OUT/'revised_analysis/pooled_and_HK_frozen_predictions.csv'),pd.read_csv(OUT/'original_reproduction/exact_flow_matches.csv')]);pred=pred[pred.quota>0]
 _,g=score(evidence());rows=[];cfg_hash=sha(ROOT/'pipeline/sim/scripts/config.py');geom_dev=json.loads((ROOT/'pipeline/cells/selected_cells.json').read_text())['cells'];gm={r['cell_id']:r for r in geom_dev};dc={r['combo_id']:r for r in json.loads((ROOT/'pipeline/cells/decoupled_cells.json').read_text())['combos']};hk=json.loads((ROOT/'external_validation/hong_kong/sites/hk_formal_local_geometry.json').read_text());dd=data().set_index('combo_id')
 for (dataset,tag,q),z in pred.groupby(['dataset','tag','quota']):
  geom=hk[tag] if dataset=='Hong Kong' else (dc[tag.split('|')[0]] if tag.startswith('DC-') else gm[dd.loc[tag,'cell_id']]);gh=hashlib.sha256(json.dumps(geom,sort_keys=True).encode()).hexdigest();dh=sha(ROOT/'pipeline/sim/scripts/simulator.py');hit=g[(g.dataset==dataset)&(g.tag==tag)&(g.qr==q)]
  for seed in range(30):
   key=hashlib.sha256(f'{dataset}|{tag}|{gh}|{dh}|{cfg_hash}|{q}|{seed}'.encode()).hexdigest()
   rows.append(dict(job_key=key,dataset=dataset,tag=tag,qr=q,seed=seed,geometry_hash=gh,demand_protocol_hash=dh,simulator_config_hash=cfg_hash,methods='|'.join(sorted(set(z.method))),scopes='|'.join(sorted(set(z.scope))),legacy_flow_status=hit.iloc[0].status if len(hit) else 'UNTESTED',status='LEGACY_METRICS_ONLY' if len(hit) else 'PENDING'))
 q=pd.DataFrame(rows);csv('exact_flow_queue.csv',q);print(q.groupby('status').size(), 'unique groups',len(q.drop_duplicates(['dataset','tag','qr'])),flush=True)
if __name__=='__main__':
 for stage in sys.argv[1:]:globals()[stage]()

