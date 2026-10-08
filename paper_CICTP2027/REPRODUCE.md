# Reproduce the CICTP research version

Python 3.10+ with NumPy, pandas, matplotlib and PyMuPDF. Local validation used
Python 3.14.7, NumPy 2.5.2, pandas 3.0.5, matplotlib 3.11.1 and PyMuPDF 1.28.2.
The workflow uses relative paths and requires no author's Windows directory.

## Archived-data reproduction

From repository root:

```bash
python -m pip install -r paper_CICTP2027/requirements.txt
python -B paper_CICTP2027/scripts/reproduce.py
python -B paper_CICTP2027/scripts/build_assets.py
```

`outputs/reproduced/` contains `main_comparison.csv`, `margin_sweep.csv`,
`margin_by_city.csv`, `margin_candidates.csv`, `margin_parameters.csv`,
`replication_summary.csv`, full replication conditions and matched baseline/mixed
seed evidence, `failure_decomposition.csv`, `hong_kong_summary.csv`,
`demand_summary.csv`, `guardrail_reconstruction.csv` and `integrity.json`.

The script refits the six-city width–demand model and all five prespecified
margins, then scores exact candidate tests from real archived seed metrics. It
checks the original four-method outcomes, frozen endpoints, independent matching
baselines, replication freeze hash, all 18 failure groups, Hong Kong strata and
synthetic guardrails. It does not augment frozen q* with selective new flows.

`outputs/assets/` contains the compact paper tables, exact generated macros and
Figure2 in PDF/SVG/PNG. All five points come from the reproduced table. Figure1
and Figure3 are retained vector assets in the manuscript project; Figure3 uses
actual stored Hong Kong geometries. Arial is preferred for production figures,
with Helvetica/DejaVu Sans fallback; a missing font can change typography without
changing numerical results. Point counts are descriptive, not confidence bounds
on population risk.

## Manuscript

```bash
python -B paper_CICTP2027/scripts/build_manuscript.py
```

This requires pdfLaTeX and BibTeX with the provided ASCE class/style and standard
packages used in the source. The compiled copy and logs go to
`outputs/manuscript/`; archived manuscript files stay intact. The `manuscript/`
folder is also directly usable in Overleaf with `ascexmpl-new.tex` as the main file.

## Explicit simulation reruns

Simulation execution is optional and requires **SUMO 1.27.1 with JuPedSim** and
`netconvert`, found through PATH or SUMO_HOME. Inspect a preserved template first:

```bash
python -B paper_CICTP2027/scripts/run_exact_test.py --index 0 --flow 1 --block independent --group --with-baseline --inspect
```

Only an explicit `--run` launches the engine:

```bash
python -B paper_CICTP2027/scripts/run_exact_test.py --index 0 --flow 1 --block independent --group --with-baseline --run
```

This tests one scenario at flow 1 with seeds 10000–10029 and a matching independent
baseline. `--block original` uses 0–29. Select the desired scenario/entrance in
`configs/run_specs.json`; `--flow` specifies an exact integer within 0–20. The
published extension queue records the original 64 missing groups/1,920 jobs.
Never retune candidates to new seed outcomes.

The runner preserves generated geometry/routes/configuration, personinfo/FCD,
stdout/error logs, status and hashes. It refuses to overwrite interrupted runs,
checks completed caches and distinguishes technical failure from completed adverse
service. A PASS/FAIL group label requires a complete matching 30-seed baseline and
candidate. No substitute seeds are used. The rerun interface was tested in
inspection mode only during this manuscript/publication phase; no new scientific
simulation was executed. The original 1,920 extension runs are represented by
their actual scalar outcomes and frozen job specifications.

The templates support preserved configuration-specific groups. This is not a
claim that every older scan can be reconstructed from raw XML: most original XML
was deleted during an earlier author-directed cleanup. Its archived derived
metrics remain available. Full exact insertion history is not recoverable from
first-observation counts, even when service metrics can be reproduced.
