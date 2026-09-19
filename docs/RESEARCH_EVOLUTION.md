# Research purpose and evolution

The submitted question is a configuration-specific candidate robot entry rate, evaluated together with pedestrian service and applicability. Permission/fleet limits and segment flow are different decisions. This is offline assessment, not feedback control or a certified capacity interval.

| Stage | Change | Current interpretation |
|---|---|---|
| Early experiments, through GitHub `efc05fe` | Synthetic guardrails, seven-city geometry/demand sample, initial formula, Hong Kong transfer | Historical results and parameters are superseded |
| Raw reconstruction / VERIFIED_V2 | Preserved raw evidence, explicit exclusions and direct-flow tests | Complete logs did not itself establish correct aggregation |
| Primary-block review, Overleaf `c07bb75` | Seeds 0–29 separated from independent 10000–10029; zero throughput denominator undefined/failing; five reference labels changed; calibration and downstream results regenerated | Final reference/fit lineage; do not mix with original VERIFIED_V2 numbers |
| Narrative consolidation, `791aa30` | Access–service–coverage story, 64 evaluated cells, paired access opportunities, separate Hong Kong configurations | No superiority/equivalence claim |
| Final completion, `b0c9264`, 17 September 2026 | Six groups / 180 seeds; another group reused existing logs; all positives tested | Final references, fits, margins and recommendations unchanged |
| GitHub publication, 19 September 2026 | Curated structure, portable verification, documentation and cache cleanup | No new simulation or scientific change; submitted PDF copied byte-for-byte |

Overleaf hashes refer to the manuscript repository, not commits in this GitHub history. The previous GitHub tree remains accessible at `efc05fe`.

## Retired claims and practices

- Universal maximum flow or guarantees for every lower rate.
- Formula superiority, or equivalence inferred from small/non-significant differences.
- Zero admission counted as PASS; reference exceedance treated as actual failure.
- Replication seeds pooled into primary references and calibration.
- Zero completed-departure denominator imputed to one.
- Preserved polygons interpreted as unchanged entrances or field validation.

## Supported conclusion

A margin changes offered rates and which scenarios receive access. Removing it recovers many passing opportunities while introducing more failed recommendations. Estimator choice matters, but the margin has the larger aggregate effect in this experiment. Entrance configuration, robot size and directional composition constrain transfer. Boundary seed-block differences do not establish truly nonmonotonic population pass probability.

Numeric authority: `data/submission/FINAL_RESULTS.json`. Files under `docs/audits/history/` are prior-stage records, not current result tables.
