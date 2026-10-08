# CC0 scene, continuous service definition and representative geometry revision

Presentation update, 8 October 2026. **No new experiments or scientific retuning.**
All earlier experimental datasets, configurations, seed decisions and parameter
versions remain unchanged. The immutable cictp2027-v1.0.0 release is preserved.

## Exact changes

- Figure 1 uses the supplied 1280-by-1280 rendition of the Moscow Yandex scene.
  Its author, Retired electrician, and CC0 1.0 license were verified on the
  [Wikimedia Commons file page](https://commons.wikimedia.org/wiki/File:Moscow,_Yandex_employee_walking_his_pet_A-505_robot,_Aug_2025_04.jpg).
  The caption links both the source and the license. The original JPEG stream is
  embedded without pixel modification or resampling. Two side callouts use
  separate native PDF vector text, rounded boxes, leader lines and target rings.
  Text remains selectable/editable; SVG also retains text elements. This is
  illustrative photography, not evidence validating the simulated robot.
- Figure 2 now follows the complete service-definition and reference-flow
  paragraphs. Controlled inline placement anchors it at this paragraph boundary.
  The entire sentence “A zero denominator is undefined and fails the flow
  component.” appears continuously on page 4, before the diagram. The sentence
  is not forced into an oversized unbreakable box. All service definitions and
  scientific rules are unchanged.
- Figure 4 displays eight configurations rather than eighteen. Selection is
  deterministic and uses geometric inputs and entrance-repair displacement only;
  it does not inspect candidate flows, references or service outcomes.
  Four original cases illustrate narrow width, straightness, widest width and
  lowest rectangular fill. Four repaired cases illustrate narrow width, highest
  sinuosity, lowest rectangular fill and greatest entrance-anchor displacement.
  The [selection table](../figures/HK_REPRESENTATIVE_SELECTION.csv) records all
  eight reasons. Its display height is 262.8 pt instead of the complete figure's
  493.2 pt, with the same readable text sizes and a common metric scale within
  each figure.
- The [complete eighteen-configuration figure](../figures/hong_kong_all18_metric.pdf),
  its vector/raster formats, all input hashes and exact display coordinates are
  retained separately in the public package. The original M1 failure at HK-ST-08
  remains visible there and in the complete results. The eight-case illustration
  is not used to calculate or reinterpret any reported total.
- The local and public current manuscripts also retain the preceding literature
  comparison and compact bounded-rate notation. The page count remains eleven,
  with four figures, three tables, a 184-word abstract and five keywords.

## Validation

- Clean portable-source pdfLaTeX/BibTeX build succeeds from a separate directory.
  No undefined references/citations, overfull boxes or off-page text are present.
- Automated page-text assertions verify the whole service sentence on one page
  and before Figure 2. Final rendered pages were inspected for interrupted prose,
  figure/table order, caption clarity and spacing.
- The embedded JPEG extracted from the scene PDF has exactly the same SHA-256
  as the supplied source file. All added labels are native text/vector objects.
- All 130 captured frozen scientific files, including public scalar evidence,
  configuration and inference sources, retain their before-edit SHA-256 hashes.
  No simulator was launched. The earlier locally archived raw run directories
  were not opened for writing or replaced.
- Both geometry exports assert complete scenario identifiers, exact input
  matching, representative widths, configuration-dependent marker coordinates,
  unique selection and equal rendered x/y metre scales. All 18 configurations
  and all 72 method rows remain in the source dataset. Only the visual subset
  changes; all reported aggregate Hong Kong results still use eighteen cases.
- Native Python static preflight has no blocking failures. The 146 mm width
  advisory is resolved by this ASCE template's actual text width. Scene and
  geometry collision audits pass with zero failures or warnings. Minimum
  vector glyph sizes are 8.4 pt for the scene and 7.5 pt for geometry figures.
  The photo's JPEG compression filter is outside the text auditor's filter
  vocabulary; this affects no native text checks and was verified by extraction
  and visual inspection.
- The publication package validator checks scene credit, subset disclosure,
  complete figure counts, preserved scientific versions and exact direct-test
  evidence, as well as private-path/credential and page-boundary checks.

## Reproduction

```bash
python paper_CICTP2027/scripts/build_visual_revision.py
python paper_CICTP2027/scripts/build_manuscript.py
python paper_CICTP2027/scripts/validate_package.py
```

Generated outputs are written to ignored output directories. Archived inputs,
historical presentation assets and the v1.0.0 release are not overwritten.
