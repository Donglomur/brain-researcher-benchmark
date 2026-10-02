# MOVIESYNC-001: two descriptive intersubject-correlation estimators

Compute pairwise and leave-one-out (LOO) intersubject correlation (ISC) for three visual MSDL components in the fixed released 40-person development_fmri subset. Either estimator is a valid declared headline. This is a descriptive method-control adaptation, not a paper replication or a requirement to obtain a positive, above-chance, unusually large, or ordered result.

Use the original source bundle at `/app/data/moviesync`, its `source_manifest.json`, the exact public `/app/method_contract.json`, and `/app/output_schema.json`. The two JSON documents specify the complete mathematical and serialization contracts. Use the provided bytes, not a live downloader, a different cohort, a synthetic substitute or historical reference values. Verify source identity before analysis. Do not change the source files.

## Scope and measurement

The literal cohort comprises `sub-pixar001` through `sub-pixar031` and `sub-pixar123` through `sub-pixar131`. Keep all 168 released frames, indexed 0–167, using TR=2 seconds and index-origin 0 as the computational convention. Do not censor, shorten to a minimum length, add a dummy-volume removal, optimize temporal lags or infer an actual movie-onset clock. Richardson et al.'s functional-maturity analysis used TRs 11:168 of ToM/pain timecourses; retaining all 168 frames here is a different whole-window visual-component endpoint, not a movie-only or precisely stimulus-aligned reproduction.

MSDL contains overlapping continuous maps. Resample all 39 maps linearly to each original BOLD grid, zero outside the atlas field, and clip to the original atlas global range including zero. Preserve negative map values. Jointly fit all 39 maps to the scaled BOLD on the full voxel grid, with no additional mask. Use float64 minimum-norm least squares as specified publicly; rank deficiency is recorded, not used to drop maps or people. Only after extraction and cleaning select `Vis`, `Striate`, and `Occ post` by their original label/axis identity.

These are three named MSDL components, not a claim of exact visual-cortex anatomical boundaries. The archive's README qualifies its region names as useful plotting labels rather than final anatomical labeling.

The public recipe makes the Nilearn 0.13.1 settings explicit: no smoothing or detrending; the fixed 15 confounds; order 5 Butterworth 0.01–0.1 Hz at 0.5 Hz sampling, odd padding33 applied to both signals and confounds; centered/population-standardized confounds and the stated pivoted-QR nuisance projection; final sample-SD standardization. Unlike the previous oracle, there is **no second population-SD-plus-1e-9 normalization**. Explicit float64 processing is also prospective, not a claim of legacy bit equality. Do not average the three component timecourses together before computing ISC.

## Estimators and undefined values

For each component, pairwise ISC is Pearson correlation for all 780 distinct unordered participant pairs. A person's component-level pairwise value is the mean of its39 correlations. LOO ISC correlates each person's series with the per-frame mean of the other 39 series, excluding that person by literal ID. A finite constant contributor stays in the template; it is not dropped. Means across the three components and40 people use arithmetic Pearson r, not Fisher-z means, absolute correlations or sign flips.

Declare `isc_estimator` as `pairwise`, `loo`, or `leave-one-out`. Report both diagnostics, with `visual_isc` equal to the declared estimator's complete headline. Neither a positive sign nor LOO exceeding pairwise is required. `reference_zero=0` is descriptive only, not an empirical chance distribution or a significance test.

Canonical source activity is defined by centered L2 norm strictly greater than `1e-12*sqrt(168)` for each person/component and each LOO template. Canonical inactive cases remain undefined. Keep every record and propagate incomplete support with the published fixed denominators; never calculate an available-case replacement. A constant LOO template can occur even when every individual series varies. A valid complete run may contain undefined estimands, represented by JSON null/empty CSV numeric fields and explicit statuses. All NPZ series themselves remain finite, with Boolean source-support flags.

Source fidelity requires final timecourses pointwise within `1e-7+1e-7*abs(reference)` and centered relative L2 error at most `1e-6` for each canonical-active person series **and reconstructed active LOO template**. Raw39-map coefficients have the separately published `1e-5+1e-6*abs(reference)` bound. Cleaning is not replayed from rounded raw receipts. Downstream correlations and summaries are recomputed from accepted final series on canonical support, within absolute `1e-6`; there is no second hidden expected-ISC target. Six-decimal derived scalars are permitted, but NPZ timecourses generally need fuller precision to satisfy the tighter source-fidelity conditions. Precision acceptance does not establish robustness of near-cancelling templates.

## Required output

Write seven files to `${OUTPUT_DIR:-/app/output}`, using a fresh directory without overwriting evidence:

1. `cohort.csv`: all 40 literal people, source row/file joins, frame counts and extraction/cleaning diagnostics.
2. `timecourses.npz`: explicit unique participant, original map and frame axes; all 39 raw coefficients; three final ISC-input series; source activity flags. See exact nine-array schema.
3. `isc_pairs.csv`: all 2340 component-by-unordered-pair records, signed correlation or explicit undefined status.
4. `isc_per_subject.csv`: all 120 person-by-component records, both estimator values, statuses and support counts.
5. `isc_results.json`: both full headlines, all 40 three-component person aggregates, all 3 region aggregates, and the declared headline, with exact expected/defined denominators.
6. `run_metadata.json`: method/schema/source identities, original file inventory, headers/label and frame interpretation, actual software versions and estimator declaration.
7. `findings.md`: nonempty free prose describing the observed computation and its limits. No interpretation phrases or desired numerical claims are graded.

Coherent CSV/NPZ axis reordering, either pair orientation, equivalent numeric storage and harmless finite extras are allowed within the schema and size limits. Duplicate/missing keys, malformed/nonfinite required values, pickle/object arrays, inconsistent derived arithmetic or a `failure_report.json` marker do not constitute success. If a source/numerical precondition fails, stop and preserve a truthful failure report and partial evidence; do not fabricate a complete result.

## Interpretation

Pair and LOO estimates share participants and are not independent replicates. This convenience sample, one film, anatomical registration and remaining common artifacts limit interpretation. Computing ISC does not itself establish causation, statistical significance, developmental effects, population generalization or task difficulty. See [Hasson et al.2004](https://doi.org/10.1126/science.1089506), [Richardson et al.2018](https://doi.org/10.1038/s41467-018-03399-2), and [Nastase et al.2019](https://doi.org/10.1093/scan/nsz037) for scientific motivation and distinctions, not required outcome values.
