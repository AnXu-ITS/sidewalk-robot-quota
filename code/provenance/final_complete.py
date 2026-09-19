from pathlib import Path
import json,sys,hashlib,sqlite3,copy,time
import pandas as pd
from concurrent.futures import ThreadPoolExecutor,as_completed
O=Path(__file__).resolve().parent; ROOT=O.parents[1]; RR=ROOT/'revision_review'; V=O/'reviewer_revision'; F=O/'submission_final';F.mkdir(exist_ok=True)
sys.path.insert(0,str(RR)); import simulate

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def physical(s):
 s=json.loads(json.dumps(s))
 return {k:v for k,v in s.items() if k not in ['qr','seed','simulator_source_hash','config_hash','instrumentation_version']}
def prepare():
 pred=pd.read_csv(V/'loco_predictions_v3.csv'); hk=pd.read_csv(V/'hk_analysis_v3.csv'); rec=pred[pred.quota.gt(0)].copy();rec['configuration']='historical'
 h=hk[hk.quota.gt(0)].copy();h['dataset']='Hong Kong';h['configuration']=h.configuration.map({'ORIGINAL':'historical','REPAIRED':'nearest-safe-anchor-v1'})
 rec=pd.concat([rec,h],ignore_index=True)
 raw=pd.read_csv(O/'raw_index_writing.csv'); raw=raw[raw.seed.between(0,29)&raw.status.eq('COMPLETED_DIAGNOSTIC')].copy()
 # Include completed registry records that post-date the writing index.
 conn=sqlite3.connect(f'file:{(RR/"run_registry.sqlite").as_posix()}?mode=ro',uri=True)
 known=set(raw.spec_hash); extra=[]
 for row in conn.execute("select job_key from seed_runs where status='COMPLETED_DIAGNOSTIC' and seed between 0 and 29"):
  key=row[0]
  if key in known:continue
  p=RR/'runs'/key/'result.json'
  if not p.exists():continue
  r=json.loads(p.read_text());r['configuration']=r.get('entrance_version','historical');extra.append(r)
 if extra:raw=pd.concat([raw,pd.DataFrame(extra)],ignore_index=True)
 raw=raw.drop_duplicates('spec_hash');raw.to_csv(F/'raw_index_before.csv',index=False)
 rows=[];tasks=[]; matches=[]
 for (ds,tag,conf,q),g in rec.groupby(['dataset','tag','configuration','quota']):
  z=raw[(raw.dataset==ds)&(raw.tag==tag)&(raw.configuration==conf)]
  b=z[z.qr.eq(0)].drop_duplicates('seed');assert len(b)==30,(ds,tag,conf,'baseline missing')
  bs=json.loads((RR/'runs'/b.iloc[0].spec_hash/'spec.json').read_text()); now=simulate.spec(ds,tag,float(q),0,conf)
  assert physical(bs)==physical(now),(ds,tag,'configuration mismatch')
  signature=hashlib.sha256(json.dumps(physical(bs),sort_keys=True).encode()).hexdigest()
  available=[]
  for r in z[z.qr.isin([0,q])].itertuples():
   folder=RR/'runs'/r.spec_hash
   ss=json.loads((folder/'spec.json').read_text())
   if physical(ss)!=physical(bs):continue
   rr=json.loads((folder/'result.json').read_text())
   needed=['personinfo.xml','spec.json','cell.rou.xml','cell.sumocfg','sumo.log']
   if not all((folder/n).exists() for n in needed):continue
   if not ((folder/'personfcd.xml.gz').exists() or (folder/'personfcd.xml').exists()):continue
   if rr.get('exit_code')!=0:continue
   available.append(r._asdict())
  a=pd.DataFrame(available).drop_duplicates(['qr','seed']); bb=a[a.qr.eq(0)]; mm=a[a.qr.eq(q)]
  assert len(bb)==30,(tag,'baseline raw incomplete')
  missing=sorted(set(range(30))-set(mm.seed))
  matches.append(dict(dataset=ds,scenario=tag,configuration=conf,flow=q,simulation_config=signature,seed_block='0-29',methods_using_this_flow='|'.join(sorted(g.method.unique())),baseline_available=len(bb),mixed_flow_available=len(mm),required_runs=len(missing)))
  if missing:
   rows.append(dict(matches[-1],reason_missing='No complete configuration-matched raw record for seeds '+','.join(map(str,missing))))
   tasks.extend((ds,tag,float(q),int(seed),conf) for seed in missing)
 pd.DataFrame(matches).to_csv(F/'ALL_POSITIVE_GROUPS.csv',index=False)
 pd.DataFrame(rows).to_csv(O/'FINAL_UNTESTED_QUEUE.csv',index=False);pd.DataFrame(rows).to_csv(F/'FINAL_UNTESTED_QUEUE.csv',index=False)
 (F/'tasks.json').write_text(json.dumps(tasks,indent=2))
 protected=[V/'reference_dataset_original_block_v3.csv',V/'fit_parameters_v3.csv',V/'loco_predictions_v3.csv',V/'hk_analysis_v3.csv',ROOT/'final_freeze_29of30_corrected/final_quota_method_config.json']
 (F/'frozen_hashes.json').write_text(json.dumps({str(p):sha(p) for p in protected},indent=2))
 print(pd.DataFrame(rows).to_string(index=False));print('unique groups',len(rows),'new seed runs',len(tasks),flush=True)

def run():
 tasks=json.loads((F/'tasks.json').read_text());start=time.monotonic();out=[]
 with ThreadPoolExecutor(max_workers=4) as pool:
  futures={pool.submit(simulate.run,*t):t for t in tasks}
  for f in as_completed(futures):
   r=f.result();out.append(r);(F/'new_runs.json').write_text(json.dumps(out,indent=2))
   print(len(out),'/',len(tasks),r['tag'],r['qr'],r['seed'],r['status'],round(time.monotonic()-start),flush=True)
 (F/'execution.json').write_text(json.dumps({'unique_groups':len(pd.read_csv(F/'FINAL_UNTESTED_QUEUE.csv')),'seed_runs':len(out),'wall_seconds':time.monotonic()-start,'statuses':pd.Series([x['status'] for x in out]).value_counts().to_dict()},indent=2))
 for p,h in json.loads((F/'frozen_hashes.json').read_text()).items():assert sha(p)==h,p
if __name__=='__main__':globals()[sys.argv[1]]()
