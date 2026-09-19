# Reproduction

Run from repository root. Python 3.10+; publication checks used Python 3.14. Install requirements.txt. Tested versions are recorded in VALIDATION_ENVIRONMENT.json.

## Final analysis without simulation

`python scripts/verify_results.py`

Recomputes per-fold candidate predictions and abstention reasons, checks matching primary baseline means, recomputes seed decisions and development/Hong Kong outcomes, utilization, error and paired access subsets. CSV summaries and verification.json go to outputs/. No reference fitting or SUMO execution occurs. Archived legacy flow_ratio is ignored: undefined throughput fails.

`python -m unittest discover -s tests` checks undefined denominators, exclusions and the 29/30 boundary.

## Figures and manuscript

`python scripts/build_figures_v2.py` writes three figures to outputs/figures/. The historical v2 filename is retained, but the input is the final submission data. Arial is the reference font. Regeneration does not overwrite submitted artifacts.

`python scripts/build_paper.py` copies source to outputs/paper/ and runs pdflatex, bibtex and two further pdflatex passes. Required packages are those in paper/ascexmpl-new.tex, including newtxtext/newtxmath, caption, amsmath, booktabs, microtype, needspace, placeins and hyperref. The ASCE class/style are included. PDF metadata can differ by TeX environment; the committed 12-page PDF is the submitted snapshot.

## Inspect or rerun one simulation

`python scripts/run_simulation.py --index 0 --seed 0 --inspect`

This prints one of 467 preserved baseline/positive-flow specifications. Select by dataset, tag, entrance configuration and robot flow in configs/run_specs.json. Source hashes are preserved.

Only explicit `--run` executes the engine. Install SUMO **1.27.1 with JuPedSim** and netconvert; set SUMO_HOME or PATH. Run `python scripts/run_simulation.py --index INDEX --seed SEED --run`. The wrapper keeps inputs, XML, stdout/stderr, exit status and hashes under outputs/runs/ and refuses to overwrite an existing run directory. It uses the original backend but returns undefined throughput for zero denominators.

The publication cleanup tested inspection and lightweight reproduction, not a fresh simulation. A single seed is not a recommendation test: complete matching baseline and flow groups are required. New runs never update the submitted reference or predictions automatically.

## Code lineage and limitations

src/sidewalk_admission/model.py is the portable final inference/service layer, regression-checked against all 1,600 recommendations. code/simulation/ preserves the original backend, including legacy parsing behavior; use the final service layer for scoring. code/provenance/ retains original scripts with historical workspace dependencies, not the quick-start entry point.

Full scan/reference reconstruction requires the retained original raw-run archive and provenance-script dependencies. It is not claimed to be self-contained in this lightweight Git release. SOURCE_MANIFEST.json maps copied source artifacts; PUBLICATION_SHA256.csv records published scientific files. Existing hashes and archive evidence are retained. Historical absolute paths in audit records are provenance, not required runtime configuration.
