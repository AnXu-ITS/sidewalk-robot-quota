# -*- coding: utf-8 -*-
"""
run_all_analysis.py — one-command post-scan analysis chain (run AFTER the
main 280-combo and decoupled 120-combo scans AND boundary refinement):

  1. consolidate_reference --kind main      -> main_280_reference_table.csv
  2. consolidate_reference --kind decoupled -> decoupled_120_reference_table.csv
  3. refine_boundary --run                  -> refined_quota_reference_table.csv
  4. merge_datasets --refined ...           -> full_reference_dataset.csv
  5. fit_models (D1 = main only; D2 = full) -> candidate_model_parameters.csv,
     loco_city_results.csv, residual_diagnostics.csv/.json,
     identifiability_comparison.csv, formula_selection_table.csv
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CELLS = os.path.join(HERE, "cells")
OUT = os.path.join(HERE, "final_analysis")
SIM_OUT = os.path.join(HERE, "sim", "outputs")


def run(cmd, cwd=HERE):
    print("$", " ".join(cmd), flush=True)
    r = subprocess.run([sys.executable] + cmd, cwd=cwd)
    if r.returncode != 0:
        raise SystemExit(f"step failed: {cmd}")


def main():
    os.makedirs(OUT, exist_ok=True)
    run(["consolidate_reference.py", "--kind", "main"])
    run(["consolidate_reference.py", "--kind", "decoupled"])

    refined = os.path.join(SIM_OUT, "refinement",
                           "refined_quota_reference_table.csv")
    if not os.path.exists(refined):
        print("refined table not found -> run refine_boundary --run")
        run(["refine_boundary.py", "--run"])
    run(["merge_datasets.py", "--refined", refined])

    full = os.path.join(CELLS, "full_reference_dataset.csv")
    main = os.path.join(CELLS, "main_280_reference_table.csv")
    # (a) fit on D1=280, identifiability compares D1 vs D2=280+120
    run(["fit_models.py", "--ref", main, "--ref2", full,
         "--outdir", os.path.join(OUT, "d1_main")])
    # (b) fit + LOCO + selection on D2=full (decoupled included)
    run(["fit_models.py", "--ref", full, "--ref2", full,
         "--outdir", os.path.join(OUT, "d2_full")])
    print("\nALL ANALYSIS DONE ->", OUT)


if __name__ == "__main__":
    main()
