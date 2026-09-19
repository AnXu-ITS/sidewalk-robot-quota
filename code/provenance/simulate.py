"""Preserved-log diagnostics and resumable exact-flow execution."""
import os,sys,json,time,hashlib,subprocess,ctypes,copy,gzip,shutil,xml.etree.ElementTree as ET
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import numpy as np
import pandas as pd
from runner import ROOT,OUT,sha,js,data
sys.path.insert(0,str(ROOT/'pipeline/sim/scripts'))
import simulator as sim
from config import PED,ROBOT,SIM,SUMO_BIN
GM={r['cell_id']:r for r in json.loads((ROOT/'pipeline/cells/selected_cells.json').read_text(encoding='utf-8'))['cells']}
DC={r['combo_id']:r for r in json.loads((ROOT/'pipeline/cells/decoupled_cells.json').read_text(encoding='utf-8'))['combos']}
HK=json.loads((ROOT/'external_validation/hong_kong/sites/hk_formal_local_geometry.json').read_text(encoding='utf-8'))
D=data().set_index('combo_id');H=pd.read_csv(ROOT/'external_validation/hong_kong/sites/HONG_KONG_FORMAL_SAMPLE_FREEZE.csv').set_index('cell_id')
def spec(dataset,tag,qr,seed,entrance_version='historical'):
 if dataset=='Development':
  r=D.loc[tag];g=DC[tag.split('|')[0]] if tag.startswith('DC-') else GM[r.cell_id];cl=g['centerline'];poly=None;W=float(r.W);L=50.;qp=float(r.qp)
 else:
  g=HK[tag];cl=g['centerline_local'];poly=g['walkable_polygon_local']['coordinates'];W=float(H.loc[tag,'W']);L=float(g['L']);qp=float(pd.read_csv(ROOT/'external_validation/hong_kong/runs/formal/hk_reference_qr_star.csv').set_index('cell_id').loc[tag,'qp'])
 s=dict(dataset=dataset,tag=tag,qr=float(qr),seed=int(seed),W=W,L=L,qp=qp,centerline=cl,polygon=poly,sim=SIM,ped=PED,robot=ROBOT,simulator_source_hash=sha(ROOT/'pipeline/sim/scripts/simulator.py'),config_hash=sha(ROOT/'pipeline/sim/scripts/config.py'),engine_version='SUMO 1.27.1',instrumentation_version='preserve-xml-v1')
 if entrance_version.startswith('assumption-'):
  if dataset!='Development':raise ValueError('Assumption checks are development-only')
  s.update(entrance_version=entrance_version,sim=copy.deepcopy(SIM),robot=copy.deepcopy(ROBOT))
  factor={'assumption-size080-v1':.8,'assumption-size120-v1':1.2}.get(entrance_version,1.)
  for field in ['length','width','radius']:s['robot'][field]*=factor
  if entrance_version=='assumption-direction075-v1':s['sim']['bidirectional_split']=.75
  if entrance_version not in ['assumption-reference-v1','assumption-size080-v1','assumption-size120-v1','assumption-direction075-v1']:raise ValueError(entrance_version)
 elif entrance_version!='historical':
  from shapely.geometry import Polygon,Point
  from shapely.ops import nearest_points
  safe=Polygon(poly[0],poly[1:]).buffer(-.75)
  if safe.is_empty:raise ValueError('No 0.75m-clearance entrance anchor; cannot apply deterministic technical repair')
  a=nearest_points(Point(cl[0]),safe)[1];b=nearest_points(Point(cl[-1]),safe)[1];direction=np.array(cl[-1])-np.array(cl[0]);direction=direction/np.linalg.norm(direction)
  s.update(entrance_version=entrance_version,entrance_clearance=.75,net_centerline=[(np.array(a.coords[0])-.35*direction).tolist(),(np.array(b.coords[0])+.15*direction).tolist()],entrance_anchors=[list(a.coords[0]),list(b.coords[0])])
 return s
def run(dataset,tag,qr,seed,entrance_version='historical'):
 s=spec(dataset,tag,qr,seed,entrance_version);key=hashlib.sha256(json.dumps(s,sort_keys=True).encode()).hexdigest();folder=OUT/'runs'/key;folder.mkdir(exist_ok=True)
 result=folder/'result.json'
 if result.exists():
  saved=json.loads(result.read_text());assert saved['spec_hash']==key
  for name,digest in saved['raw_hashes'].items():
   if not (folder/name).exists() or sha(folder/name)!=digest:raise RuntimeError(f'Existing job hash mismatch: {key}/{name}; preserve and investigate, never overwrite')
  return saved
 (folder/'spec.json').write_text(json.dumps(s,indent=2),encoding='utf-8');t=time.monotonic();peak=0
 m=dict(dataset=dataset,tag=tag,qr=qr,seed=seed,spec_hash=key,run_directory=str(folder.relative_to(OUT)),status='TECHNICAL_INVALID',exit_code=None,entrance_version=entrance_version)
 try:
  net=sim._build_net(str(folder),s['W'],s['L'],s.get('net_centerline',s['centerline']))
  if s['polygon'] is None:add=sim._build_additional(str(folder),s['W'],s['L'],s['centerline'])
  else:
   shape=' '.join(f'{x:.3f},{y:.3f}' for ring in s['polygon'] for x,y in ring);add=str(folder/'cell.add.xml');Path(add).write_text(f'<additional><poly id="walkable" type="jupedsim.walkable_area" color="179,217,255" fill="1" layer="0" shape="{shape}"/></additional>')
  route=sim._build_routes(str(folder),s['W'],s['L'],s['qp'],qr,s['ped'],s['robot'],s['sim'],s['sim']['bidirectional_split'],s['robot']['v_ref'],seed)
  cfg=sim._build_sumocfg(str(folder),net,route,add,seed,s['sim'])
  cmd=[SUMO_BIN,'-c',cfg,'--no-warnings','true','--error-log',str(folder/'sumo.err'),'--no-duration-log','true','--ignore-route-errors','true','--person-device.fcd.probability','1.0','--person-device.fcd.period','1.0']
  with (folder/'sumo.log').open('w') as log:
   p=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT)
   while p.poll() is None:
    # Measure resident memory from the process handle without global dependencies.
    class PMC(ctypes.Structure):_fields_=[('cb',ctypes.c_ulong),('PageFaultCount',ctypes.c_ulong),('PeakWorkingSetSize',ctypes.c_size_t),('WorkingSetSize',ctypes.c_size_t),('QuotaPeakPagedPoolUsage',ctypes.c_size_t),('QuotaPagedPoolUsage',ctypes.c_size_t),('QuotaPeakNonPagedPoolUsage',ctypes.c_size_t),('QuotaNonPagedPoolUsage',ctypes.c_size_t),('PagefileUsage',ctypes.c_size_t),('PeakPagefileUsage',ctypes.c_size_t)]
    mem=PMC();mem.cb=ctypes.sizeof(mem);ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.c_void_p(int(p._handle)),ctypes.byref(mem),mem.cb);peak=max(peak,mem.PeakWorkingSetSize)
    if time.monotonic()-t>SIM['timeout_sec']:p.kill();p.wait();raise TimeoutError('300-second fixed timeout; no substitute seed')
    time.sleep(.2)
   m['exit_code']=p.returncode
  if p.returncode:raise RuntimeError('SUMO nonzero exit')
  metrics=sim._parse(str(folder),s['W'],s['sim'],s['centerline']);m.update(dict(zip(['mean_speed','speed_count','mean_density','inflow_ped','outflow_ped','flow_ratio'],metrics)))
  agents=[]
  for _,el in ET.iterparse(folder/'personinfo.xml',events=('end',)):
   if el.tag!='personinfo':continue
   row=dict(el.attrib);w=el.find('walk');row.update({'walk_'+k:v for k,v in (w.attrib.items() if w is not None else [])});agents.append(row);el.clear()
  ad=pd.DataFrame(agents);ad.to_csv(folder/'completed_personinfo.csv',index=False)
  first={};last={};types={};stocks={100.:{'ped':0,'robot':0},339.:{'ped':0,'robot':0}}
  for _,el in ET.iterparse(folder/'personfcd.xml',events=('end',)):
   if el.tag!='timestep':continue
   tt=float(el.get('time'))
   for a in el.iter('person'):
    ident=a.get('id');typ=a.get('type');first.setdefault(ident,tt);last[ident]=tt;types[ident]=typ
    if tt in stocks and typ in stocks[tt]:stocks[tt][typ]+=1
   el.clear()
  observed=pd.DataFrame([dict(id=k,type=types[k],first_fcd=first[k],last_fcd=last[k]) for k in first]);observed.to_csv(folder/'observed_agents.csv',index=False)
  routes=ET.parse(route).getroot();schedules=[]
  for flow in routes.findall('personFlow'):
   start=float(flow.get('begin'));end=float(flow.get('end'));period=3600/float(flow.get('personsPerHour'))
   for i,tt in enumerate(np.arange(start,end-1e-9,period)):
    ident=flow.get('id')+'.'+str(i);schedules.append(dict(id=ident,type=flow.get('type'),scheduled=tt,first_fcd=first.get(ident),last_fcd=last.get(ident)))
  plan=pd.DataFrame(schedules);plan.to_csv(folder/'arrival_schedule_and_observation.csv',index=False)
  for typ in ['ped','robot']:
   z=plan[plan.type==typ];cohort=z.scheduled.between(100,340,inclusive='left');m[typ+'_planned_window']=int(cohort.sum());m[typ+'_cohort_observed_by_end']=int((cohort&z.first_fcd.notna()).sum());m[typ+'_fcd_first_window']=int(z.first_fcd.between(100,340,inclusive='left').sum());m[typ+'_never_observed']=int(z.first_fcd.isna().sum());m[typ+'_stock_100']=stocks[100.][typ];m[typ+'_stock_339']=stocks[339.][typ]
  m['status']='COMPLETED_DIAGNOSTIC';m['count_caveat']='FCD first observation is presence, not verified JuPedSim insertion; saved timestamps use the actual engine output step despite the requested 1-second device period. See per-agent first-position-update audit. Schedule inferred from deterministic personFlow.'
 except Exception as exc:m['error']=repr(exc)
 for _name in ('personfcd.xml','sumo.err'):
  _src=folder/_name
  if _src.exists():
   _dst=folder/(_name+'.gz')
   _dst.write_bytes(gzip.compress(_src.read_bytes(),mtime=0))
   _src.unlink()
 m['wall_seconds']=time.monotonic()-t;m['peak_sumo_rss_bytes']=peak;m['raw_hashes']={p.name:sha(p) for p in folder.iterdir() if p.is_file() and p.name!='result.json'}
 tmp=result.with_suffix('.tmp');tmp.write_text(json.dumps(m,indent=2),encoding='utf-8');tmp.replace(result);return m
def pilot():
 # Deterministic protocol-based diagnostic sample, selected before viewing new outputs.
 tags=[D[D.operational_member].sort_values(['W','qp']).index[0],D[D.operational_member].sort_values(['W','qp']).index[len(D[D.operational_member])//2]]
 tasks=[('Development',tags[0],0,0),('Development',tags[1],4,0)]+[('Hong Kong',x,0,0) for x in ['HK-ST-05','HK-ST-16','HK-ST-19','HK-ST-22','HK-ST-24']]
 js('pilot_selection.json',tasks)
 results=[]
 for task in tasks:
  r=run(*task);results.append(r);print(json.dumps({k:v for k,v in r.items() if k not in ['raw_hashes','count_caveat']}),flush=True)
 js('pilot_results.json',results)
def simulate():
 protocol=json.loads((OUT/'analysis_protocol.yaml').read_text());pilot=json.loads((OUT/'pilot_results.json').read_text())
 budget=dict(workers=protocol['workers'],wall_budget_seconds=28800,pilot_wall_seconds=sum(r['wall_seconds'] for r in pilot),pilot_peak_sumo_rss_bytes=max(r['peak_sumo_rss_bytes'] for r in pilot),pilot_max_run_seconds=max(r['wall_seconds'] for r in pilot),note='Seven pilots reproduce archived seed-0 metrics to floating precision; max SUMO RSS <23MB; <=4 workers, 12GB free memory. XML storage retained. All new groups use 30 original seeds. Outputs-only instrumentation leaves physical config unchanged.')
 js('resource_budget.json',budget)
 q=pd.read_csv(OUT/'exact_flow_queue.csv');tasks=[(r.dataset,r.tag,r.qr,r.seed) for r in q[q.status=='PENDING'].itertuples()]
 results=run_tasks(tasks,'simulation')
 print('batch complete',len(results),len(tasks),flush=True)

def repair_pilot():
 plan=dict(version='HK-entrance-repair-v1',selection=['HK-ST-05','HK-ST-16','HK-ST-19','HK-ST-22','HK-ST-24'],rule='Nearest point in original polygon eroded by 0.75m to each original endpoint; orient stubs along original principal axis. Physical polygon, width, measurement axis, speed, radius, arrivals unchanged. 0.75m clearance accommodates fixed 0.48m robot radius plus the 0.15m offset and 0.1m numerical allowance. No service-outcome tuning.',role='technical geometry repair diagnostic; separate configuration; old HK labels never reused',seeds=list(range(30)),grid=[0,1,2,3,4,5,6,8,10,12,15,18,20])
 if not (OUT/'HK_REPAIR_PROTOCOL.json').exists():js('HK_REPAIR_PROTOCOL.json',plan)
 results=[]
 for tag in plan['selection']:
  r=run('Hong Kong',tag,0,0,'nearest-safe-anchor-v1');results.append(r);print(tag,r['status'],r.get('inflow_ped'),r.get('wall_seconds'),flush=True)
 js('HK_repair_pilot_results.json',results)
def run_tasks(tasks,stage):
 t=time.monotonic();results=[];protocol=json.loads((OUT/'analysis_protocol.yaml').read_text())
 # A single process holds the campaign lock; batches are sequential, never additional worker pools.
 lock=OUT/'CAMPAIGN.lock'
 with lock.open('x') as f:f.write(str(os.getpid()))
 try:
  ledger_path=OUT/'campaign_wall_ledger.json'
  if ledger_path.exists():ledger=json.loads(ledger_path.read_text())
  else:
   ledger=[]
   for record in ['simulation_execution.json','HK_repair_baseline_execution.json','HK_repair_positive_execution.json','independent_replication_execution.json']:
    path=OUT/record
    if path.exists():
     x=json.loads(path.read_text());ledger.append(dict(stage=record,wall_seconds=float(x.get('wall_seconds',x.get('batch_wall_seconds',0))),origin='pre-ledger completed batch',source_sha256=sha(path)))
   for record in ['pilot_results.json','HK_repair_pilot_results.json']:
    path=OUT/record
    if path.exists():ledger.append(dict(stage=record,wall_seconds=sum(x['wall_seconds'] for x in json.loads(path.read_text())),origin='conservative pilot sum; overlap not subtracted'))
   js('campaign_wall_ledger.json',ledger)
  elapsed_previous=sum(x['wall_seconds'] for x in ledger)
  if elapsed_previous>=protocol['simulation_wall_budget_seconds']-SIM['timeout_sec']:
   print('Campaign wall budget reached; remaining tasks preserved',flush=True);return results
  with ThreadPoolExecutor(max_workers=protocol['workers']) as pool:
   from concurrent.futures import wait,FIRST_COMPLETED
   remaining=iter(tasks);futures={}
   for _ in range(protocol['workers']):
    try:task=next(remaining);futures[pool.submit(run,*task)]=task
    except StopIteration:break
   while futures:
    ready,_=wait(futures,timeout=30,return_when=FIRST_COMPLETED)
    for f in ready:
     futures.pop(f);r=f.result();results.append(r);i=len(results)
     if i%30==0:print(stage,i,'/',len(tasks),'seconds',round(time.monotonic()-t),flush=True)
     if elapsed_previous+time.monotonic()-t < protocol['simulation_wall_budget_seconds']-SIM['timeout_sec']:
      try:task=next(remaining);futures[pool.submit(run,*task)]=task
      except StopIteration:pass
  elapsed=time.monotonic()-t
  js(stage+'_execution.json',dict(completed=len(results),planned=len(tasks),wall_seconds=elapsed))
  ledger.append(dict(stage=stage,wall_seconds=elapsed,finished_utc=pd.Timestamp.now(tz='UTC').isoformat(),completed=len(results),planned=len(tasks)))
  js('campaign_wall_ledger.json',ledger)
 finally:lock.unlink()
 return results
def repair():
 plan=json.loads((OUT/'HK_REPAIR_PROTOCOL.json').read_text());tasks=[('Hong Kong',tag,0,seed,'nearest-safe-anchor-v1') for tag in plan['selection'] for seed in plan['seeds']]
 base=run_tasks(tasks,'HK_repair_baseline');b=pd.DataFrame(base);b.to_csv(OUT/'revised_analysis/HK_repair_baseline.csv',index=False)
 from runner import predict,csv
 geom=pd.read_csv(ROOT/'external_validation/hong_kong/sites/HONG_KONG_FORMAL_SAMPLE_FREEZE.csv').set_index('cell_id');original=pd.read_csv(ROOT/'external_validation/hong_kong/runs/formal/hk_reference_qr_star.csv').set_index('cell_id');hb=b.groupby('tag').agg(vbar=('mean_speed','mean'),density=('mean_density','mean'),flow=('flow_ratio','mean'));params=pd.read_csv(OUT/'revised_analysis/loco_fit_and_margin_parameters.csv');pred=[]
 h=original.loc[plan['selection']].copy();h['cell_id']=h.index;h['geometry_type']=h.index.map(geom.geometry_type);h['sinuosity']=h.index.map(geom.sinuosity);h['max_turn_deg']=h.index.map(geom.max_turn_deg);h['cum_turn_deg']=h.index.map(geom.cum_turn_deg);h['vbar']=h.index.map(hb.vbar);h['base_pass']=((h.index.map(hb.density)<=1.2)&(h.index.map(hb.flow)>=.9)&(h.index.map(hb.flow)<=1.2)).astype(int)
 for method in ['M0','M1','M2','M3']:
  param=params[(params.city=='ALL_DEVELOPMENT')&(params.model==method)].iloc[0]
  for row,(q,reason) in zip(h.itertuples(),predict(h,method,np.array(json.loads(param.coefficients)),param.margin)):pred.append(dict(tag=row.cell_id,method=method,quota=q,reason=reason,parameter_source='development-only parameters; no HK-driven tuning',parameter_sha256=sha(OUT/'revised_analysis/loco_fit_and_margin_parameters.csv'),calibration_reference_version='390-known-archival-v1',configuration='nearest-safe-anchor-v1'))
 hp=pd.DataFrame(pred);csv('revised_analysis/HK_repaired_frozen_predictions.csv',hp)
 tasks=[]
 for tag in plan['selection']:
  flows=set(plan['grid'][1:])|set(hp[(hp.tag==tag)&(hp.quota>0)].quota.astype(int))
  tasks.extend(('Hong Kong',tag,q,seed,'nearest-safe-anchor-v1') for q in sorted(flows) for seed in plan['seeds'])
 js('HK_repair_queue.json',tasks);results=run_tasks(tasks,'HK_repair_positive');pd.DataFrame(results).drop(columns=['raw_hashes'],errors='ignore').to_csv(OUT/'revised_analysis/HK_repair_positive.csv',index=False)
def replication():
 from runner import evidence,score,csv
 _,g=score(evidence());candidates=[];pairs=[]
 for (dataset,tag),z in g.groupby(['dataset','tag']):
  for lo in z[z.status=='FAIL'].itertuples():
   for hi in z[(z.status=='PASS')&(z.qr>lo.qr)].itertuples():pairs.append(dict(dataset=dataset,tag=tag,low=lo.qr,high=hi.qr,low_passing=lo.passing,high_passing=hi.passing))
 pp=pd.DataFrame(pairs);csv('revised_analysis/nonmonotonicity_all_archived.csv',pp)
 from summarize import collect
 collect()
 failed=pd.read_csv(OUT/'exact_flow_status_by_method.csv');failed=failed[(failed.method=='M0')&(failed.exact_service_status=='FAIL')]
 keys=sorted(set(zip(pp.dataset,pp.tag))|set(zip(failed.dataset,failed.tag)))[:3];tasks=[]
 for dataset,tag in keys:
  z=pp[(pp.dataset==dataset)&(pp.tag==tag)];levels={0}
  if len(z):
   lo=int(z.iloc[0].low);hi=int(z.iloc[0].high);levels.update([lo,hi,max(1,lo-1),min(20,hi+1)])
  else:
   q=int(failed[(failed.dataset==dataset)&(failed.tag==tag)].iloc[0].quota);levels.update([max(1,q-1),q,min(20,q+1)])
  tasks.extend((dataset,tag,q,seed) for q in sorted(levels) for seed in range(10000,10030))
 if not (OUT/'replication_queue.json').exists():js('replication_queue.json',tasks)
 else:tasks=json.loads((OUT/'replication_queue.json').read_text())
 results=run_tasks(tasks,'independent_replication');pd.DataFrame(results).drop(columns=['raw_hashes'],errors='ignore').to_csv(OUT/'revised_analysis/independent_replication.csv',index=False)
def assumption_protocol():
 path=OUT/'ASSUMPTION_SENSITIVITY_PROTOCOL.json'
 if path.exists():return json.loads(path.read_text())
 z=D[D.operational_member].sort_values(['W','qp']);tags=[z.index[int((len(z)-1)*q)] for q in [.25,.75]]
 plan=dict(version='development-assumptions-v1',selection_rule='Sort eligible development scenarios by width then nominal demand; take 25th and 75th percentile positions using floor((n-1)*p); no HK or new service outcomes used',tags=tags,flow=4,seeds=list(range(30)),settings=['assumption-reference-v1','assumption-size080-v1','assumption-size120-v1','assumption-direction075-v1'],interpretation='Hypothesis sensitivity only: scale both robot dimensions and thus actual JuPedSim radius by 0.8 or 1.2; separately change bidirectional split from .5 to .75. No claim of calibrated physical range. Every configuration has its own complete 30-seed baseline.',planned_runs=480)
 js('ASSUMPTION_SENSITIVITY_PROTOCOL.json',plan);return plan

def assumptions():
 plan=assumption_protocol();tasks=[('Development',tag,q,seed,setting) for tag in plan['tags'] for setting in plan['settings'] for q in [0,plan['flow']] for seed in plan['seeds']]
 results=run_tasks(tasks,'assumption_sensitivity');pd.DataFrame(results).drop(columns=['raw_hashes'],errors='ignore').to_csv(OUT/'sensitivity/assumption_per_seed.csv',index=False)

if __name__=='__main__':globals()[sys.argv[1]]()
