"""
config.py
=========
Global parameters for the sidewalk delivery-robot quota experiment.

All physical values are grounded in published references and the experiment
plan document:

  * Pedestrian free-flow walking speed ~1.25 m/s
      - Tanaboriboon, Hwa & Chor (1986) "Pedestrian Characteristics Study in
        Singapore" reports mean free walking speed ~1.2 m/s for Singapore.
      - We calibrate the desired-speed distribution mean to 1.25 m/s.
  * Pedestrian body radius ~0.25 m (Singapore adult body ellipse minor axis).
  * Reference delivery robot: an AIDEN-style sidewalk robot with a footprint
    of roughly 0.55 m (w) x 0.9 m (l); we model it as a hard disc of radius
    0.40 m (a conservative area-equivalent proxy).  Programmed speed is fixed
    at 5 km/h (1.39 m/s), below the 6 km/h regulatory cap cited in the plan
    (Singapore S 374/2026 exemption).
  * Effective sidewalk widths span 1.5 - 3.0 m, the typical clear-footpath
    range used in Singapore design guidance.

The simulation is a microscopic 2-D social-force model (Helbing & Molnar
1995) for pedestrians, with a fixed reference robot acting as a moving
"traffic-capacity proxy" (fixed lane + longitudinal collision-free speed
control).  See simulator.py for the dynamics.
"""

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Pedestrian model (social force, Helbing & Molnar 1995)
# ---------------------------------------------------------------------------
PED = dict(
    radius=0.25,          # m, body radius
    mass=80.0,            # kg
    v0_mean=1.25,         # m/s, free-flow desired speed (Singapore)
    v0_std=0.15,          # m/s
    v0_min=0.8,           # m/s
    v0_max=1.8,           # m/s
    tau=0.5,              # s, relaxation time (driving force)
    A=300.0,              # N, social-force strength (soft, dt-robust)
    B=0.30,               # m, social-force range
    lam=0.5,              # anisotropy (react less to agents behind)
    k_contact=2000.0,     # N/m, contact stiffness on overlap (soft)
    kappa=400.0,          # kg/s, contact damping
    v_max=2.0,            # m/s, hard speed cap
    a_max=6.0,            # m/s^2, acceleration cap for stability
)

# ---------------------------------------------------------------------------
# Wall / boundary interaction
# ---------------------------------------------------------------------------
WALL = dict(
    A=300.0,              # N
    B=0.20,               # m
    k_contact=2000.0,     # N/m
    kappa=400.0,
)

# ---------------------------------------------------------------------------
# Reference delivery robot
# ---------------------------------------------------------------------------
ROBOT = dict(
    radius=0.30,          # m, hard-disc proxy of ~0.55 x 0.9 m footprint (width)
    mass=60.0,            # kg (unused in lane model but documented)
    v_ref=1.39,           # m/s = 5.0 km/h (below 6 km/h regulatory cap)
    tau=0.25,             # s, longitudinal relaxation
    lane_frac=0.5,        # default lane centre as fraction of width (centreline)
    d_stop=0.6,           # m, headway at which robot comes to a full stop
    d_follow=1.5,         # m, headway at which robot matches leader speed
    d_yield=1.5,          # m, headway at which robot steps laterally aside
    v_creep=0.25,         # m/s, creep speed when a pedestrian is in its path
    yield_frac=0.30,      # fraction of width the robot shifts to open a gap
    tau_lat=0.3,          # s, lateral relaxation
    lookahead=2.5,        # m, search radius ahead for collision-free control
    A=600.0,              # N, repulsion strength that pedestrians feel from robot
    B=0.25,               # m, repulsion range for the robot
)

# ---------------------------------------------------------------------------
# Simulation / scenario
# ---------------------------------------------------------------------------
SIM = dict(
    dt=0.1,               # s
    L=50.0,               # m, corridor (cell) length
    warmup=100.0,         # s, discarded transient
    measure=240.0,        # s, steady-state measurement window
    measure_zone=(15.0, 35.0),  # x range (m) for speed / density sampling
    bidirectional_split=0.5,    # fraction of pedestrian demand in -x direction
)

# ---------------------------------------------------------------------------
# Pedestrian-first service constraints (base scenario)
# ---------------------------------------------------------------------------
CONSTRAINTS = dict(
    delta_v=0.10,         # speed retention floor: R_v >= 1 - delta_v
    outflow_ratio_min=0.90,   # q_p,out / q_p,in floor (flow stability)
    density_floor=1.20,   # ped/m^2, LOS / density absolute floor
    conf_level=0.95,      # Pr(C_p = 1) >= 0.95 for a flow to be admissible
)

# ---------------------------------------------------------------------------
# Experimental design
# ---------------------------------------------------------------------------
# Type-A training cells: straight, locally homogeneous widths (m).
WIDTHS_TRAIN = [1.5, 1.8, 2.1, 2.4, 2.7, 3.0]
# Pedestrian demand levels (ped/min, bidirectional total).
PED_FLOWS_TRAIN = [10, 20, 30, 40, 50, 60]
# Robot flow sweep levels (robot/min); q_r=0 is the pedestrian-only baseline.
# Upper level 10 robot/min = 600 robot/h is already well above typical fleet
# densities; higher levels only add slow, deep-jam scenarios without changing
# the quota (they all fail).
ROBOT_FLOWS = [0, 1, 2, 3, 4, 5, 6, 8, 10]

# Held-out cells: unseen effective widths (m) representing different real
# Singapore footpath sections not used in fitting.
WIDTHS_TEST = [1.65, 1.95, 2.25, 2.55, 2.85]
PED_FLOWS_TEST = [12, 18, 22, 27, 35, 45, 55]

# Number of random seeds per (q_p, W, q_r) combination.
N_SEEDS_SWEEP = 30
N_SEEDS_BASELINE = 30
N_SEEDS_VALIDATION = 30

# Threshold sensitivity: speed-retention floors to compare.
DELTA_V_LEVELS = [0.05, 0.10, 0.15]

# Robot speed sensitivity: v_ref * [0.8, 1.0, 1.2].
ROBOT_SPEED_FACTORS = [0.8, 1.0, 1.2]

# ---------------------------------------------------------------------------
# Paths (relative to the experiment root; overridable)
# ---------------------------------------------------------------------------
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATHS = dict(
    root=ROOT,
    geometry=os.path.join(ROOT, "data", "geometry"),
    processed=os.path.join(ROOT, "data", "processed"),
    baseline=os.path.join(ROOT, "outputs", "baseline"),
    sweeps=os.path.join(ROOT, "outputs", "sweeps"),
    quota_labels=os.path.join(ROOT, "outputs", "quota_labels"),
    validation=os.path.join(ROOT, "outputs", "validation"),
    sensitivity=os.path.join(ROOT, "outputs", "sensitivity"),
    figures=os.path.join(ROOT, "outputs", "figures"),
    models=os.path.join(ROOT, "models", "quota_algorithm"),
    reports=os.path.join(ROOT, "reports"),
)
