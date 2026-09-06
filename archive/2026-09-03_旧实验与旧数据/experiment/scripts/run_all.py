"""
run_all.py
==========
End-to-end orchestrator for the sidewalk robot-quota experiment.

    python run_all.py [--n-procs N]

Stages (each writes real outputs to disk):
  1. ground_truth.py  -> baseline + robot sweep -> reference quota dataset
  2. fit_quota.py     -> Model A / B / A-iso fitted to the quota dataset
  3. validate.py      -> held-out prediction error + closed-loop SVR
  4. sensitivity.py   -> threshold + robot-speed sensitivity
  5. figures.py       -> paper figures + policy table
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-procs", type=int, default=None)
    ap.add_argument("--skip-ground-truth", action="store_true")
    args = ap.parse_args()
    np_ = args.n_procs

    if not args.skip_ground_truth:
        import ground_truth
        ground_truth.main(n_procs=np_)

    import fit_quota
    fit_quota.fit_and_save()

    import validate
    validate.main(n_procs=np_)

    import closed_loop_safe
    closed_loop_safe.main(n_procs=np_)

    import sensitivity
    sensitivity.rederive_thresholds()
    sensitivity.robot_speed_sensitivity(n_procs=np_)

    import figures
    figures.main()

    import calibration
    calibration.main()

    import report
    report.main()

    print("\n=== experiment pipeline complete ===")


if __name__ == "__main__":
    main()
