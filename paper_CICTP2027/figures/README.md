# Complete Hong Kong geometry record

[All 18 configurations at a shared metric scale](hong_kong_all18_metric.pdf)
retain the complete original/repaired comparison. SVG, PNG and 600 dpi TIFF
exports are supplied alongside the PDF. The figure's provenance JSON records
input hashes, exact coordinates, display translations and marker meanings.
Shapes receive no individual scale change or additional rotation. Existing
local GIS coordinate preprocessing is retained; this is not a north-up map.

The manuscript shows **eight examples**, selected solely from geometry and
configuration metadata. The [selection CSV](HK_REPRESENTATIVE_SELECTION.csv)
records one objective reason per selected case:

| Group | Rule, applied sequentially to remaining candidates | Selected site |
|---|---|---|
| Original | Narrowest representative input width | HK-ST-06 |
| Original | Lowest centreline sinuosity | HK-ST-15 |
| Original | Widest representative input width | HK-ST-25 |
| Original | Lowest polygon rectangular fill | HK-ST-28 |
| Repaired | Narrowest representative input width | HK-ST-05 |
| Repaired | Highest centreline sinuosity | HK-ST-16 |
| Repaired | Lowest polygon rectangular fill | HK-ST-22 |
| Repaired | Largest sum of endpoint-to-anchor displacements | HK-ST-24 |

Ties use ascending site identifiers. Selection does not read reference flow,
candidate flow or service outcome. The visual subset does not change the
analysis population: all reported Hong Kong totals still use 18 configurations.
In particular, the single original M1 failure at HK-ST-08 remains in the complete
figure, dataset and manuscript aggregate results even though that site is not
selected by these geometric rules.

Regenerate both figures and the CC0 scene from the archived inputs:

```bash
python paper_CICTP2027/scripts/build_visual_revision.py
```

The command writes to `paper_CICTP2027/outputs/visual_revision/` and leaves
archived inputs, figures and raw evidence intact. Run it from the repository
root, or use `python scripts/build_visual_revision.py` inside the package.
