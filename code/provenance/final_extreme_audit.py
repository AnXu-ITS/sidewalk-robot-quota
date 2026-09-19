"""Read-only independent trajectory check; no original logs modified."""
from pathlib import Path
import json,gzip,sys,re,hashlib,xml.etree.ElementTree as ET
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent; R=O.parent; F=O/'submission_final'
loc=json.loads((F/'extreme_location.json').read_text()); key=loc['seed']['spec_hash']; p=R/'runs'/key
spec=json.loads((p/'spec.json').read_text()); result=json.loads((p/'result.json').read_text())
hash_ok={n:hashlib.sha256((p/n).read_bytes()).hexdigest()==h for n,h in result['raw_hashes'].items()}
assert all(hash_ok.values())
cl=np.array(spec['centerline']); delta=np.diff(cl,axis=0); lengths=np.linalg.norm(delta,axis=1); cum=np.r_[0,np.cumsum(lengths)]
initial={}; moved={}; maxdist={}; times=[]; counts=[]; speeds=[]; zonecounts=[]
with gzip.open(p/'personfcd.xml.gz','rb') as f:
 for _,el in ET.iterparse(f,events=('end',)):
  if el.tag!='timestep':continue
  t=float(el.get('time')); nz=0; sm=0
  for a in el.iter('person'):
   ident=a.get('id');xy=np.array([float(a.get('x')),float(a.get('y'))]);initial.setdefault(ident,xy);dist=float(np.linalg.norm(xy-initial[ident]));maxdist[ident]=max(dist,maxdist.get(ident,0))
   if dist>.05:moved.setdefault(ident,t)
   if 100<=t<340 and a.get('type')=='ped':
    u=np.clip(np.sum((xy-cl[:-1])*delta,axis=1)/lengths**2,0,1); near=cl[:-1]+u[:,None]*delta; j=np.argmin(np.sum((xy-near)**2,axis=1));s=cum[j]+u[j]*lengths[j]
    if 15<=s<=35:nz+=1;sm+=float(a.get('speed'))
  if 100<=t<340:times.append(t);counts.append(nz);speeds.append(sm)
  el.clear()
mean_speed=sum(speeds)/sum(counts); density=np.mean(counts)/(20*spec['W'])
assert abs(mean_speed-result['mean_speed'])<1e-9
assert sum(counts)==result['speed_count']
assert abs(density-result['mean_density'])<1e-9
agents=pd.read_csv(p/'arrival_schedule_and_observation.csv');agents['first_moved_005m']=agents.id.map(moved);agents['max_displacement_m']=agents.id.map(maxdist)
err=gzip.open(p/'sumo.err.gz','rt',errors='replace').read()
boundary=set(re.findall(r"adding person '([^']+)'.*(?:geometry boundaries|not inside walkable area)",err));neighbors=set(re.findall(r"adding person '([^']+)'.*too close to agent",err))
stats={}
for typ in ['ped','robot']:
 a=agents[agents.type.eq(typ)]; w=a[a.scheduled.between(100,340,inclusive='left')]
 stats[typ]={'scheduled_window':len(w),'observed_window_cohort':int(w.first_fcd.notna().sum()),'moved_window_cohort_by_end':int(w.first_moved_005m.notna().sum()),'boundary_rejected_agents_total':len(set(a.id)&boundary),'never_moved_boundary_agents':len(set(a[a.first_moved_005m.isna()].id)&boundary),'neighbor_rejected_agents_total':len(set(a.id)&neighbors),'stock_start':result[typ+'_stock_100'],'stock_near_end':result[typ+'_stock_339']}
raw=pd.read_csv(F/'raw_index_before.csv');b=raw[raw.dataset.eq('Development')&raw.tag.eq(spec['tag'])&raw.qr.eq(0)&raw.configuration.eq('historical')].drop_duplicates('seed');assert len(b)==30
vbar=float(b.mean_speed.mean()); ret=mean_speed/vbar
out={'spec_hash':key,'technical_exit_code':result['exit_code'],'all_raw_hashes_match':all(hash_ok.values()),'window_timesteps':len(times),'first_time':min(times),'last_time':max(times),'zone_observations':sum(counts),'empty_zone_timesteps':sum(n==0 for n in counts),'mean_speed_recomputed':mean_speed,'baseline_mean':vbar,'speed_retention_recomputed':ret,'density_recomputed':density,'completed_departures':result['inflow_ped'],'completed_arrivals':result['outflow_ped'],'throughput_defined':False,'seed_service_status':'FAIL','agents':stats,'error_lines':len(err.splitlines())}
agents.to_csv(F/'extreme_agent_movement.csv',index=False);(F/'EXTREME_SPEED_RAW_AUDIT.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
