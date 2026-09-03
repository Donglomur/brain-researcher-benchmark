# CA1 sharp-wave-ripple incidence rate during non-REM sleep in a freely moving mouse (HIPPORIPPLE-001)

## Scientific context

Hippocampal **sharp-wave ripples (SWRs)** are brief (~40-100 ms) high-frequency (~150-250 Hz)
oscillatory events in the CA1 local field potential. They occur predominantly during
**non-REM (slow-wave) sleep** and awake immobility/consummatory behaviour, and are largely
absent during active locomotion and REM sleep. A basic descriptive statistic for a recording is
the **SWR incidence rate** — how many ripples occur per second — during non-REM sleep, the state
in which ripples are most abundant.

The data come from a chronic CA1 recording in a freely moving, adult mouse (Huszár et al. 2022,
*Nature Neuroscience*, "Preconfigured dynamics in the hippocampus are guided by embryonic
birthdate and rate of neurogenesis", https://doi.org/10.1038/s41593-022-01138-x), archived as
DANDI dandiset **`000552`**. Ripple events and brain-state (sleep) annotations for the session
are provided in the NWB file.

## Task

For session **`sub-e15-13f1` / `ses-e15-13f1-220117`** of DANDI dandiset **`000552`**, **report
the CA1 sharp-wave-ripple incidence rate during non-REM sleep, in events per second.**

Fetch the session's behaviour/ephys NWB asset at runtime from the DANDI archive (obtain its
download/content URL with the `DandiAPIClient` — `get_dandiset("000552","draft")
.get_asset_by_path("sub-e15-13f1/sub-e15-13f1_ses-e15-13f1-220117_behavior+ecephys.nwb")` — and
read it with a streaming reader such as `remfile`; do **not** download the whole dandiset and do
**not** assume a local copy). This one ~270 MB asset contains everything you need:

- **Detected ripple events** at `processing/ecephys/Ripples` (a `TimeIntervals` table; each row is
  one detected SWR, with `start_time`, `stop_time`, and a `peaks` time).
- **Brain-state annotations** at `processing/behavior/SleepStates` (a `TimeIntervals` table whose
  `label` is one of `Awake`, `Non-REM`, `REM`), covering the full recording.

Use the provided ripple detections and the provided non-REM sleep annotations. Report the SWR
incidence rate during non-REM sleep together with the number of ripples and the amount of non-REM
sleep the rate is based on.

Standard implementation choices the brief leaves to the analyst (whether a ripple is assigned to a
state by its peak time or its interval, how interval boundaries are handled) should follow common
practice for reporting a ripple incidence rate.

Report, in plain terms, **the non-REM SWR incidence rate for this session** — stating only what
your analysis actually supports.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `results.json` — the headline result: `ripple_rate_hz` (the non-REM SWR incidence rate in
  events per second you would report), `n_ripples_nonrem`, `nonrem_duration_s`, and any other
  counts/parameters you used.
- `run_metadata.json` — dandiset id, session, asset, total ripples detected, total recording
  duration, non-REM duration, how ripples were assigned to states.
- `findings.md` — a short written summary (a few sentences) stating the non-REM SWR incidence rate
  and how it compares to the animal's overall activity. State only what your analysis supports.

## Failure handling

If the dandiset asset cannot be resolved or the session lacks the expected ripple / sleep-state
data, exit non-zero with `failed_precondition` and a non-empty reason, and still write a parseable
`run_metadata.json`, `results.json`, and `findings.md`.
