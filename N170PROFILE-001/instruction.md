# Spatiotemporal profile of the N170 face effect (N170PROFILE-001)

## Scientific context

The **N170** is a face-sensitive occipito-temporal ERP component: faces elicit a larger
negative deflection than non-face objects around 130-200 ms, maximal at lateral posterior
sites such as PO8. The **face-minus-car difference wave** is the canonical readout of the
ERP CORE N170 paradigm (Kappenman, Farrens, Zhang, Stewart & Luck, 2021, *NeuroImage*,
https://doi.org/10.1016/j.neuroimage.2020.117465). Beyond the peak at a single electrode,
a common next question is **where on the scalp and over what part of the epoch the two
conditions actually diverge** — i.e. the spatiotemporal profile of the effect.

## Task

Using the ERP CORE **N170** continuous EEG recordings for **subjects 1-12**, map the
**face-minus-car difference across the 30 scalp electrodes and the whole epoch** and
report **where and when faces and cars reliably differ**, following the fixed processing
below. Specifically, determine, across the group of 12 subjects:

- the **onset latency** of the face-minus-car effect (the earliest time at which the two
  conditions reliably diverge),
- the **time range** over which the difference is reliable, and
- the **set of scalp electrodes** that carry the reliable difference.

Also report the face-minus-car difference-wave **peak amplitude at PO8** (most negative
value in 110-150 ms, per subject then averaged) so the underlying ERP can be checked.

### Data (ERP CORE N170, downsampled continuous EEGLAB files, subjects 1-12)

Each subject has a `<n>_N170_shifted_ds.set` header and a matching `.fdt` data file that
must sit in the same directory. Download both files for each subject from OSF at
`https://osf.io/download/<id>/`:

```
subj   .set id                         .fdt id
1      5f161eb00596f601227a0103        5f161ead0870f201320984de
2      5f16272b0870f20133098a1a        5f1627280596f6012179e75a
3      5f1630c20596f6012179f5cb        5f1630bc0596f6012179f5bc
4      5f163c3a0596f6011d7a0609        5f163c350870f2011709d6d2
5      5f163e7d0870f2013309b91b        5f163e790596f601217a11d3
6      5f163fa16ef4400137bcf3da        5f163f9d6ef4400137bcf3cc
7      5f1640c50870f2013209dd22        5f1640c00596f6011d7a0ef1
8      5f1641f80870f2012709f785        5f1641f20596f6011d7a1160
9      5f16432d0596f6012c7997cd        5f1643290870f2013309c548
10     5f161f840596f601227a026b        5f161f820596f6011d79dd0f
11     5f1620590596f6011979d25b        5f1620546ef4400130bd131b
12     5f16211b6ef440012fbce9c8        5f1621180596f6012179e0a0
```

Save each pair as `<n>_N170_shifted_ds.set` / `<n>_N170_shifted_ds.fdt` (the `.set`
references the `.fdt` by name). Read with `mne.io.read_raw_eeglab`.

### Fixed processing (pin exactly)

- Mark `HEOG_left`, `HEOG_right`, `VEOG_lower` as EOG; the other 30 channels are scalp EEG.
- Band-pass filter the EEG **0.1-30 Hz**.
- Stimulus event codes **1-40 are faces, 41-80 are cars**. Epoch **-200 to 400 ms** around
  stimulus onset, no baseline yet.
- **Re-reference the EEG to the average of the 30 scalp electrodes.** Then apply a **-200
  to 0 ms baseline** and drop epochs exceeding a **150 uV** peak-to-peak threshold on any
  EEG channel.
- Average faces and cars per subject; the difference wave is **face minus car**.
- Work from the **per-subject face-minus-car difference waves** (all 30 scalp electrodes,
  the full -200 to 400 ms epoch) across the 12 subjects.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `n170.json` — at minimum
  `{"onset_latency_ms": <float>, "sig_time_range_ms": [<start>, <end>],
    "sig_electrodes": [<str>, ...], "peak_amplitude_po8_uv": <float>,
    "n_subjects": <int>}`.
- `run_metadata.json` — dataset id, n subjects, the reference, filter, baseline, epoch, and
  a short description of how you decided where/when the difference is reliable.
- `findings.md` — a few sentences reporting the spatiotemporal profile of the face-minus-car
  N170 effect: its onset, the time range and scalp electrodes over which it is reliable, and
  the PO8 peak amplitude. State only what your analysis supports.

## Failure handling

If the ERP CORE N170 files cannot be resolved, exit non-zero with `failed_precondition`
and a non-empty reason, and still write parseable `run_metadata.json`, `n170.json`, and
`findings.md`.
