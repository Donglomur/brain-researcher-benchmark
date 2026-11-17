# Reconstruct four processed-release spine associations

Task ID: `PAPER-FIND-REP-012`. Finite `spec_data` result-artifact component.

The scientific context is Wright, Hedrick and Komiyama, *Science* (2025),
DOI `10.1126/science.ads4706`: associations of local synaptic coactivity and
dendrite-coincident activity with subsequent spine structural change during
early learning. Reconstruct the four declared processed-release calculations.

| Endpoint | Panel | Predictor | Compartment |
| --- | --- | --- | --- |
| `apical_local` | 2F | `distance_coactivity_rate_norm_row0` | Apical |
| `basal_local` | 2M | `distance_coactivity_rate_norm_row0` | Basal |
| `apical_coincident` | 3B | `dendrite_coincident_rate_norm` | Apical |
| `basal_coincident` | 3H | `dendrite_coincident_rate_norm` | Basal |

The operator supplies the frozen processed packet as `/public/input_manifest.json`
and `/public/data.npz` inside its separately controlled candidate environment.
Those paths describe the scientific input convention, not files distributed by
this source component. The manifest identifies the archive and its source rows.
Hash its exact bytes for `input_manifest_sha256`.

Use the full supplied member/row population, typed eligibility flags, endpoint
specific NaN pairing and declared dtype conventions in
`RECONSTRUCTION_ASSUMPTIONS.md`. The outcome is follow-up structural measurement
divided by baseline. Do not tune exclusions to the publication captions.

Write one finished `result.json` conforming to `OUTPUT_SCHEMA.json`, with
`schema_version=1`, `task_id="PAPER-FIND-REP-012"` and
`analysis_id="released_source_four_pooled_pearson_v1"`. All four endpoints must
occur exactly once. Each reported endpoint contains Pearson r, nominal
two-sided p, paired-outcome mean and population SD, four counts and two support
digests. Include the five raw-cohort fields. Derive identities and counts from
the supplied packet; do not copy descriptive paper counts.

If a declared statistic is undefined, use the explicit abstention form with a
reason and null result. Omission is invalid. Denominators remain fixed at
16 numeric fields, 24 support checks and five cohort checks. Larger correlations
and smaller p values receive no improvement reward. The evaluator only reads
finished JSON; it does not run or certify the analysis program.

This target is the selected **Version 2 Zenodo data/code release**, not a caption
matching task. Its relationship to manuscript-linked Version 1 remains unresolved,
as do three reconstructed-versus-caption p-value discrepancies. Version numbers
refer to Zenodo releases. Do not attribute the discrepancy to versioning without
evidence. Full supplementary Methods access is not supplied by this component.

Pooled-spine correlations ignore within-animal and within-dendrite dependence
for inferential purposes. Their p values reproduce nominal source statistics;
they do not establish animal-population significance. Outcome moments and row
digests are diagnostics, not additional publication findings. The public article,
code lineage and historical answers are exposed. A correct result does not prove
input dependence, uncontaminated reasoning or fresh computation.

This component does not assess raw imaging, all 18 families in the broader
released-method programme, a direct compartment contrast, causal plasticity,
paper-only versus author-code access effects, or frontier improvement. A separate
runner, scientific provenance/rights review, protected protocol and calibrated
agent study are required for those claims.
