# Distinguishing left- vs right-hand motor imagery from EEG (EEGMC-001)

## Scientific context

Motor imagery — imagining left- vs right-hand movement — produces **lateralised** changes in
sensorimotor EEG rhythms (mu/beta), and identifying which EEG features distinguish the two
conditions is a standard analysis underlying motor brain–computer interfaces (Schalk et al.,
2004, *IEEE TBME*, https://doi.org/10.1109/TBME.2004.827072).

## Task

Using the PhysioNet EEG Motor Movement/Imagery dataset via MNE
(`mne.datasets.eegbci.load_data(subject=1, runs=[4, 8, 12])` — the left-vs-right-fist imagery
runs; read with `mne.io.read_raw_edf`), set an **average reference**, epoch the two conditions
(annotations `T1` = left, `T2` = right), and compute **band power per channel × frequency**.
**Test which channel×frequency features differ between left and right imagery**, and report the
significant features.

The standard analytic choices the analysis leaves to the analyst (epoch window, frequency
resolution, test) should follow common practice.

Report, in plain terms, **which EEG features distinguish left- from right-hand motor imagery on
these data** — stating only what your analysis actually supports.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `differences.json` — `n_tests` (number of channel×frequency features tested), `n_significant`
  (the number you conclude **significantly differ** between conditions), `n_channels`,
  `n_epochs_per_condition`.
- `run_metadata.json` — dataset, channels, reference, band range, the test used, analytic choices.
- `findings.md` — a short written summary of which features distinguish the conditions. State
  only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `differences.json`, and `findings.md`.
