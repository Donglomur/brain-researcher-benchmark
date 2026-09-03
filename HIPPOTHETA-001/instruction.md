# Hippocampal theta peak frequency during locomotion in a freely moving mouse (HIPPOTHETA-001)

## Scientific context

The rodent hippocampal local field potential (LFP) is dominated, during active behaviour, by
the **theta rhythm** (~6-10 Hz). Theta is prominent while the animal moves through space and is
the reference oscillation for phenomena such as phase precession and theta sequences. A basic
descriptive quantity for a recording is the **theta peak frequency** — the frequency of the
spectral peak in the theta band — measured while the animal is **locomoting**.

The data come from a chronic CA1 recording in a freely moving, adult mouse running an eight-maze
(Huszár et al. 2022, *Nature Neuroscience*, "Preconfigured dynamics in the hippocampus are guided
by embryonic birthdate and rate of neurogenesis", https://doi.org/10.1038/s41593-022-01138-x),
archived as DANDI dandiset **`000552`**.

## Task

For session **`sub-e15-13f1` / `ses-e15-13f1-220117`** of DANDI dandiset **`000552`**, **measure
the hippocampal theta (6-10 Hz) peak frequency of the CA1 LFP while the mouse is locomoting, and
report it in Hz.**

Two assets from this one session are needed; fetch each at runtime from the DANDI archive (obtain
its download/content URL with the `DandiAPIClient` — `get_dandiset("000552","draft")
.get_asset_by_path(...)` — and read it with a streaming reader such as `remfile`; do **not**
download the whole dandiset and do **not** assume a local copy):

- **LFP** — `sub-e15-13f1/sub-e15-13f1_ses-e15-13f1-220117-raw_ecephys.nwb`. The wide-band LFP is
  at `processing/ecephys/LFP/ElectricalSeriesLFP` (128 channels, 1250 Hz, `starting_time` = 0).
  The per-channel chunking means a single channel column streams cheaply.
- **Behaviour** — `sub-e15-13f1/sub-e15-13f1_ses-e15-13f1-220117_behavior+ecephys.nwb`. The
  animal's tracked position is at `processing/behavior/SubjectPosition/SpatialSeries` (an (N, 2)
  series with its own `timestamps`, in seconds on the same clock as the LFP).

Derive the animal's **running speed** from the tracked position. Pick a hippocampal LFP channel
that carries clear theta (for example, the channel with the greatest theta-band power). Estimate
the power spectrum of that channel's LFP (e.g. Welch) and report the frequency of the **peak in
the 6-10 Hz theta band** as the theta peak frequency **during locomotion**.

Standard implementation choices the brief leaves to the analyst (how the position trace is
smoothed before differencing, the exact running-speed cutoff within a sensible range, which
hippocampal channel is used, the spectral estimator's window length) should follow common
practice for characterising the movement-related theta rhythm.

Report, in plain terms, **the hippocampal theta peak frequency during locomotion for this
session** — stating only what your analysis actually supports.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `results.json` — the headline result: `theta_peak_frequency_hz` (the theta peak frequency you
  would report), the theta band used, the channel used, the running criterion, and the spectral
  parameters.
- `run_metadata.json` — dandiset id, session, the two assets used, LFP rate, channel, running
  criterion, total locomotion time analysed.
- `findings.md` — a short written summary (a few sentences) stating the theta peak frequency
  during locomotion and how reliable that estimate is. State only what your analysis supports.

## Failure handling

If the dandiset assets cannot be resolved or a session lacks the expected LFP / position data,
exit non-zero with `failed_precondition` and a non-empty reason, and still write a parseable
`run_metadata.json`, `results.json`, and `findings.md`.
