# Matched DoSEI observation construction

This source-only streaming core constructs provisional observations for the
adopted `native_marker_relative_30s_v1` condition. It has not been applied to the
authentic EEG projection. It is not a benchmark runner or a new benchmark.

The target is the source's grouped bedside MOAAS responsiveness category 1–5.
Every source-supported assessment marker is retained, including an unresolved
target or an incomplete/all-missing observation. The interval is exactly
`[marker timestamp − 30000 ms, marker timestamp)`. This is retrospective marker
association; a marker has not been proven to identify clinical challenge onset.

`PairedWindowBuilder` receives every authenticated native row sequentially,
before emitting a packet at each matching private assessment event. It keeps
exact relative timestamps, duplicate earlier timestamps, both channels and
source missingness. Conversion-invalid values become null with false masks;
their original approximations and flags remain in the private native source.
Finite hardware endpoints remain visible with explicit endpoint flags. No
filter, resampling, interpolation, median replacement, artificial sentinel or
offline artifact mask enters participant observations.

The same packet and opaque case ID are intended for both access conditions:

- **Viewer-only interpretation:** calibrated plots of the complete two-channel
  packet, with declared scrolling/zoom controls and visible missingness. The
  participant interface grants no raw file, script, numerical detector or
  arbitrary tool execution.
- **Code-enabled interpretation:** the identical packet's numerical values,
  timestamps and masks, with an isolated declared programming/tool interface.

The arm distinction is an enforced delivery/runtime policy, not something this
pure core can enforce. A model with an unrestricted browser or filesystem is not
a qualified viewer-only participant. Direct numerical text would be a separate
declared access condition, not evidence of visual interpretation.

Source recording IDs, absolute times, labels, other annotations, original
filenames and offline artifact masks stay evaluator-private. Case IDs are HMACs
under a private 32-byte key and must be reused unchanged across both arms.
Public delivery order must be frozen independently of recording order; repeated
assessments and nearby windows remain correlated cases, not independent people.
Recording-level identity does not establish independent patients. Neither
patient generalization nor independent-marker uncertainty can be claimed from
these keys. Any permitted training evidence or pretrained tool must be declared
for each arm. Different assistance makes the result a workflow comparison, not
an isolated causal effect of tools. An extra raw-data arm is not a prerequisite
for completing these two declared workflows.

The full driver still must bind accepted native verification and all 171 source
receipts, match every private annotation event, finish each source stream before
publishing provisional cases, freeze the complete case manifest and construct
actual display artifacts and isolated delivery. No biological-person crosswalk
is established, so this implementation creates no person split or trained
baseline. Canonical successor population/scoring remains separately unadmitted;
the historical 7,328-slot scorer must not be used on this source release.

The numeric policy dependency is the reviewed sibling
`source-eeg-numeric-v1/numeric_policy.py`; it is supplied explicitly by the
authenticated cohort driver. This module performs no signal-file reads or model
calls. Generated boundary controls are in `test_paired_windows.py`.

Any rejected or interrupted input permanently invalidates that builder. It
cannot resume with a different row after pruning history. Previously emitted
packets remain provisional and must be discarded from publication if the full
stream fails; the driver must retain a complete failure/coverage report.
