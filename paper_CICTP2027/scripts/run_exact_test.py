"""Inspect or explicitly rerun one preserved configuration/flow/seed group.

No execution without --run. Archived research files are never replaced. Healthy
and adverse completed runs share the same cache policy; technical failures stay
separate and no substitute seed is selected.
"""
from pathlib import Path
import argparse,copy,hashlib,json,os,shutil,subprocess,sys,time
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def one(s,configuration,out,engine,version):
    ident=hashlib.sha256(json.dumps(s,sort_keys=True).encode()).hexdigest();folder=out/ident
    if folder.exists():
        p=folder/'result.json'
        if not p.exists():raise RuntimeError('Interrupted directory retained; inspect it before continuing')
        r=json.loads(p.read_text(encoding='utf-8'))
        assert r['spec_hash']==ident
        for name,h in r['raw_hashes'].items():assert digest(folder/name)==h
        return r
    folder.mkdir(parents=True,exist_ok=False)
    (folder/'spec.json').write_text(json.dumps(s,indent=2),encoding='utf-8')
    (folder/'engine_version.txt').write_text(version,encoding='utf-8')
    t=time.monotonic();r=dict(dataset=s['dataset'],tag=s['tag'],configuration=configuration,qr=s['qr'],seed=s['seed'],
                             W=s['W'],qp=s['qp'],spec_hash=ident,status='TECHNICAL_FAILURE',exit_code=None)
    try:
        net=engine._build_net(str(folder),s['W'],s['L'],s.get('net_centerline',s['centerline']))
        if s['polygon'] is None:add=engine._build_additional(str(folder),s['W'],s['L'],s['centerline'])
        else:
            shape=' '.join(f'{x:.3f},{y:.3f}' for ring in s['polygon'] for x,y in ring);add=str(folder/'cell.add.xml')
            Path(add).write_text(f'<additional><poly id="walkable" type="jupedsim.walkable_area" color="179,217,255" fill="1" layer="0" shape="{shape}"/></additional>',encoding='utf-8')
        route=engine._build_routes(str(folder),s['W'],s['L'],s['qp'],s['qr'],s['ped'],s['robot'],s['sim'],s['sim']['bidirectional_split'],s['robot']['v_ref'],s['seed'])
        cfg=engine._build_sumocfg(str(folder),net,route,add,s['seed'],s['sim'])
        cmd=[engine.SUMO_BIN,'-c',cfg,'--no-warnings','true','--error-log',str(folder/'sumo.err'),'--no-duration-log','true',
             '--ignore-route-errors','true','--person-device.fcd.probability','1.0','--person-device.fcd.period','1.0']
        (folder/'command.json').write_text(json.dumps(cmd,indent=2),encoding='utf-8')
        with (folder/'stdout_stderr.log').open('w',encoding='utf-8') as log:
            p=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=s['sim']['timeout_sec'])
        r['exit_code']=p.returncode
        if p.returncode:raise RuntimeError('SUMO nonzero exit')
        v,n,k,dep,arr,_=engine._parse(str(folder),s['W'],s['sim'],s['centerline'])
        r.update(status='COMPLETED_DIAGNOSTIC',mean_speed=v,speed_count=n,mean_density=k,inflow_ped=dep,outflow_ped=arr,
                 throughput_ratio=arr/dep if dep>0 else None)
    except Exception as exc:r['error']=repr(exc)
    r['wall_seconds']=time.monotonic()-t
    r['raw_hashes']={p.name:digest(p) for p in folder.iterdir() if p.is_file()}
    (folder/'result.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
    return r

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--index',type=int,default=0)
    ap.add_argument('--flow',type=int);ap.add_argument('--seed',type=int);ap.add_argument('--block',choices=['original','independent'],default='original')
    ap.add_argument('--group',action='store_true');ap.add_argument('--with-baseline',action='store_true')
    ap.add_argument('--run',action='store_true');ap.add_argument('--inspect',action='store_true')
    ap.add_argument('--output',type=Path,default=ROOT/'outputs/reruns');args=ap.parse_args()
    record=json.loads((ROOT/'configs/run_specs.json').read_text(encoding='utf-8'))[args.index]
    s=copy.deepcopy(record['spec']);s['qr']=int(s['qr']) if args.flow is None else args.flow
    assert 0<=s['qr']<=20
    seeds=list(range(30)) if args.block=='original' else list(range(10000,10030))
    if args.seed is not None:assert args.seed in seeds and not args.group;seeds=[args.seed]
    elif not args.group:seeds=seeds[:1]
    flows=sorted({0,s['qr']}) if args.with_baseline else [s['qr']]
    s['seed']=seeds[0]
    if not args.run:
        print(json.dumps(dict(configuration=record['configuration'],spec=s,flows=flows,seeds=seeds,
                              note='Inspection only; no simulations launched'),indent=2));return
    sys.path.insert(0,str(ROOT/'src/engine'));import simulator as engine
    home=os.environ.get('SUMO_HOME')
    def binary(name):
        p=Path(home)/'bin'/(name+'.exe' if os.name=='nt' else name) if home else None
        return str(p) if p and p.exists() else shutil.which(name)
    engine.SUMO_BIN=binary('sumo');engine.NETCONVERT_BIN=binary('netconvert')
    assert engine.SUMO_BIN and engine.NETCONVERT_BIN,'SUMO and netconvert required'
    version=subprocess.check_output([engine.SUMO_BIN,'--version'],text=True)
    assert '1.27.1' in version and 'JuPedSim' in version,'Frozen simulator build required'
    results=[]
    for q in flows:
        for seed in seeds:
            spec=copy.deepcopy(s);spec.update(qr=float(q),seed=seed)
            results.append(one(spec,record['configuration'],args.output.resolve(),engine,version))
    d=pd.DataFrame(results);d.drop(columns=['raw_hashes'],errors='ignore').to_csv(args.output/'rerun_metrics.csv',index=False)
    # No group service claim from a single seed or an unmatched baseline.
    if args.group and args.with_baseline and d.status.eq('COMPLETED_DIAGNOSTIC').all():
        sys.path.insert(0,str(ROOT/'src'));from sidewalk_admission import seed_pass
        cfg=json.loads((ROOT/'configs/admission.json').read_text(encoding='utf-8'))
        base=d[d.qr.eq(0)];assert len(base)==30 and set(base.seed)==set(seeds)
        v=float(base.mean_speed.mean());summary=[]
        for q,z in d[d.qr.gt(0)].groupby('qr'):
            assert len(z)==30 and set(z.seed)==set(seeds)
            count=int(seed_pass(z,v,cfg['service']).sum());summary.append(dict(flow=q,passing=count,status='PASS' if count>=29 else 'FAIL'))
        (args.output/'group_service.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print('Preserved rerun records:',len(d),'technical failures:',int(d.status.ne('COMPLETED_DIAGNOSTIC').sum()))

if __name__=='__main__':main()
