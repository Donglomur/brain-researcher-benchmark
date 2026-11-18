# Matched calcium input controls

NEURAL-026's measured-target score can improve because a candidate models the
retrospective context better. Such a gain alone does not establish use of calcium
observations. This operator component constructs the missing explicit input
views for a separately admitted candidate ablation study. It does not fit,
execute or score a candidate, change the existing primary metric, or qualify
the benchmark.

`build_control(packet, design, case_id, mode, max_array_working_bytes=...)`
returns one complete packet and private operator metadata. All 50 cases remain
in the original design. A caller constructs one case/view at a time; a
participant must never receive the complete design or another fold's training
labels, because those labels overlap its query angles.

The views are:

- `full`: independently capture all original arrays without changing values.
- `context_only`: replace both training and query calcium (`train_x`, `query_x`)
  with constant zero arrays of the original geometry and dtype. Retain the
  original nuisance fields, training angles, trial order and LR targets exactly.
- `training_trial_shift`: apply the original protocol's nonidentity cyclic
  rotation by `floor(n/2)` within each training LR stratum to **whole training
  calcium trials**. Leave query calcium, nuisance inputs, angles and all IDs
  unchanged. This reproduces the existing input-disruption rule, not a shuffled
  label, prediction or within-trial time series.

The fixed source is the existing `delivery-source/public/protocol.py`, pinned
to SHA256 `cb485a93af96ca7fc1c56da596a6e0ad174a3a349cd66bc938fc8de752c46621`.
Its complete design and packet validation run before any view is returned.
The selected case's complete train/query IDs must match the packet. The builder
rejects extra fields such as query angles, arbitrary subsets, unsupported
controls and nonfinite observations. It preserves primitive array widths,
including widths above eight bytes, rather than assuming the original parser
accepted only float64. Input arrays are never changed. Returned arrays own their
memory and are marked read-only as an accidental-mutation guard, not a sandbox.

Metadata binds every original and transformed array's C-order bytes, dtype and
shape, plus the training permutation. It remains operator-only. Hash consistency
does not establish source authenticity, execution provenance or a protected
evaluation. The working allowance is checked before packet copies against a
conservative incremental NumPy-array envelope (twice the actual packet byte
extent plus one MiB). The caller's original arrays, interpreter/library memory
and native allocator behavior still need separate execution admission. No OS
memory cap or full-scale resource qualification is claimed here.

For a matched candidate study, freeze the same candidate code, initialization,
model-selection rule and resource budget before any held-out response is
accessed, then refit independently in each view. The candidate should receive
the ordinary single-case ABI without this private control receipt. Zeroed
inputs are necessarily recognizable; these are explicit input interventions,
not a blinded manipulation. Observe actual execution and expenditure externally.
An unchanged candidate may fail on a zero-input condition; retain that failure,
without quietly changing its algorithm or support.

Use the existing measured-target scorer on all complete output panels against
the same independently frozen nuisance comparator and target binding. Report
full-versus-context and full-versus-shifted contrasts descriptively alongside the
unchanged fixed-nuisance gain. A training-only shift is one diagnostic and can
produce distribution differences; it does not identify causality or exhaustive
conditional neural information. No statistic, threshold or inferential claim
is added by this builder. Source preparation, full-cohort authentication,
matched candidate execution, target custody and ablation grading remain open.

`test_controls.py` checks only generated in-memory observations, including a
separately written whole-trial permutation oracle, byte-preserved context and
targets, input ownership, complete support, forbidden query labels and
pre-copy resource refusal. These controls are not neuroscience results.
