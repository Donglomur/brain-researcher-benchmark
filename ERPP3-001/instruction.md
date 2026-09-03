# The P3b oddball effect at Pz (ERPP3-001)

## Scientific context

The **P3b** is a large centro-parietal positive ERP component elicited by rare,
task-relevant ("oddball") stimuli, maximal at midline parietal sites such as **Pz**. In
the ERP CORE active visual oddball paradigm (Kappenman, Farrens, Zhang, Stewart & Luck,
2021, *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2020.117465), the canonical
readout is the **rare-minus-frequent difference wave** at Pz and its amplitude in the P3b
window.

## Task

Using the ERP CORE **P3** continuous EEG recordings for **subjects 1-12**, **compute the
rare-minus-frequent P3b difference-wave amplitude at electrode Pz in the 300-600 ms
window** and report it (microvolts), following the fixed processing below.

### Data (ERP CORE P3, downsampled continuous EEGLAB files, subjects 1-12)

Each subject has a `<n>_P3_shifted_ds.set` header and a matching `.fdt` data file that
must sit in the same directory. Download both files for each subject from OSF at
`https://osf.io/download/<id>/`:

```
subj   .set id                         .fdt id
1      5f18a6d085d25a001def6044        5f18a6cc9e0cfe001b1c123b
2      5f18b0f185d25a0023ef2fa2        5f18b0ee85d25a0023ef2f9d
3      5f18b97c86a05500320dec3d        5f18b97985d25a001eef92db
4      5f18c1b285d25a001eef9b4d        5f18c1b086a055003c0df0fc
5      5f18c33086a055003c0df3da        5f18c32c9e0cfe00251c5302
6      5f18c3db9e0cfe00251c546d        5f18c3d89e0cfe00241c3928
7      5f18c49785d25a001eef9f18        5f18c4949e0cfe00241c3ae6
8      5f18c55e9e0cfe00251c56bb        5f18c55c86a055003c0df785
9      5f18c60d9e0cfe00251c57b4        5f18c60b9e0cfe00201c33c5
10     5f18a7b99e0cfe00241c11ab        5f18a7b485d25a001eef7ece
11     5f18a8b19e0cfe001b1c14b1        5f18a8ad85d25a0023ef236e
12     5f18a9b386a055003c0dc805        5f18a9af9e0cfe00201c13e5
```

Save each pair as `<n>_P3_shifted_ds.set` / `<n>_P3_shifted_ds.fdt` (the `.set`
references the `.fdt` by name). Read with `mne.io.read_raw_eeglab`.

### Fixed processing (pin exactly)

- Mark `HEOG_left`, `HEOG_right`, `VEOG_lower` as EOG; the other 30 channels are scalp EEG.
- Band-pass filter the EEG **0.1-30 Hz**.
- Re-reference the EEG to the **average of the 30 scalp electrodes**.
- Stimulus event codes are two digits **XY**: X is the block's designated target letter
  and Y is the presented letter (1=A … 5=E). A stimulus is **rare** (oddball/target) when
  **X == Y** — i.e. codes **11, 22, 33, 44, 55** — and **frequent** (standard) otherwise
  (the other two-digit XY codes). Ignore the response codes (201/202).
- Epoch **-200 to 800 ms** around stimulus onset, apply a **-200 to 0 ms baseline**, and
  **average all epochs** of each condition (no additional peak-to-peak artifact
  rejection).
- The difference wave is **rare minus frequent** (average of rare minus average of
  frequent), per subject.
- Measure the P3b as the **amplitude of the Pz rare-minus-frequent difference wave over
  the 300-600 ms window**, per subject.
- Report the **mean across the 12 subjects** of that per-subject amplitude.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `p3.json` — at minimum `{"p3b_amplitude_uv": <float>, "channel": "Pz",
  "window_ms": [300, 600], "n_subjects": <int>}`.
- `run_metadata.json` — dataset id, n subjects, the reference and filter you used, the
  baseline and measurement window, and the rare/frequent code definition.
- `findings.md` — a few sentences reporting the rare-minus-frequent P3b amplitude at Pz.
  State only what your analysis supports.

## Failure handling

If the ERP CORE P3 files cannot be resolved, exit non-zero with `failed_precondition`
and a non-empty reason, and still write parseable `run_metadata.json`, `p3.json`, and
`findings.md`.
