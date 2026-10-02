# Analysis contract: N170 shifted_ds adaptation

This is an explicitly specified adaptation motivated by ERP CORE's N170
characterization, not the complete paper preprocessing or exact historical
ERPLAB implementation. The estimands are participant-level signed PO8 mean
voltage and a sampled fractional-peak latency of the face-minus-car ERP.

## Source and preprocessing

Use all 37 manifest participants; the released stage has already shifted
events and resampled to 256 Hz. Never infer a new shift from
original_sample_num, and do not reapply the paper's 26-ms correction.

The original 33-channel recording is an external little-endian float32 FDT:
flat element channel+33*time. Interpret stored values as µV using the declared
EEGLAB compatibility convention. Unit fields are absent, not independent proof
of calibration. The reference token common does not establish that the
30-channel analysis reference has already been applied.

Contributing channel order:
FP1,F3,F7,FC3,C3,C5,P3,P7,P9,PO7,PO3,O1,Oz,Pz,CPz,
FP2,Fz,F4,F8,FC4,FCz,Cz,C4,C6,P4,P8,P10,PO8,PO4,O2.
Require these continuous values finite, promote to float64, subtract their
ordinary arithmetic samplewise mean, and exclude the three EOG channels from
reference/rejection. Do not apply ICA, source reject flags, or another filter.

Apply one centered symmetric Hamming FIR with pass edges .1 and30 Hz,
transitions .1 and7.5 Hz, and full length8449 samples. This is MNE1.12.1
firwin/auto/phase=zero semantics, not filtfilt. The kernel is a centered upper
lowpass minus a centered lower lowpass, not a single full-length bandpass
firwin call. Normalize frequency breakpoints [0,.1,30,37.5] by Nyquist128.
For each transition pair a,b: component length=round(3.3/((b-a)/2)), raised to
odd; cutoff=(a+b)/2. Each component is a symmetric Hamming-windowed ideal
lowpass normalized by its DC sum, centered in8449. Upper minus lower has no
subsequent bandpass-gain normalization.

For a segment of n samples, e=min(8449,n)-1. Pad with
[2*x[0]-x[e:0:-1], x, 2*x[-1]-x[-2:-e-2:-1]], treating e=0 as no padding.
Take full linear convolution and slice e+4224 through e+4224+n.
Equivalent overlap-add is acceptable. Short segments keep the full kernel,
which can distort edges; no hidden trimming/minimum-duration exclusion applies.

## Events, selection, and averaging

Preserve every original event row, including non-target events. Normalize a
finite non-Boolean integral number or stripped signed decimal-integer string
to an event code; do not extract digits or parse floating-point strings.
Codes1..40 are faces;41..80 are cars. -99 and stripped case-insensitive boundary
are boundaries; other tokens are documentary, with no implicit BAD-prefix rule.
Invalid target/boundary latency fails the precondition. Documentary nonfinite
values on other fields/rows use {"__nonfinite__":"NaN"}, "Infinity", or
"-Infinity" tags in their JSON cells, never numeric NaN or silently omitted rows.

Target sample=rint(latency-1), ties to even, zero-based. Keep original event-row
order for trial averaging. If target rows share a rounded sample, exclude all
of them as duplicate_target_sample. Boundaries cut at ceil(latency-1), constrained
to0..pnts; deduplicate cuts, add0/pnts, and filter every nonempty interval
independently. Boundary duration denotes removed samples, not a new bad interval
inside recorded data. The current fixed source has no such boundaries or
duplicate target samples; these edge-case rules remain explicit.

Epoch offsets −51..102 are inclusive (154 samples). Selection precedence:
out_of_bounds, duplicate_target_sample, crosses_boundary, peak_to_peak, accepted.
The first three determine geometric eligibility. For each eligible epoch,
record all30 full-epoch max-minus-min values and the pre-baseline PO8 mean.
Reject iff any PTP>150µV; equality is retained. These receipts include artifact
rejects. Subtract each channel's mean over offsets−51..0. Average accepted PO8
epochs per condition with equal weights. An empty condition is undefined,
not zero activity; its storage uses a false mask and exact-zero sentinel.

## Participant measurement

Subtract accepted face minus car, then explicitly rebaseline over−51..0 once
at measurement time. This is separate from epoch baseline removal. Snap
requested endpoints to nearest samples, first index on equal distance:
amplitude110..150ms gives offsets28..38; onset10..150ms gives3..38.
Amplitude is the signed inclusive sample mean. No sign is required.

A local trough must be strictly below both immediate neighbors and both
three-sample side means. Actual padding samples beyond the onset window are
used only to qualify troughs. Select the deepest local trough, earliest on ties;
if none exists, select the earliest global minimum inside the window.
If selected voltage is nonnegative, onset is null. Otherwise walk backward to
the nearest in-window sample >= half the peak voltage. Return that sample's
time, with no interpolation. If none exists, return null, never the window's
left edge. The public measurement_kernel.py specifies all diagnostic nulls.

The independent verifier checks each accepted condition waveform against the
original-source reconstruction. In µV, B(v)=1e-8*maxabs(v)+64*eps64*max(1,maxabs(v)).
Require supnorm error <=B(source) independently for face,car and their
measurement-rebaselined difference. The difference is derived, never separately
submitted. Accepted-waveform peaks/crossings need not match hidden source
scalars: coherent near-tie changes are allowed and expose estimator sensitivity.

Missing source conditions remain missing. If canonical rebaselined difference
maxabs<=64*eps64*max(1,maxabs(source_face),maxabs(source_car)), onset alone is null
with numerical_zero_difference. This public floating-point resolution policy
does not null amplitude; continue accepted-wave amplitude/baseline replay.
The scale floor1 means1µV. For active differences, accepted evidence alone
determines the peak/crossing and any other onset null.

## Group summary and interpretation

Use all37 unrounded participant slots in canonical ID order for each endpoint.
If all are defined, report mean, sample SD, SE, and two-sided95% t(36) interval.
An exactly constant defined cohort has a point CI. If any slot is undefined,
report complete-cohort null mean/SD/SE/df/CI with n_defined and missing IDs.
Do not compute an available-case t36 interval or silently drop participants.

No negative effect, minimum variability, significance, historical trial count,
paper number or reference-bank endpoint is an acceptance condition. This
adaptation lacks the paper's complete ICA/artifact processing and additional
onset lowpass. Fractional-peak latency is a waveform descriptor, not a guarantee
of precise physiological onset. Optional cluster evidence is cluster-level only.
