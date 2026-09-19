"""Portable final rule, checked against every frozen LOCO recommendation.

Coefficients and margins are explicit inputs, never fitted at inference time.
None denotes abstention; zero denotes no admission. A positive rate needs its
own configuration-matched test and does not certify all lower rates.
"""
import math
import numpy as np


def predict(row, method, coefficients, margin, config):
    status = row.get('q_star_status', '')
    if status in ('OUT_OF_DOMAIN_GEOMETRY', 'TECHNICAL_INVALID'):
        return None, status
    w, qp = float(row['W']), float(row['qp'])
    d, g = config['applicability_domain'], config['guardrails']
    if not (math.isfinite(w) and math.isfinite(qp) and qp > 0):
        return None, 'INSUFFICIENT_INPUT'
    typ = str(row.get('type', 'A')).upper()
    mt, ct = float(row.get('max_turn_deg', 0)), float(row.get('cum_turn_deg', 0))
    sh = g['sharp_corner_guard']
    turn = mt >= sh['max_turn_min_deg'] and ct >= sh['cum_turn_min_deg'] and (mt / ct if ct > 1e-6 else 0) >= sh['concentration_min']
    if not (d['W_range'][0] <= w <= d['W_range'][1]) or qp > d['q_p_max'] or qp/w >= g['x_crit'] or typ not in d['type_in_domain'] or (typ == 'B' and row['sinuosity'] > d['type_b_sinuosity_max']) or turn:
        return None, 'DOMAIN'
    vb, bp = row.get('vbar'), row.get('base_pass')
    if vb is None or bp is None or not math.isfinite(float(vb)) or not math.isfinite(float(bp)):
        return None, 'INSUFFICIENT_INPUT'
    if bp == 0 or vb < g['absolute_speed_floor']['vbar_min'] or qp >= np.interp(w, g['C_W']['W'], g['C_W']['C']):
        return 0., 'SERVICE'
    c = coefficients
    if method in ('M0', 'M1'):
        nominal = np.exp(c[0]) * w * (qp/w)**c[1]
    elif method == 'M2':
        nominal = np.exp(c[0]) * w**c[1]
    elif method == 'M3':
        nominal = np.exp(c[0]) * w**c[1] * qp**c[2]
    else:
        raise ValueError('Expected M0, M1, M2 or M3')
    rate = float(math.floor(min(g['q_max'], np.interp(w, g['Q_low']['W'], g['Q_low']['Q']), max(0., nominal-margin))))
    return rate, 'ADMITTED' if rate > 0 else 'MARGIN_FLOOR'


def seed_pass(frame, baseline_mean, service):
    ratio = frame.outflow_ped / frame.inflow_ped.replace(0, np.nan)
    return (frame.inflow_ped.gt(0) & (frame.mean_speed / baseline_mean).ge(service['speed_retention'])
            & frame.mean_density.le(service['density_limit'])
            & ratio.between(service['throughput_low'], service['throughput_high']))
