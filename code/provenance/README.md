# Original research implementation

These scripts retain the historical workspace layout and document how the original experiments and revisions were implemented. They are not the portable entry point. Use scripts/verify_results.py for current result verification and scripts/run_simulation.py for a selected preserved run specification.

Do not execute an earlier runner to overwrite final references or recommendations. In particular, archived parser behavior assigning one to zero throughput denominators is superseded by the final explicit undefined/failing rule. See docs/RESEARCH_EVOLUTION.md.
