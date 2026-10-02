# Windowed connectivity variability and a shared-phase comparison

Using the supplied resting-state BOLD recordings, quantify how much windowed
functional-connectivity estimates vary, and compare that statistic with a
specified finite-record Fourier-surrogate ensemble. This is a paper-derived
method/sensitivity exercise, not a reproduction of Allen et al.'s connectivity
states or evidence for an ADHD group difference.

The source contains a preselected 30-person convenience cohort from Nilearn's
public ADHD demo and the Harvard–Oxford cortical max-probability atlas
(25% threshold, 2-mm release, 48 nonbackground labels). Membership is the
explicit literal-ID list in the public contract; it is **not** the first 30
participants returned by the current Nilearn loader. Do not fetch additional
data. The container must run offline.

## Public inputs and numerical contract

Original files are under `/app/data/fcvar`. Read `/app/source_manifest.json`,
`/app/method_contract.json`, `/app/output_schema.json`, and
`/app/SOURCE_NOTICE.md`. The manifest identifies the original files and their
checksums; the other two JSON documents specify the estimator and keyed output
format, including numerical tolerances and undefined cases. The public
`/app/signal_kernel.py` defines the deterministic float64 phase/window/rank
arithmetic used for exact Monte Carlo counts. You may use it or implement the
same public computation. It contains no original-data results.

Extract all 48 atlas ROI means on each participant's original BOLD grid using
the declared nearest-label resampling. Use the source header's time units and
TR. Preserve every original frame. Apply the task's public detrending, bandpass
and ordered 13-confound regression recipe; do not silently fill missing
confounds, censor frames, or substitute a different cohort. Retain all ROI
identities in the evidence, including empty geometric support and inactive
signals, with the specified flags rather than invented measurements.

For rectangular windows of 20, 30 and 44 frames, advanced by 3 frames, calculate
Pearson correlations, clip to ±0.999 before Fisher transformation, take each
edge's sample standard deviation across windows, and average over the fixed
retained edges. Window lengths are in frames: their duration in seconds follows
each participant's TR. At least two windows and two active ROIs are necessary.
The public conditioning rule determines whether every required window has a
well-defined correlation; do not drop individual windows or edges to repair an
undefined statistic.

Generate 50 full-recording shared-phase surrogates for each participant/window
configuration, with one declared uint32 base seed for the whole analysis
(default 0). Follow the exact public PCG64 draw schedule, including its DC
and even-length Nyquist handling. A frequency's phase is shared across all ROI
signals; do not independently randomize regions, phase only a cropped window,
or re-clean surrogates. Phase arrays are receipts; canonical regenerated phases
define the calculation.

Report every observed and surrogate statistic, their observed/mean-null ratio,
and the inclusive plus-one rank fraction `(1 + count(null >= observed))/51`.
Use the unrounded own-series computations, not rounded CSV values, for counts
and subsequent summaries. Keep all 50 draw slots, including duplicates or
undefined slots. A zero null mean makes the ratio undefined, not necessarily
the rank fraction. Each group metric uses all 30 participants equally; if its
required participant values are incomplete, report its actual count and a
null group value rather than silently changing the cohort.

## Deliverables

Write these seven files under `${OUTPUT_DIR}` (default `/app/output`), following
the public schema:

- `cohort.csv`: the complete ID-keyed cohort and source clock/support metadata.
- `roi_evidence.npz`: full keyed raw/cleaned ROI series, ROI/support diagnostics
  and phase receipts; use real/text/Boolean arrays, never pickled objects.
- `variability.csv`: all 90 participant-by-window records.
- `surrogate_statistics.csv`: all 4,500 participant-by-window-by-draw records.
- `dynamics.json`: complete, separately counted group summaries for each window.
- `run_metadata.json`: source/contract identities, declared seed and processing
  metadata, with `status: "ok"` only after the complete computation.
- `findings.md`: a short account of the observed result and its limitations.

Source failure is not an admissible participant exclusion. If the analysis
cannot complete, leave a `failure_report.json` explaining why; its presence
prevents a successful score. Legitimately undefined numerical endpoints are
instead completed results with the schema's explicit statuses and nulls.

The verifier authenticates the original data, reconstructs extraction and
cleaning, and checks all keyed receipts. Accepted source-close cleaned signals
drive the downstream comparison; there is no required effect direction,
significance rate, ratio range or preferred prose conclusion. Scoring is binary:
all required checks must pass. Additional clearly labeled analyses are optional
and cannot replace the required calculation.

## Interpretation and paper connection

The shared-phase construction is adapted from Prichard and Theiler's
[multivariate surrogate method, Eq. 5](https://arxiv.org/pdf/comp-gas/9405002).
It preserves the finite-DFT power and cross-spectra, not every possible
distributional or temporal property. The specified finite-ensemble rank is not
a universal stationarity test. Rejection does not isolate a neural mechanism;
nonrejection does not establish absence of meaningful dynamics.

[Allen et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC3920766/) used a different
405-person ICA, tapered-window, regularized-connectivity and clustering
analysis. This task does not reproduce its states, figures or population
finding. [Hutchison et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC3807588/)
provides the relevant caution that variability of windowed estimates alone
does not establish changing underlying interactions. Overlapping windows,
edges and surrogates are not additional independent participants.
