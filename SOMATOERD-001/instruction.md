# Total beta-power change in one somatosensory MEG recording

## Scientific target

Estimate the descriptive change in total 15–30 Hz trial power for four fixed
sensors in MNE somato subject sub-01. This is a paper-derived **method control**,
not a numerical reproduction of an original paper's finding. The anchor is
Pfurtscheller & Lopes da Silva (1999), *Clinical Neurophysiology* 110:1842–1857,
section 3.1 and Figure 3: calculate power per trial, average trials, then express
change relative to reference power as `100*(A-R)/R`.
[Original review](https://doi.org/10.1016/S1388-2457(99)00141-8).

Total trial power includes phase-locked and non-phase-locked activity. It is not
isolated induced power or the power of the trial-average waveform. The result may
have either sign: a negative value means lower power relative to baseline.
Do not infer population effects, precise onset, or cortical/contralateral
localization from this fixed sensor readout. Baseline rhythmicity is not separately
validated here. The custom Morlet settings, sensor set and windows below are not a
claim that the review used these data or reproduced this exact number.

## Offline original data

Use `/app/data/somato/sub-01/meg/sub-01_task-somato_meg.fif` and its supplied
sidecars. The original OSF MNE-somato-data archive, version 8, is hash-pinned and
selectively staged at image-build time. The archive's dataset metadata identify
Lauri Parkkonen and the PDDL dedication. Acquisition and per-file hashes are in
`/app/data/somato/data_manifest.json`; the executable method specification is
`/app/method_contract.json`. No runtime downloads are needed or allowed. Keep
the original sample clock, units and source events; do not replace the data.
The archived conversion script reads the upstream `sef_raw_sss.fif`; this is a
released, already processed recording, not untouched instrument output. Its
header records approximately 0.1–100.1 Hz acquisition/source passbands. We do not
rerun or claim to independently validate the upstream SSS processing.

## Public estimator contract

The following choices define this method case, not a hidden estimator:

1. Read the FIF in float64. Discover `STI 014` onset events using the exact
   `find_events` settings in the method contract. Keep a ledger of every discovered
   event, including non-target events; analyze event code `1` only.
2. Construct epochs from −1.5 to +1.5 s, inclusive, on the original sampling grid.
   Use all original gradiometers while applying source SSP projections, then select
   `MEG 1342`, `MEG 1343`, `MEG 1332`, `MEG 1333`, in that order. No extra filtering,
   resampling, detrending, voltage baseline correction, interpolation, amplitude
   rejection or hand-selected trial exclusions. Source annotation and boundary
   rejection remain active. Fail if a readout sensor is absent, source-marked bad,
   or has nonfinite retained data. Keep original bad-channel/projector metadata.
3. Compute Morlet power for every retained trial and selected sensor at integer
   frequencies 15 through 30 Hz, `n_cycles=frequency/2`, `zero_mean=True`,
   `use_fft=True`, `decim=1`. Use MNE 1.12.1's discrete wavelet normalization
   (complex L2 norm √2) and centered, linear zero-padded convolution, not circular
   or reflected padding. Equivalent independent implementations are welcome.
4. For `P[trial,channel,frequency,time]`, compute `A=mean_trial(P)`, then
   `B[channel,frequency]=mean_baseline(A)`, using the inclusive −1.0 to −0.25 s
   baseline. Require finite positive `B`; do not add a floor. Compute
   `100*(A/B-1)` separately for each channel/frequency, then average these percentages
   equally across the four sensors and 16 frequencies. Do not normalize each trial
   first or pool channels/frequencies before normalization.
5. Average that complete percentage timecourse over the inclusive +0.10 to +0.35 s
   window. Select windows using unrounded source times, not rounded CSV values.
   Sample offsets are `round(-1.5*sfreq)` through `round(1.5*sfreq)`, inclusive;
   absolute event/epoch sample indices include the FIF `first_samp`.

The Gaussian temporal standard deviation is approximately 79.6 ms, with wavelet
support extending about 398 ms on each side; epoch endpoints have padding effects.
This temporal smoothing precludes interpreting the first changing sample as onset.
Wavelets centered near the −0.25 s baseline boundary also have support after the
stimulus. The prescribed baseline therefore does not guarantee strictly prestimulus
signal support; this is a disclosed limitation of the fixed-window method case.

## Outputs

Write to `${OUTPUT_DIR}` (default `/app/output`). Numeric CSV values should retain
float64 precision, with one header row and no duplicate/missing keys. Row order is
not graded; membership is. Powers are in `(T/m)^2`. Write these seven files:

- `source_events.csv`: `event_index,event_sample,event_code,retained,drop_reason,epoch_start_sample,epoch_end_sample`.
  `event_index` is the zero-based discovery index; `retained` is 0 or 1. Retained
  events have an empty reason; non-target codes use `non_target_event`. Otherwise
  record the epoch rejection reason. Epoch bounds use the original absolute clock.
- `mean_power.csv`: `channel,frequency_hz,time_index,time_s,mean_power_T2_per_m2`.
  Include the full channel × frequency × epoch-time grid of trial-averaged raw power.
- `trial_windows.csv`: `event_index,channel,frequency_hz,baseline_power_T2_per_m2,target_power_T2_per_m2`.
  Include every retained event × channel × frequency, with raw per-trial power
  averaged over the baseline and target windows, respectively.
- `beta_power_timecourse.csv`: `time_index,time_s,beta_power_pct`, the entire epoch
  curve, not just the target interval. `time_index` is zero-based.
- `erd.json`: `beta_erd_percent`, `band_hz:[15,30]`, the ordered `channels`,
  `window_ms:[100,350]`, `baseline_ms:[-1000,-250]`, and actual retained `n_trials`.
  The historical key `beta_erd_percent` denotes the signed total-power change here.
- `run_metadata.json`: `status`, `task_id`, `source_manifest_sha256`,
  `source_fif_sha256`, `method_contract_sha256`, `sfreq_hz`, `first_samp`,
  `n_source_samples`, `n_discovered_events`, `n_trials`, `n_epoch_times`,
  `source_bads`, `n_source_projectors`, `software_versions`, and `method_contract`
  containing the supplied method-contract JSON object. Hash the supplied files'
  bytes, not a reserialized object. Set successful `status` to `ok`.
- `findings.md`: briefly state your measured signed result and its single-recording,
  total-power and sensor-level limitations. No mandatory wording or hidden keywords.

## Verification and failure handling

Reward is binary. The verifier checks complete source membership, original power
receipts and consistency of all aggregations; a plausible headline or correlated
curve is insufficient. For raw powers, the tolerance is
`abs(submitted-reference) <= 1e-8*reference_baseline + 1e-6*abs(reference)`
using the corresponding channel/frequency baseline. Time tolerance is 1e-9 s;
percentage arithmetic tolerance is 1e-6 percentage points. Integer membership is
exact. These numerical tolerances are not scientific confidence intervals.

If source identity, epoch construction or finite-power requirements fail, exit
nonzero and write parseable `run_metadata.json` and `erd.json` with
`status:"failed_precondition"` and a nonempty `reason`, plus `findings.md`.
Do not invent replacement events, powers, counts or a default answer.
