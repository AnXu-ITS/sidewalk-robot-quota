"""Optional one-seed runner using preserved configuration specifications.

Default --inspect prints the chosen specification without running any engine.
Explicit --run requires SUMO 1.27.1 with JuPedSim and retains all raw outputs.
No fit/reference/table is updated by this runner.
"""
from pathlib import Path
import argparse, json, os, sys, shutil, subprocess, hashlib
ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--index',type=int,default=0)
    ap.add_argument('--seed',type=int,default=0,choices=range(30))
    ap.add_argument('--run',action='store_true')
    ap.add_argument('--inspect',action='store_true')
    args=ap.parse_args()
    specs=json.loads((ROOT/'configs/run_specs.json').read_text(encoding='utf8'))
    s=specs[args.index]['spec'].copy();s['seed']=args.seed
    if not args.run:
        print(json.dumps(s,indent=2));return
    def binary(name):
        home=os.environ.get('SUMO_HOME')
        candidate=Path(home)/'bin'/(name+'.exe' if os.name=='nt' else name) if home else None
        path=str(candidate) if candidate and candidate.exists() else shutil.which(name)
        if not path:raise RuntimeError('Install SUMO 1.27.1 with JuPedSim; set SUMO_HOME or PATH')
        return path
    sumo,netconvert=binary('sumo'),binary('netconvert')
    version=subprocess.check_output([sumo,'--version'],text=True)
    if '1.27.1' not in version:raise RuntimeError('Engine version differs from frozen 1.27.1; create a new study version instead')
    sys.path.insert(0,str(ROOT/'code/simulation'))
    import simulator as sim
    sim.SUMO_BIN=sumo;sim.NETCONVERT_BIN=netconvert
    digest=hashlib.sha256(json.dumps(s,sort_keys=True).encode()).hexdigest()
    folder=ROOT/'outputs/runs'/digest;folder.mkdir(parents=True,exist_ok=False)
    (folder/'spec.json').write_text(json.dumps(s,indent=2))
    (folder/'engine_version.txt').write_text(version)
    net=sim._build_net(str(folder),s['W'],s['L'],s.get('net_centerline',s['centerline']))
    if s['polygon'] is None:add=sim._build_additional(str(folder),s['W'],s['L'],s['centerline'])
    else:
        shape=' '.join(f'{x:.3f},{y:.3f}' for ring in s['polygon'] for x,y in ring)
        add=str(folder/'cell.add.xml');Path(add).write_text(f'<additional><poly id="walkable" type="jupedsim.walkable_area" color="179,217,255" fill="1" layer="0" shape="{shape}"/></additional>')
    route=sim._build_routes(str(folder),s['W'],s['L'],s['qp'],s['qr'],s['ped'],s['robot'],s['sim'],s['sim']['bidirectional_split'],s['robot']['v_ref'],s['seed'])
    cfg=sim._build_sumocfg(str(folder),net,route,add,s['seed'],s['sim'])
    cmd=[sumo,'-c',cfg,'--no-warnings','true','--error-log',str(folder/'sumo.err'),'--no-duration-log','true','--ignore-route-errors','true','--person-device.fcd.probability','1.0','--person-device.fcd.period','1.0']
    (folder/'command.json').write_text(json.dumps(cmd,indent=2))
    with (folder/'stdout_stderr.log').open('w') as log:
        try:exitcode=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=s['sim']['timeout_sec']).returncode
        except subprocess.TimeoutExpired:exitcode=None
    result={'exit_code':exitcode,'status':'TECHNICAL_INVALID','seed':args.seed}
    if exitcode==0:
        v,n,k,dep,arr,_=sim._parse(str(folder),s['W'],s['sim'],s['centerline'])
        result.update(status='COMPLETED_DIAGNOSTIC',mean_speed=v,speed_count=n,mean_density=k,inflow_ped=dep,outflow_ped=arr,throughput_ratio=arr/dep if dep>0 else None)
    result['note']='No service PASS label without a complete matching 30-seed baseline and group; undefined throughput fails the component.'
    result['raw_hashes']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()}
    (folder/'result.json').write_text(json.dumps(result,indent=2));print(folder)


if __name__=='__main__':main()
