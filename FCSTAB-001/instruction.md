# Within-run change of the strongest functional connections (FCSTAB-001)

## Scientific context

The strongest edges of a resting-state functional-connectivity network — the ROI pairs
with the highest correlations — are often treated as the stable "backbone" of the
functional connectome and are the edges most likely to be reported, thresholded on, and
carried forward into hub and graph analyses. A natural question is how stable those
dominant connections are *within a single scan*: do the strongest functional connections
hold their strength across the run, or do they change (weaken) as the session proceeds?
Within-scan reliability of connectivity estimates is an active methodological concern
(e.g. Laumann et al. 2015, *Neuron*; Noble et al. 2019, *NeuroImage*).

A subtlety governs any "select the strong edges, then look at their change" analysis:
edges chosen because they are extreme on one measurement will, on an independent
measurement, tend to move — so a naive selected-set change is not, by itself, an estimate
of a genuine temporal effect.

## Data (baked into the image; no internet)

The pre-extracted **Craddock-200 (CC200)** ROI time series for the cohort are provided
**offline** in the container at `/app/data/`:

- `/app/data/abide_cc200_pitt40.npz` — a NumPy `.npz` with
  `timeseries` (shape **(40, 196, 200)** = subjects × time × ROI, float32),
  `subject_ids` (40 ints) and `file_ids` (40 strings).
- `/app/data/MANIFEST.json` — provenance and pinned content hashes (per-file SHA-256,
  cohort hash, and the float32 numeric hash `37c4f5e901962978d1d00ce503af590971edc3a1fec484f964fb02e86addedac`).

These are the **first 40 quality-checked subjects** of the ABIDE Preprocessed `cpac`
derivatives (band-pass filtered, **without** global-signal regression, `quality_checked=True`),
in the default `SUB_ID` order, exactly as returned by
`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", band_pass_filtering=True,
global_signal_regression=False, derivatives=["rois_cc200"], quality_checked=True, n_subjects=40)`.

**Acquisition (verify against MANIFEST.json):** all 40 subjects are from a **single site,
PITT (Pittsburgh)**, scanned **eyes closed**, each a **single resting run of 196 volumes
(~4.9 minutes at TR = 1.5 s)** — a short, single-site, eyes-closed acquisition. The pinned
`file_ids` are `Pitt_0050003, Pitt_0050004, Pitt_0050005, Pitt_0050006, Pitt_0050007,
Pitt_0050008, Pitt_0050010, Pitt_0050011, Pitt_0050012, Pitt_0050013, Pitt_0050014,
Pitt_0050015, Pitt_0050016, Pitt_0050020, Pitt_0050022, Pitt_0050023, Pitt_0050024,
Pitt_0050025, Pitt_0050026, Pitt_0050027, Pitt_0050028, Pitt_0050030, Pitt_0050031,
Pitt_0050032, Pitt_0050033, Pitt_0050034, Pitt_0050035, Pitt_0050036, Pitt_0050037,
Pitt_0050038, Pitt_0050039, Pitt_0050040, Pitt_0050041, Pitt_0050042, Pitt_0050043,
Pitt_0050044, Pitt_0050045, Pitt_0050046, Pitt_0050047, Pitt_0050048` (subject ids are the
numeric part, e.g. `50003`).

## Task

Split each subject's run into two equal, contiguous halves — the **first half** (earlier)
and the **second half** (later), each `L = floor(T/2)` time points. In each half form the
ROI × ROI correlation matrix over the ROIs with non-degenerate signal (drop any ROI that is
constant/all-zero in a half), and take the **Fisher z-transformed** correlation of every ROI
pair as that half's edge-connectivity values. "Strongest connections" = the **top decile
(10%)** of edges. For every subject compute the **signed within-run change**
`Δz = mean(second-half z) − mean(first-half z)` of the top-decile edge set under **four
selection schemes**:

1. **forward** — top decile selected on the **first half** (the naive scheme: select and
   re-measure on the second half).
2. **reverse** — top decile selected on the **second half** (same Δz, edges chosen on the
   *other* half).
3. **independent** — a top-decile strong-edge set chosen **independently of this subject's
   two halves** (e.g. leave-one-subject-out from the other 39 subjects' connectivity, or a
   cross-fitted / independently selected set), then Δz measured on this subject's halves.
4. **random** — a **size-matched random** edge set (control).

For each scheme report the **per-subject signed Δz** and the **group-level uncertainty**
(mean, SE or 95% CI, and a one-sample test against 0). Because a selected-set change is not
by itself an estimate of a genuine effect, **any claim that the strongest connections are
stable must be made against a prespecified equivalence margin** (e.g. TOST at ±0.05 z on the
selection-free estimate); if the target is reliability, additionally report edge-set / rank
agreement (top-decile set overlap, edge rank Spearman, or ICC) between the halves.

Then state, in plain terms and **using the numbers**, **what the comparison of the four
schemes establishes about whether the strongest functional connections genuinely weaken
across the run** — reporting only what your analysis actually supports.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `stability.csv` — **one row per subject** with columns exactly:
  `subject_id, n_edges, forward_first_half, forward_second_half, forward_delta,
  reverse_delta, independent_delta, random_delta`
  where `forward_first_half` / `forward_second_half` are the mean first-/second-half
  connectivity of the forward-selected top-decile edges, and `*_delta` are the per-subject
  signed changes `second − first` for the four selection schemes.
- `summary.json` — group-level summary with at least:
  ```
  {
    "n_subjects": ..., "atlas": ..., "metric": ...,
    "cohort": {"site": ..., "eye_status_at_scan": ..., "n_timepoints": ...,
               "run_minutes_approx": ..., "data_sha256": ...},
    "selection_schemes": {
       "forward":     {"delta_mean": ..., "delta_se": ..., "ci95_lo": ..., "ci95_hi": ...},
       "reverse":     {"delta_mean": ...},
       "independent": {"delta_mean": ...},
       "random":      {"delta_mean": ...}
    },
    "forward_top_decile_connectivity": {"first_half_mean": ..., "second_half_mean": ...,
                                        "change": ..., "pct_change": ...},
    "equivalence": {"margin_z": ..., "tost_p": ..., "equivalent_within_margin": ...},
    "reliability": {"top_decile_set_overlap_first_vs_second": ..., ...},
    "conclusion": "..."
  }
  ```
  The four `selection_schemes.*.delta_mean` values must equal what your `stability.csv` rows
  actually produce.
- `findings.md` — a short written summary stating **what the four selection schemes establish
  about genuine within-run weakening of the strongest connections**, and what that implies
  for treating them as the stable backbone of the connectome. State only what your analysis
  actually supports.

## Failure handling

If the baked data cannot be read, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `summary.json` and `findings.md`.
