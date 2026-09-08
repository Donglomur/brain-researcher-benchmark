# Within-run stability of the strongest functional connections (FCSTAB-001)

## Scientific context

The strongest edges of a resting-state functional-connectivity network — the ROI pairs
with the highest correlations — are often treated as the stable "backbone" of the
functional connectome and are the edges most likely to be reported, thresholded on, and
carried forward into hub and graph analyses. It is therefore natural to ask how stable
those dominant connections are *within a single scan*: do the strongest functional
connections hold their strength across the run, or do they weaken as the session proceeds
(for instance as vigilance and arousal drift over a long, eyes-open resting acquisition)?
Within-scan reliability of connectivity estimates is an active methodological concern
(e.g. Laumann et al. 2015, *Neuron*; Noble et al. 2019, *NeuroImage*, on the reliability
of functional-connectivity edges).

## Task

Using the nilearn-pinned preprocessed derivatives of the **ABIDE** resting-state cohort
(`nilearn.datasets.fetch_abide_pcp`, pipeline `"cpac"`, band-pass filtered, **without**
global-signal regression, `quality_checked=True`), take the **first 40 subjects** in the
default `SUB_ID` order and use the pre-extracted **Craddock 200 (CC200)** ROI time series
(`derivatives=["rois_cc200"]`). Each subject provides one resting-state run of ROI × time
series.

For each subject:

1. **Split the run into two equal, contiguous halves** — the first half (earlier in the
   run) and the second half (later in the run) — using the same number of time points in
   each half.
2. In **each half separately**, form the ROI × ROI correlation matrix over the ROIs with
   non-degenerate signal, and take the **Fisher z-transformed** correlation of every ROI
   pair as that half's edge-connectivity values.
3. From the **first half**, identify the **top decile** of edges — the 10% of ROI pairs
   with the highest first-half connectivity (the subject's strongest connections).
4. For exactly that set of edges, compute the **mean first-half connectivity** and the
   **mean second-half connectivity**, and their difference (second − first).

Then summarise across the 40 subjects: report the group-mean first-half and second-half
connectivity of the strongest (top-decile) edges and the mean within-run change.

The standard preprocessing choices the derivative leaves to the analyst (which ROIs to
keep, exactly how the halves are cut when the run length is odd, Fisher-z vs raw r for the
summary) should follow common practice.

Report, in plain terms, **whether the strongest functional connections are stable across
the run or weaken as the scan proceeds**, stating only what your analysis actually
supports.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `stability.csv` — one row per subject:
  `subject_id, n_edges, top_decile_first_half, top_decile_second_half, top_decile_change`
  (the last three are the mean connectivity of that subject's top-decile edges in the
  first half, in the second half, and the second − first change).
- `summary.json` — group-level summary with at least:
  `{"n_subjects": ..., "atlas": ..., "metric": ...,
    "top_decile_connectivity": {"first_half_mean": ..., "second_half_mean": ...,
    "change": ..., "pct_change": ...}}`,
  plus the preprocessing choices you made.
- `findings.md` — a short written summary stating whether the strongest functional
  connections are stable within the run or weaken across it, and what that implies for
  treating them as the stable backbone of the connectome. State only what your analysis
  actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a
non-empty reason, and still write parseable `summary.json` and `findings.md`.
