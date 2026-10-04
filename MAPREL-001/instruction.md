# Published cortical maps under a spatial null

Estimate the **signed** across-parcel Pearson association between the published
second functional-connectivity gradient (Margulies2016 fcgradient02) and the
HCP-S1200 group cortical-thickness map. Evaluate it against a declared spherical
centroid-spin null on Schaefer400/7 fsLR32k parcels.

This is a paper-motivated method application to two fixed released group maps,
not a reproduction of a named paper result. The400 parcels are locations, not
400 independent participants; rotations are null draws, not subjects. Preserve
the gradient's published sign. Either a significant or a nonsignificant result
is acceptable when supported by the data and declared calculation.

## Inputs and public method

The original maps, two spherical surfaces, atlas and documentary provenance are
already available offline under `/app/data/maprel`. Exact relative paths,
versions and SHA256 values are listed in `/app/source_manifest.json`; the copy
inside the data directory is identical. Do not fetch replacements. See
`/app/SOURCE_NOTICE.md` for citations and reuse limitations.

`/app/method_contract.json` is the public numerical contract and
`/app/output_schema.json` specifies the required evidence. In particular:

- Join the CIFTI BrainModelAxis to the full hemisphere GIFTIs using brain
  structure and original zero-based local vertex ID. Flattened array positions
  and label-number halves do not establish correspondence. Retain all400
  nonzero, nonempty, hemisphere-pure parcels. Exclude label0; do not impute or
  drop parcels based on map values.
- Compute float64 arithmetic parcel means with vertices in ascending original
  vertex order. For each spherical centroid, normalize the arithmetic coordinate
  mean to radius100. Use stored sphere coordinates without an extra transform.
- Declare `original`, `vasa` or `hungarian`, an integer seed0..4294967295 and
  100..4096 rotations. The public contract specifies the neuromaps0.0.7 seeded
  rotation/assignment conventions, coupled hemispheres, pinned tie behavior and
  capped duplicate policy. `original` may validly map multiple destinations to
  one source parcel. Do not replace rotations based on their resulting r values.
- Use one replay of the signed parcel values you submit for observed and null
  correlations. Recenter each remapped vector. Count inclusive two-sided
  exceedances from unrounded computed correlations and use `(E+1)/(N+1)`.
  Report significance strictly below0.05. No particular r, null spread, p or
  conclusion is required.
- Canonical source constants remain inactive even if serialization introduces
  tiny variation. Keep every undefined rotation as an explicit null/status;
  if any required statistic is undefined, report undefined inference rather
  than an available-case p. The contract specifies stable centering, source
  fidelity and numerical receipt tolerances.

## Deliverables

Write these five files in `/app/output`:

1. `parcels.csv`: one keyed row per parcel, including source label/network,
   hemisphere, original vertex support count/digest and both signed means.
2. `spin_evidence.npz`: explicit parcel and rotation axes, centroid/hemisphere
   receipts, and mapped **source parcel IDs** for every destination and rotation.
3. `results.json`: declared method/seed/count, observed signed r, every keyed
   null r/status, exact expected/defined/exceedance counts, numerator/denominator,
   p and significance or explicit undefined inference.
4. `run_metadata.json`: hashes of the three public contracts, closed source
   identity records, observed geometry/support facts, canonical activity,
   software versions and warnings, following the public schema.
5. `findings.md`: a concise interpretation and limitations. A conditional spin
   result does not establish a causal explanation or prove absence of a
   relationship. There are no required prose keywords or verdict direction.

### Metadata representation

The JSON field names and structure in `output_schema.json` are required.
`run_metadata.json` uses `schema_version="maprel-metadata-v2"`,
`task_id="MAPREL-001"`, and `status="ok"`; `results.json` instead uses
`schema_version="maprel-results-v2"` and `status="complete"`. The three contract
hashes are SHA-256 strings for the supplied unchanged files. `source_files`
contains every manifest record with exact relative `path`, literal `role`,
integer `size_bytes`, and SHA-256 string; record order is immaterial.

In `source_observed`, preserve the original GIFTI metadata, array intents,
shapes, coordinate systems, hemisphere declarations, and source-ordered arrays.
The atlas record requires `shape`, `label_axis_index`, `brain_model_axis_index`,
`label_map_name`, source-ordered `structures`, `excluded_zero_entries`, sorted
`label_keys`, and these three documentary fields:

- `cortical_join`: nonempty description of the brain-structure/local-vertex-ID
  join. No exact phrase, keyword, or private spelling is required.
- `sphere_coordinate_transform`: nonempty description of the sphere-coordinate
  treatment. For example, `"none"` can describe using stored pointsets directly.
- `map_support`: either a nonempty description of the nonzero cortical-label
  support, or two records keyed by `map_id` (`"gradient2"`, `"thickness"`).
  Each record requires exact integer `included_vertices`, `finite_vertices`,
  `nonfinite_vertices`, and `zero_vertices`, counted over all retained original
  support vertices for that map. Structured counts are verified against the
  original inputs; all-zero/missing/extra-map or conflicting counts do not pass.

The prose fields are documentation, not evidence that a correct join or
transform occurred. Original parcel membership, support counts/digests, signed
map means, centroids, hemisphere identities, assignments and result arithmetic
remain independently source-bound. Source-derived literal labels and original
GIFTI metadata are not free-form descriptions. `analysis_observed` must retain
the two Boolean map-activity records and integer remap-support counts specified
in the schema. `software_versions` is a nonempty string-to-nonempty-string
object for actual software; `warnings` is a list of strings, possibly empty.

Coherently reordered keyed evidence, equivalent numerical dtype spellings and
bounded harmless extra evidence are accepted as described in the schema. Full
precision parcel values are recommended; rounded r/p receipts never determine
the rank count. Do not emit a success result if a prerequisite failed: write
`failure_report.json` with the reason. Its presence invalidates success.

The verifier authenticates the original inputs, independently reconstructs
parcel geometry and measurements, regenerates your declared assignments from
canonical source geometry, then checks the arithmetic of your accepted values.
Scoring is all-or-nothing for complete valid evidence, not proportional credit.

## Method references

- Alexander-Bloch et al.2018, spherical spatial correspondence testing:
  https://doi.org/10.1016/j.neuroimage.2018.05.070
- Markello et al.2022, neuromaps and published-map comparison:
  https://doi.org/10.1038/s41592-022-01625-w
- Exact computational conventions are identified in the method contract.
