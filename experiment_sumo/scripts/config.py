"""
config.py  (SUMO-JuPedSim edition)
==================================
Global parameters for the sidewalk delivery-robot quota experiment, re-run with
Eclipse SUMO + JuPedSim instead of the Python social-force model.

The experimental design (widths, pedestrian demands, robot-flow sweep,
pedestrian-first service constraints, seeds) is kept IDENTICAL to the original
Python experiment so the two backends can be compared directly.  Only the
simulation engine differs: this edition shells out to `sumo` with
`--pedestrian.model jupedsim`.

Physical grounding (unchanged):
  * Pedestrian free-flow walking speed ~1.25 m/s (Singapore, Tanaboriboon 1986)
  * Pedestrian body radius ~0.25 m
  * Reference delivery robot: Camello-equivalent Singapore delivery robot,
    footprint L_r = 0.96 m x W_r = 0.70 m, fixed 5 km/h (1.39 m/s), below the
    6 km/h regulatory cap (Singapore S 374/2026 Bendemeer exemption).  The robot
    is NOT a "special pedestrian": it carries a real anisotropic footprint whose
    JuPedSim collision-disc area is ~3.7x the pedestrian's (0.724 vs 0.196 m^2).
  * Effective sidewalk widths 1.5 - 3.0 m
"""

import os

# ---------------------------------------------------------------------------
# SUMO toolchain
# ---------------------------------------------------------------------------
SUMO_HOME = os.environ.get("SUMO_HOME", r"C:\Users\xuan1\sumo")
SUMO_BIN = os.path.join(SUMO_HOME, "bin", "sumo.exe")
NETCONVERT_BIN = os.path.join(SUMO_HOME, "bin", "netconvert.exe")

# ---------------------------------------------------------------------------
# Pedestrian model parameters (mapped to SUMO vType + JuPedSim)
# ---------------------------------------------------------------------------
PED = dict(
    radius=0.25,          # m  -> JuPedSim radius = max(length,width)/2
    length=0.50,          # m  -> gives radius 0.25
    width=0.50,           # m
    v0_mean=1.25,         # m/s free-flow desired speed (Singapore)
    v0_std=0.15,          # m/s
    v0_min=0.8,           # m/s
    v0_max=1.8,           # m/s
)

# Wall repulsion is handled by JuPedSim's geometry; kept for API compatibility.
WALL = dict(A=300.0, B=0.20, k_contact=2000.0, kappa=400.0)

# ---------------------------------------------------------------------------
# Reference delivery robot (Camello-equivalent Singapore delivery robot)
# ---------------------------------------------------------------------------
# The robot is modeled with its REAL anisotropic footprint (length along the
# travel direction, width across it), not a hard disc.  JuPedSim's
# CollisionFreeSpeedModel reduces a pedestrian to a scalar collision radius;
# SUMO maps the vType shape to radius = max(length, width) / 2, so the robot's
# dominant half-length (0.48 m) is what pedestrians feel -- ~1.9x the
# pedestrian's 0.25 m radius and ~3.7x its plan area.
ROBOT = dict(
    length=0.96,          # m  Camello length along travel direction
    width=0.70,           # m  Camello width across travel direction
    radius=0.48,          # m  JuPedSim collision radius = length / 2 (dominant)
    v_ref=1.39,           # m/s = 5.0 km/h
)

# JuPedSim's CollisionFreeSpeedModel achieves ~0.914x of the vType maxSpeed in
# free flow (measured empirically).  This multiplier compensates so the achieved
# free-flow speed matches the target (~1.25 m/s pedestrians, ~1.39 m/s robot).
SPEED_CALIB = 1.094

# ---------------------------------------------------------------------------
# Simulation / scenario
# ---------------------------------------------------------------------------
SIM = dict(
    dt=0.1,               # s  SUMO step length (JuPedSim sub-steps internally)
    L=50.0,               # m corridor (cell) length
    warmup=100.0,         # s discarded transient
    measure=240.0,        # s steady-state measurement window
    tail=100.0,           # s extra sim time AFTER the flow ends so every person
                          #    who departs inside the measurement window finishes
                          #    and appears in personinfo (no write-unfinished for
                          #    personinfo exists).  Not part of the metrics.
    measure_zone=(15.0, 35.0),   # x range (m) for speed / density sampling
    bidirectional_split=0.5,     # fraction of pedestrian demand in -x direction
)

# ---------------------------------------------------------------------------
# Pedestrian-first service constraints (base scenario)
# ---------------------------------------------------------------------------
CONSTRAINTS = dict(
    delta_v=0.10,             # speed retention floor R_v >= 1 - delta_v
    outflow_ratio_min=0.90,   # q_p,out / q_p,in floor (throughput collapse)
    outflow_ratio_max=1.20,   # q_p,out / q_p,in ceiling (spawn-blocking jam;
                              #   SUMO blocks spawns when a corridor is at
                              #   capacity, so flow_ratio >> 1 signals
                              #   over-capacity -- the SUMO analogue of the
                              #   original social-force throughput collapse)
    density_floor=1.20,       # ped/m^2 LOS floor
    conf_level=0.95,          # Pr(C_p = 1) >= 0.95
)

# ---------------------------------------------------------------------------
# Experimental design (identical to the original experiment)
# ---------------------------------------------------------------------------
# 1.6 / 1.7 m were added (P0) to resolve the W_min cliff between the blocked
# 1.5 m corridor and the operable 1.8 m corridor with real simulation data.
WIDTHS_TRAIN = [1.5, 1.6, 1.7, 1.8, 2.1, 2.4, 2.7, 3.0]
# New widths added in the P0 incremental pass (not present in the original
# baseline/sweep CSVs); extend_experiment.py runs their baseline + sweep.
NARROW_WIDTHS = [1.6, 1.7]
PED_FLOWS_TRAIN = [10, 20, 30, 40, 50, 60]
ROBOT_FLOWS = [0, 1, 2, 3, 4, 5, 6, 8, 10]
# Extended robot-flow levels for ceiling resolution (P0): the base sweep tops
# out at 10 robot/min, which leaves wide / light cells un-resolved ("at least
# 10").  extend_experiment.py runs these levels only for cells that saturated
# at the base ceiling.
ROBOT_FLOWS_EXTENDED = [12, 15, 18, 20]
# Union of base + extended levels, used by the aggregation / fit / validation.
ROBOT_FLOWS_ALL = ROBOT_FLOWS + ROBOT_FLOWS_EXTENDED

WIDTHS_TEST = [1.65, 1.95, 2.25, 2.55, 2.85]
PED_FLOWS_TEST = [12, 18, 22, 27, 35, 45, 55]

N_SEEDS_SWEEP = 30
N_SEEDS_BASELINE = 30
N_SEEDS_VALIDATION = 30

DELTA_V_LEVELS = [0.05, 0.10, 0.15]
ROBOT_SPEED_FACTORS = [0.8, 1.0, 1.2]

# ---------------------------------------------------------------------------
# Paths (relative to the experiment root)
# ---------------------------------------------------------------------------
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
    tmp=os.environ.get("SUMO_TMP", os.path.join(ROOT, "outputs", "sumo_tmp")),
)
