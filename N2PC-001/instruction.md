# The N2pc component amplitude in the ERP CORE visual-search task (N2PC-001)

## Scientific context

The **N2pc** is a posterior ERP component that indexes the focusing of covert visual
attention onto a lateralized target. It appears at lateral occipito-parietal sites — the
**PO7 / PO8** electrode pair — as a negativity over the hemisphere **contralateral** to the
visual field of the attended target, roughly **200-300 ms** after the search array. Its
canonical readout is the **contralateral-minus-ipsilateral** difference in that window. In
the ERP CORE visual-search paradigm (Kappenman, Farrens, Zhang, Stewart & Luck, 2021,
*NeuroImage*, https://doi.org/10.1016/j.neuroimage.2020.117465), the participant reports the
gap position (top vs bottom) of a colour-defined target square that appears to the **left**
or **right** of fixation among distractors.

## Task

Using the ERP CORE **N2pc** continuous EEG recordings for **subjects 1, 3, 4, 5, 6, 7, 8,
9, 10, 11, 12, 13** (subject 2 is not part of the released N2pc set), **compute the N2pc
component amplitude at the PO7/PO8 pair** and report it as the **mean
contralateral-minus-ipsilateral amplitude, in microvolts, over the 200-300 ms window**,
grand-averaged over the subjects, following the fixed processing below.

### Data (ERP CORE N2pc, BIDS-compatible continuous EEGLAB files)

Each subject has a `sub-<nnn>_task-N2pc_eeg.set` header and a matching `.fdt` data file that
must sit in the same directory. Download both files for each subject from OSF at
`https://osf.io/download/<id>/` (no credentials required):

```
subj   .set id                         .fdt id
1      60078009e80d3708eca59ed0        60077ffeba010908978910b5
3      6007806d86541a092614bc4e        60078065e80d3708eca5a074
4      60078089e80d3708eca5a0f6        60078084e80d3708eaa592c8
5      600780ace80d3708eaa59320        60078098e80d3708eaa59300
6      600780c5ba010908a7893ce5        600780bfba010908978910d5
7      600780e686541a092614bd07        600780dbe80d3708e7a586fc
8      6007810be80d3708e2a57755        600780ff86541a092c1534dc
9      6007812eba010908a7893eae        60078127ba010908a7893e7e
10     6007816b86541a092614be07        6007815d86541a092c153ba7
11     600781a0ba010908a7894081        6007818eba01090892890b1e
12     600781ca86541a092c15443a        600781c5e80d3708eca5a5e9
13     600781f186541a092614bf0b        600781e4ba0109089e8922f0
```

Save each pair as `sub-<nnn>_task-N2pc_eeg.set` / `sub-<nnn>_task-N2pc_eeg.fdt` (the `.set`
references the `.fdt` by name; use zero-padded subject numbers, e.g. `sub-001`). Read with
`mne.io.read_raw_eeglab`. Each recording has 30 scalp EEG electrodes (including PO7 and PO8)
plus 3 peripheral EOG channels (`HEOG_left`, `HEOG_right`, `VEOG_lower`), sampled at 1024 Hz.

### Event codes (ERP CORE N2pc scheme)

Stimulus event codes are three digits **XYZ**:

| digit | meaning | values |
|-------|---------|--------|
| hundreds (X) | target colour | 1 = blue, 2 = pink |
| tens (Y) | target visual field | 1 = left, 2 = right |
| ones (Z) | gap position | 1 = top, 2 = bottom |

So the eight stimulus codes are 111, 112, 121, 122, 211, 212, 221, 222. Codes 201
(response, correct) and 202 (response, error) are behavioural, not stimulus events. Read the
codes with `mne.events_from_annotations`.

### Fixed processing (pin exactly)

- Use **all target-stimulus events** (all eight stimulus codes; both correct and error
  trials).
- Set the 3 EOG channels aside and analyse the **30 scalp EEG electrodes**. Apply an
  **average reference** across those 30 electrodes.
- Apply a **0.1-30 Hz band-pass** filter.
- Epoch around each stimulus event, apply a **pre-event baseline** (the 200 ms before the
  event), and average.
- Form the **contralateral** and **ipsilateral** waveforms at the **PO7/PO8** pair, take
  their difference, and measure the **mean amplitude in the 200-300 ms post-stimulus
  window**, for each subject.
- Report the **grand average** of that contralateral-minus-ipsilateral amplitude over the
  subjects, in **microvolts**.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `n2pc.json` — at minimum `{"n2pc_amplitude_uv": <float>, "electrode_pair": "PO7/PO8",
  "measure": "mean contralateral-minus-ipsilateral amplitude, 200-300 ms",
  "window_ms": [200, 300], "n_subjects": <int>}`.
- `run_metadata.json` — dataset id, subjects, electrode pair, reference, band-pass,
  baseline, and the measurement window you used.
- `findings.md` — a few sentences reporting the N2pc amplitude. State only what your
  analysis supports.

## Failure handling

If the ERP CORE N2pc recordings cannot be resolved, exit non-zero with `failed_precondition`
and a non-empty reason, and still write parseable `run_metadata.json`, `n2pc.json`, and
`findings.md`.
