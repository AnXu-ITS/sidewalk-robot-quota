# Local cleanup — 19 September 2026

Publication succeeded before cleanup. Of 37 explicitly reviewed cache/build targets, 30 were removed completely. Removed file content totals 73.85 MB; 7.52 MB remains in seven partially cleaned or protected targets. See CLEANUP_RECEIPT.csv for each path, outcome and remaining bytes.

Read-only OneDrive directories blocked ordinary removal. Automatic approval review rejected forced recursive removal with the reason “blocked by policy”; no further attempt to override that restriction was made. Cleanup is therefore partial, not marked fully complete.

Only reproducible LaTeX outputs, rendered page images, Python bytecode and disposable verification copies were targeted. Raw simulation logs, frozen configurations, original research source, GIS evidence, Git histories and final paper were preserved. All published file hashes were rechecked after cleanup; the original final PDF remains byte-identical to the published PDF.

Old research directories were removed from the GitHub current tree (retained in Git history and locally), not physically deleted as if they were caches.

## Final size reduction

At the author's direction after the initial cleanup, the complete local run archive `revision_review/runs` (111.4 GB) was deleted. The redundant packaged raw-log archive `revision_review/deliverables/sidewalk_new_raw_logs.zip` (4.62 GB), the old `train_test_mapdata` directory (544 MB), and obsolete local analysis/figure archives were also removed. The full pre-publication Git history was moved outside the project directory; the project now uses a shallow clone of the published GitHub commit.

The final project directory measures approximately 452.2 MB (0.442 GB). The final PDF remains byte-identical to `paper/ascexmpl-new.pdf`; published submission data and lightweight verification inputs remain present. The deleted run archive and packaged raw logs are not recoverable from this project directory.
