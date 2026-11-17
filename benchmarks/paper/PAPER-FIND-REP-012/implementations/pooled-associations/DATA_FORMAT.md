# Processed-feature data format

The single frozen `spec_data` view provides `/public/input_manifest.json` and `/public/data.npz`. This is a safe, reduced representation of the released processed dictionaries, not raw imaging or neural-event data. All original 1,143 rows are retained in their 27 original member groups, including rows that may later be ineligible. No preselected cohort, derived outcome, eligibility decision, pair mask, expected endpoint, reference support digest or private grading value is included.

Read the NPZ with `numpy.load(path, allow_pickle=False)`. It contains 108 numeric arrays: four one-dimensional vectors per member. The manifest names each array, its exact source dtype and shape. Numeric NaN/Inf values are preserved rather than converted to JSON null. The arrays have no object dtype or executable pickle content.

| Exported field | Released source field | Meaning |
| --- | --- | --- |
| `spine_volumes` | `spine_volumes` | Baseline structural measurement in the source units; not a computed change |
| `followup_volumes` | `followup_volumes` | Corresponding follow-up measurement |
| `distance_coactivity_rate_norm_row0` | `distance_coactivity_rate_norm[0,:]` | The first distance-bin normalized local-coactivity vector used by the selected scatter analysis |
| `dendrite_coincident_rate_norm` | Same name | Released normalized spine–dendrite coincident-activity feature |

The two activity vectors are already the authors' processed normalized features. Their normalization is not a z-score to be recomputed from this packet. Other distance bins, raw traces, event detection and chance-rate normalization are not provided. The row-zero projection is an explicit reduction of the original workflow in this one frozen view. Structural measurements retain the source's `volume` field names even where the article describes area imaging.

Each member record contains its full archive member name, original zero-based member and row order, mouse ID, FOV, session, compartment, decoded-source content pin, array descriptors, primitive parameter projection, original spine/follow-up flags and typed dendrite ID tokens. Member order is the frozen selected-release order, not a claim about the authors' historical filesystem traversal. Preserve dtype promotion when combining members; the released join concatenates members sequentially before applying the cohort selection.

Flags have `{kind, value}` records. `kind` preserves whether the source was a string, list or tuple. A string must not silently be treated as a list of characters or as a list of whole labels: the original Python membership rules differ. Text and sequence order are unchanged. Interpret the flags using `RECONSTRUCTION_ASSUMPTIONS.md` to select the source-defined cohort; the packet does not supply a precomputed decision.

Dendrite tokens preserve source type/dtype and a lossless value representation. A missing token is not a shared dendrite label. Use source member and zero-based row as the unique observation key. Mouse/FOV/dendrite labels are provenance; matching labels across fields of view are not proof of an independent biological unit. The selected data include mice present in both compartments; report the shared IDs from the raw cohort without treating these observations as independent animals in any claim beyond the pooled source reconstruction.

The raw cohort count, unique mouse count and shared-mouse list are calculated from all members, before structural eligibility or predictor pairing. Endpoint `raw_rows` counts that compartment's unfiltered rows. `eligible_rows` precedes predictor-specific NaN pairing. `paired_rows` is the actual numerical denominator. `excluded_nan_rows` is `eligible_rows-paired_rows` for that endpoint. Do not silently impute values, discard extra finite outliers, or equate all raw rows with scientifically eligible observations.
