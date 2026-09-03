# The N400 semantic word-pair effect at CPz (N400-001)

## Scientific context

The **N400** is a centro-parietal negative ERP component that is larger (more negative)
for words that are **semantically unrelated** to a preceding context than for related
words, and is maximal at midline central-parietal sites such as **CPz**. In the ERP CORE
word-pair association paradigm (Kappenman, Farrens, Zhang, Stewart & Luck, 2021,
*NeuroImage*, https://doi.org/10.1016/j.neuroimage.2020.117465), each trial presents a
**prime** word followed by a **target** word, and the participant judges whether the two
words are semantically related. The canonical readout is the **unrelated-minus-related
difference wave** and its amplitude in the N400 window.

## Task

Using the ERP CORE **N400** continuous EEG recordings for **subjects 1-12**, **compute the
unrelated-minus-related N400 difference-wave amplitude at electrode CPz in the 300-500 ms
window** and report it (microvolts), following the fixed processing below.

### Data (ERP CORE N400, downsampled continuous EEGLAB files, subjects 1-12)

Each subject has a `<n>_N400_shifted_ds.set` header and a matching `.fdt` data file that
must sit in the same directory. Download both files for each subject from OSF at
`https://osf.io/download/<id>/`:

```
subj   .set id                         .fdt id
1      5f1694d20596f601307a31c0        5f1694d00596f6013579eea0
2      5f169db50870f2014b097fda        5f169db20596f601357a038b
3      5f16a6be0596f6012c7a1d1f        5f16a6bb6ef440013ebd3c2e
4      5f16aff70596f6012c7a27f2        5f16aff30596f6013e79a466
5      5f16b1d20870f2014b09a318        5f16b1cf6ef4400155bc9530
6      5f16b2cf6ef440014fbcbdbe        5f16b2cd0870f2014b09a4dd
7      5f16b3b36ef4400149bcea77        5f16b3b00870f201500972da
8      5f16b49b0596f6012c7a2da6        5f16b4980596f601357a29a9
9      5f16b5776ef4400155bc9e0d        5f16b5736ef4400154bc9aa4
10     5f1695950596f601307a331d        5f1695930596f6013579f09c
11     5f1696566ef4400148bca87f        5f1696530596f6012f7a0633
12     5f1697226ef4400148bca9fb        5f16971f0870f2014b097388
```

Save each pair as `<n>_N400_shifted_ds.set` / `<n>_N400_shifted_ds.fdt` (the `.set`
references the `.fdt` by name). Read with `mne.io.read_raw_eeglab`.

### Event codes (ERP CORE N400 word-pair association scheme)

Stimulus event codes are three digits **XYZ**:

| digit | meaning | values |
|-------|---------|--------|
| hundreds (X) | word type | 1 = prime, 2 = target |
| tens (Y) | word-pair type | 1 = related, 2 = unrelated |
| ones (Z) | word list | 1 = list 1, 2 = list 2 |

So the stimulus codes are 111, 112, 121, 122 (prime words) and 211, 212, 221, 222 (target
words). Response codes 201 (correct) and 202 (incorrect) are behavioural and are not
stimulus events.

### Fixed processing (pin exactly)

- Mark `HEOG_left`, `HEOG_right`, `VEOG_lower` as EOG; the other 30 channels are scalp EEG.
- Band-pass filter the EEG **0.1-30 Hz**.
- Re-reference the EEG to the **average of the mastoid-adjacent electrodes P9 and P10**.
- Epoch **-200 to 800 ms** around stimulus onset, apply a **-200 to 0 ms baseline**, and
  **average all epochs** of each condition (no additional peak-to-peak artifact
  rejection).
- Form the **unrelated-minus-related** difference wave (average of the unrelated condition
  minus average of the related condition), per subject.
- Measure the N400 as the **mean amplitude of the CPz unrelated-minus-related difference
  wave over the 300-500 ms window**, per subject.
- Report the **mean across the 12 subjects** of that per-subject amplitude.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `n400.json` — at minimum `{"n400_difference_amplitude_uv": <float>, "channel": "CPz",
  "window_ms": [300, 500], "n_subjects": <int>}`.
- `run_metadata.json` — dataset id, n subjects, the reference and filter you used, the
  baseline and measurement window, and the event codes entering each condition.
- `findings.md` — a few sentences reporting the unrelated-minus-related N400 amplitude at
  CPz. State only what your analysis supports.

## Failure handling

If the ERP CORE N400 files cannot be resolved, exit non-zero with `failed_precondition`
and a non-empty reason, and still write parseable `run_metadata.json`, `n400.json`, and
`findings.md`.
