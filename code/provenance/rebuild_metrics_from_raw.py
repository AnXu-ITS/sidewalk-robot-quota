"""Rebuild service metrics independently from preserved raw logs.

For every completed seed-run, this re-parses the raw SUMO/JuPedSim outputs
(personfcd.xml + personinfo.xml) with the exact frozen parser, recomputes
mean_speed, mean_density, N_in, N_out, flow_ratio, planned-vs-realized entry and
window stock, and verifies the values against both the run's result.json and the
historical aggregate CSV. The point is that the paper's service tables can be
regenerated from raw logs alone, not only from the aggregate CSV.
"""
import json, sys, xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'revision_review'
sys.path.insert(0, str(ROOT / 'pipeline/sim/scripts'))
from simulator import _parse  # noqa: E402  (frozen metric parser)
from config import SIM  # noqa: E402


def recompute_seed(folder):
    """Recompute service metrics + entry accounting from one run's raw files."""
    result = json.loads((folder / 'result.json').read_text())
    spec = json.loads((folder / 'spec.json').read_text())
    if result.get('status') != 'COMPLETED_DIAGNOSTIC':
        return dict(dataset=result.get('dataset'), tag=result.get('tag'),
                    qr=result.get('qr'), seed=result.get('seed'),
                    status=result.get('status'), error=result.get('error'))
    W = float(spec['W'])
    centerline = spec.get('centerline') or spec.get('net_centerline')
    mean_speed, speed_count, mean_density, inflow_ped, outflow_ped, flow_ratio = \
        _parse(str(folder), W, spec['sim'], centerline)

    # planned / realized entry from the saved schedule-observation table
    plan = pd.read_csv(folder / 'arrival_schedule_and_observation.csv')
    out = dict(
        dataset=result.get('dataset'), tag=result.get('tag'), qr=result.get('qr'),
        seed=result.get('seed'), W=W, qp=float(spec['qp']), status='COMPLETED_DIAGNOSTIC',
        mean_speed=float(mean_speed), speed_count=int(speed_count),
        mean_density=float(mean_density), inflow_ped=int(inflow_ped),
        outflow_ped=int(outflow_ped), flow_ratio=float(flow_ratio),
        exit_code=result.get('exit_code'), wall_seconds=result.get('wall_seconds'),
        spec_hash=result.get('spec_hash'),
    )
    for typ in ['ped', 'robot']:
        z = plan[plan.type == typ]
        cohort = z.scheduled.between(100, 340, inclusive='left')
        out[f'{typ}_planned_window'] = int(cohort.sum())
        out[f'{typ}_cohort_observed_by_end'] = int((cohort & z.first_fcd.notna()).sum())
        out[f'{typ}_never_observed'] = int(z.first_fcd.isna().sum())
    return out


def rebuild_all(limit=None, workers=4):
    folders = []
    for p in sorted((OUT / 'runs').glob('*/result.json')):
        try:
            r = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if r.get('status') != 'COMPLETED_DIAGNOSTIC':
            continue
        folders.append(p.parent)
    if limit:
        folders = folders[:limit]
    rows = []
    if workers > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for i, r in enumerate(pool.map(recompute_seed, folders, chunksize=8), 1):
                rows.append(r)
                if i % 200 == 0:
                    print(f'  rebuilt {i}/{len(folders)}', flush=True)
    else:
        for i, f in enumerate(folders, 1):
            rows.append(recompute_seed(f))
            if i % 200 == 0:
                print(f'  rebuilt {i}/{len(folders)}', flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / 'revised_analysis/raw_rebuilt_service_per_seed.csv', index=False)
    return df


def verify_against_result_json(df):
    """Confirm raw-rebuilt metrics equal the values captured in result.json."""
    mism = []
    for r in df.itertuples():
        saved = json.loads((OUT / 'runs' / r.spec_hash / 'result.json').read_text())
        for col in ['mean_speed', 'mean_density', 'inflow_ped', 'outflow_ped', 'flow_ratio']:
            a, b = getattr(r, col), saved.get(col)
            if not np.isclose(a, b, rtol=1e-9, atol=1e-12):
                mism.append((r.tag, r.qr, r.seed, col, a, b))
    print('raw-vs-result mismatches:', len(mism), flush=True)
    if mism:
        print(pd.DataFrame(mism, columns=['tag', 'qr', 'seed', 'col', 'raw', 'result']).head(10).to_string(index=False))
    return len(mism) == 0


def verify_against_legacy_csv(df):
    """Confirm raw-rebuilt metrics reproduce the historical aggregate CSV."""
    frames = []
    for f in ['multicity_baseline', 'decoupled_baseline', 'multicity_sweep',
              'decoupled_sweep', 'refinement_sweep']:
        d = pd.read_csv(ROOT / 'data/final' / (f + '.csv'))
        d['dataset'] = 'Development'
        frames.append(d)
    h = pd.read_csv(ROOT / 'external_validation/hong_kong/runs/formal/seed_results.csv').rename(columns={'cell_id': 'tag'})
    h['dataset'] = 'Hong Kong'
    frames.append(h)
    legacy = pd.concat(frames, ignore_index=True)

    # the reconstructed run reuses W/qp from the frozen dataset; legacy CSVs carry
    # identical W/qp (verified at reconstruction start), so join on the run key.
    legacy_key = legacy.set_index(['dataset', 'tag', 'qr', 'seed'])[
        ['mean_speed', 'mean_density', 'inflow_ped', 'outflow_ped', 'flow_ratio']]
    df_key = df.set_index(['dataset', 'tag', 'qr', 'seed'])
    j = df_key.join(legacy_key, lsuffix='_raw', rsuffix='_legacy', how='inner')
    mism = 0
    for col in ['mean_speed', 'mean_density', 'inflow_ped', 'outflow_ped', 'flow_ratio']:
        dcol = (j[f'{col}_raw'] - j[f'{col}_legacy']).abs()
        mism += int((dcol > 1e-6).sum())
    print('legacy-vs-raw mismatches:', mism, 'compared rows:', len(j), flush=True)
    return len(j), mism


if __name__ == '__main__':
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    df = rebuild_all(limit=limit, workers=workers)
    print('rebuilt seed rows:', len(df), flush=True)
    ok1 = verify_against_result_json(df)
    n, m = verify_against_legacy_csv(df)
    print(f'result.json consistency={ok1}  legacy overlap={n}  legacy mismatches={m}', flush=True)
