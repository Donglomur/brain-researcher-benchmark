# The ERP CORE N170 face effect at PO8 (N170PROFILE-001)

## Scientific context

The **N170** is a face-sensitive occipito-temporal ERP component: faces elicit a larger
negative deflection than non-face objects around 130-200 ms, maximal at lateral posterior
sites such as **PO8**. In the ERP CORE resource (Kappenman, Farrens, Zhang, Stewart & Luck,
2021, *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2020.117465) the canonical readout of
the N170 paradigm is the **face-minus-car difference wave**, and the component is
characterised (their Figure 2 and Tables 1-3) over the **full N=37 analysis sample**, at the
**a priori PO8 electrode**, by its amplitude and onset latency.

## Task

Reproduce the ERP CORE N170 characterisation on the **full N=37 analysis sample** at **PO8**,
from the **face-minus-car difference wave**. For **each subject** measure, at PO8:

1. the **signed mean amplitude** of the face-minus-car difference wave in the **110-150 ms**
   window (the ERP CORE N170 amplitude score; it is a negative value), and
2. the **50% fractional-peak onset latency** — the ERP CORE onset measure: within a
   **10-150 ms** search window, find the negative peak of the difference wave, then take the
   **earliest (pre-peak) time at which the wave reaches 50% of that peak amplitude**.

Then report, across the 37 subjects, the **group mean and 95% confidence interval** of each
measure.

You may additionally characterise **where on the scalp and over what part of the epoch** the
two conditions diverge with a **whole-scalp spatio-temporal cluster-based permutation test**
(electrode adjacency). If you do, treat it as **descriptive**: report the **corrected cluster
p-value(s)** and **cluster mass**, and label the cluster's time range and electrode set as
**cluster-level only** — it is cluster-level inference, **not** pointwise electrode-by-time
significance. Do **not** report an uncorrected point-by-point significance map (or a set of
"significant electrodes") as if it were reliable: uncorrected mass-univariate testing over the
30 electrodes x all samples manufactures false positives (e.g. in the pre-stimulus baseline).

### Data (baked; no internet)

The per-subject **face-minus-car difference waves** for the 37-subject ERP CORE N170 analysis
sample are provided at **`/app/data/n170_diff_waves.npz`** (NumPy `.npz`), with arrays:

- `subjects` — 37 subject id strings (the ERP CORE N170 analysis sample: subjects 1-40
  **excluding 1, 5 and 16**, which ERP CORE dropped for excessive artifacts),
- `diff_uv` — the difference waves, shape `(37, 30, n_times)`, in **microvolts**
  (subject x scalp-electrode x time),
- `ch_names` — the 30 scalp electrode names (includes `PO8`),
- `times_ms` — the time axis in **milliseconds** (epoch -200..400 ms),
- `sfreq` — the sampling rate (Hz).

These are the averaged per-subject difference waves produced by the pinned ERP CORE-style
pipeline: EOG channels `HEOG_left`/`HEOG_right`/`VEOG_lower` excluded; EEG band-pass
**0.1-30 Hz**; faces = stimulus codes 1-40, cars = 41-80; epochs **-200 to 400 ms**;
**average reference** over the 30 scalp electrodes; **-200 to 0 ms** baseline; epochs
exceeding **150 uV** peak-to-peak rejected; **face minus car** per subject.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `per_subject.csv` — one row per subject, columns **`subject_id`**, **`amp_po8_uv`**
  (signed PO8 mean amplitude 110-150 ms), **`onset_ms`** (50% fractional-peak onset latency).
  All 37 analysis-sample subjects must appear.
- `n170.json` — at minimum
  `{"electrode": "PO8", "n_subjects": <int>, "amp_po8_uv": <signed float group mean>,
    "amp_po8_ci95": [<lo>, <hi>], "onset_latency_ms": <float group mean>,
    "onset_ci95": [<lo>, <hi>]}`. If you ran the whole-scalp cluster test, add a
  `"cluster_level_only"` object with its `cluster_pvals` (corrected), `cluster_mass`, and its
  descriptive `time_range_ms` / `n_electrodes`.
- `run_metadata.json` — dataset id, analysis sample (n and the excluded subjects), electrode,
  the measurement windows, and a short description of how each measure was computed.
- `findings.md` — a few sentences reporting the N170 face effect at PO8: the signed
  face-minus-car mean amplitude (110-150 ms) and the 50% fractional-peak onset latency, over
  the 37-subject sample. If you ran the cluster test, state that its time/scalp membership is
  descriptive (cluster-level only) and that an uncorrected point-wise map would be spurious.
  State only what your analysis supports.

## Failure handling

If the baked N170 difference-wave file cannot be read, exit non-zero with `failed_precondition`
and a non-empty reason, and still write parseable `run_metadata.json`, `n170.json`, and
`findings.md`.
