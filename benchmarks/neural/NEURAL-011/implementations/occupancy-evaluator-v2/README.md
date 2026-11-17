# Siena complete-recording alarm occupancy companion

This operator evaluator adds the predicted-positive time fraction requested by
the current NEURAL-011 understanding contract. A brief detection and an alarm
covering an entire short recording can both receive perfect tolerant event F1.
The companion makes their different time burdens explicit and automatically
scores always-negative and always-positive decisions on the identical complete
recordings. It does not alter the primary endpoint or select a new threshold.

`siena_occupancy.py` loads the preserved `initial-evaluator-v1` evaluator and
source inventory by relative path, verifying both SHA256 pins before use.
All existing complete-patient, vector, channel, frozen-artifact and leakage
validation remains in force. Original event metrics, their rounded 10 Hz time
denominator, defined-only F1 aggregation and paired F1 exclusions are unchanged.
The implementation depends only on the existing NumPy installation.

## Definitions and denominators

Each score covers `[i/fs, (i+1)/fs)` seconds and is positive when it is greater
than or equal to the frozen threshold, normalized to a finite float exactly as
in the preserved event scorer. Recording occupancy is positive sample
count divided by the complete sample count. Positive seconds are positive count
divided by `fs`. This is measured before event merging, splitting, tolerance
extension or scorer rounding. The new `observed_duration_seconds` is exactly
`n_samples/fs`; the preserved `duration_seconds` remains the event scorer's
rounded duration. These fields can differ for noninteger 10 Hz support.

Within a patient, positive seconds and observed seconds are summed across every
publisher-listed recording before division. `patient_macro_predicted_positive_time_fraction`
equally averages all selected patient fractions. `pooled_predicted_positive_time_fraction`
uses total positive seconds divided by total observed seconds. The companion
retains patients whose event F1 is undefined; `occupancy_patients` and
`occupancy_undefined_patients` explicitly report its support. Mixing sample rates
does not reweight a patient by sample count.

For a paired comparator, its own frozen threshold is applied. The report gives
candidate-minus-comparator occupancy differences for every selected patient and
their equal mean, separately from the existing F1 bootstrap. No new uncertainty
claim or alarm-burden acceptance cutoff is inferred. Lower occupancy alone is
not better seizure detection; read it together with sensitivity and event F1.

The constant controls are fixed decisions, generated with 0/1 scores and a 0.5
threshold solely to express always-negative/positive support. They are not
fitted reference models, and they are not chosen using evaluation labels.
Both carry the native event metrics and occupancy over the same complete cases.

## Operator use

Use the existing v1 reference fit/predict path to obtain frozen artifacts and
complete prediction arrays. The companion accepts the same operator-private
manifest and arrays:

```sh
python siena_occupancy.py private-manifest.json predictions.npz frozen.json report.json
python siena_occupancy.py private-manifest.json predictions.npz frozen.json report.json \
  --comparator-predictions timing.npz --comparator-frozen timing-frozen.json
```

The report includes reference events inherited from v1 and is operator-private.
Do not deliver it, its source manifest, or targets to a participant. This adds
no direct-observation, typed-viewer, tool-assisted investigation or protected
frozen-program access condition. It remains restricted to the previously
implemented within-Siena reference artifacts; it does not admit arbitrary
candidate models or CHB-to-Siena transfer.

## Evidence and limits

The tests use generated software fixtures only. They distinguish perfect event
credit with 0.5% versus 100% alarm occupancy, verify unfilled short gaps, exact
sample support, mixed-rate/mixed-duration patient aggregation, background-only
patient inclusion, frozen thresholds (including large JSON integer thresholds),
mandatory constant controls and existing rejections. They do not measure Siena
detector performance.

No authentic EEG was acquired or prepared for this revision. Full payload/header
authentication, calibration and channel-role selection, clinical clock
adjudication, full 14-patient execution, competent references, protected
participant delivery and scientific qualification remain unresolved. Current
task/understanding files are preserved; their integration update is a separate
proposal. This is a substantive scoring companion, not benchmark readiness.
