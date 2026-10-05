# Response-locked FCz contrast in one ERP CORE participant

Compute the signed error-minus-correct mean voltage at FCz over 0–100 ms
after the button press in participant 001's Flankers recording. This is an
**easy, single-person computational adaptation**, not a reproduction of the
ERP CORE paper's group ERN finding or exact processing pipeline. A positive,
negative or near-zero result is acceptable if the data support it.

## Data and scope

The unchanged files of MNE's modified ERP CORE release are already available
at `/app/data/errmon`. Use `ERP-CORE_Subject-001_Task-Flankers_eeg.fif`.
`source_manifest.json` gives the exact OSF version, archive/member hashes and
license provenance; `README.txt` retains the upstream CC BY-SA 4.0 notice.
Analysis must run offline. Do not fetch a newer copy or substitute a dataset.
The `ERRMON_DATA_DIR` override may identify the same verified bundle locally.

This release contains 30 EEG and three EOG channels at 1024 Hz. Its historical
reference is marked as applied but not named; the precise export/processing
history is not established. Treat it as released, modified data, not unprocessed
acquisition or the paper's final analysis data. Absence of BAD annotations does
not establish absence of artifacts. Do not infer a population effect from one
person's trials.

## Public analysis contract

Read `/app/method_contract.json`: it supplies the complete recipe, channel and
event lists, sample conventions, output schemas and numerical tolerances. The
following summarizes it; no undisclosed estimator or effect-direction rule is
required. Equivalent numerical implementations are welcome.

1. Keep an exhaustive annotation ledger. Decode the six named stimulus/response
   descriptions explicitly, rather than assuming the order of automatic event
   codes. Pair each stimulus with its first response strictly after it and before
   the next stimulus. Preserve unanswered stimuli, extra and orphan responses;
   never borrow another trial's response. Define error from target versus response
   hand, not flanker compatibility. Do not impose an RT cutoff.
2. Use the stored FIF voltage calibration, then convert volts to microvolts
   once. Exclude the three EOG channels and subtract the simultaneous mean of
   exactly the 30 EEG channels. No interpolation, SSP or extra channel rejection.
3. Filter the uninterrupted continuous EEG at 0.1–30 Hz using the public
   symmetric Hamming FIR recipe: transitions 0.1/7.5 Hz, 33,793 taps, one-pass
   zero-phase delay compensation and limited odd-reflection padding. This is
   `MNE 1.12.1 Raw.filter` with explicit FIR/firwin settings, not `filtfilt`.
   The contract also gives a library-independent kernel and alignment formula.
   Filtering and this fixed linear reference may be applied in either order.
4. Use one common response-locked epoch support: sample offsets **−256 through
   563 inclusive** (820 samples, requested −0.25…0.55 s). Export the full FCz
   epochs **before** baseline correction. Boundary-incomplete pairs remain in
   the trial ledger but not the epoch array.
5. For each retained epoch, subtract its mean over offsets **−204…0 inclusive**
   (−0.2 ≤ time ≤ 0 s, 205 samples). Measure offsets **0…102 inclusive**
   (0 ≤ time ≤ 0.1 s, 103 samples). Zero is included in both windows. Average
   trials within each condition and report **error minus correct**, retaining
   the sign. Use no ICA, additional artifact/amplitude rejection, detrending,
   resampling, imputation or stimulus-delay adjustment.

The fixed-source header/annotation preconditions are public. Unexpected bad
channels, projectors, boundary annotations or ambiguous mapped-event ties must
produce an explicit failure, not a silent processing change. An honestly empty
condition has an undefined contrast, not an invented voltage or trial.

## Outputs and scoring

Write to `${OUTPUT_DIR}` (default `/app/output`). Exact fields and null rules
are in the public contract:

- `annotations.csv`: every original annotation, its sample, meaning and disposition.
- `trials.csv`: every stimulus, response pairing, label, epoch status, baseline and
  pre-/post-baseline window means.
- `response_epochs.npz`: non-object arrays `stimulus_annotation_index`,
  `sample_offset`, `fcz_prebaseline_uv` for every retained trial and sample.
- `fcz_waveforms.csv`: complete error, correct and difference waveforms with
  integer offsets and seconds.
- `ern.json`: retained counts, signed condition means and contrast.
- `run_metadata.json`: source/method identities, header facts, counts, actual
  software versions and warnings.
- `findings.md`: a short account of what this one-person adaptation supports.
  No particular wording, effect direction or significance claim is required.

Keys must be unique and complete. Coherent row/column/axis reordering, harmless
extra fields and numerically equivalent serialization are accepted. Do not use
object arrays/pickles, interpolate away missing samples or guess units. Source
epochs are checked within `1e-6 + 1e-6*abs(reference)` microvolts; derived voltage
quantities are recomputed from **your submitted epochs**, with
`1e-8 + 1e-6*abs(recomputed)` tolerance. Time tolerance is 1e-9 s. These checks
do not impose a separate hidden target amplitude, sign or waveform correlation.

Reward is **binary**: 1 for complete source fidelity and internal consistency,
otherwise 0. There is no proportional partial-credit claim. On a source or
precondition failure, exit nonzero and write parseable `ern.json`,
`run_metadata.json` and `findings.md` containing `failed_precondition` and a
nonempty reason. An unavailable-input report is not a successful solution.

## Paper connection

[Kappenman et al. (2021), ERP CORE](https://doi.org/10.1016/j.neuroimage.2020.117465)
characterizes the ERN at FCz and recommends the 0–100 ms measurement window
(Tables 1–2). Its ERN analysis retained 36 participants and used a different
reference, baseline, filter and artifact-processing pipeline. Here, only the
component/measurement idea and public recording are reused; average reference,
the immediate pre-response baseline and this explicitly fixed filter define a
separate descriptive adaptation. [Public resource](https://erpinfo.org/erp-core).
