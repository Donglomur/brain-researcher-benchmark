# Source-bound views and complete-support grading

`views.py` and `scoring.py` are operator-only pure-array modules. The trusted
worker loads admitted primitive NPY arrays through the owner's safe loader;
these modules perform no I/O, native imports, model fitting or source-body
verification. Source descriptors are checked against the supplied arrays for
shape/dtype. Descriptor hashes and complete-support provenance must already be
verified by the owner. No authentic arrays were used in implementation controls.

## View construction

`one_record(acquisition, arrays_by_path, modality, row, time_index, profile)`
and its alias `query_record(...)` return exactly the strict record described
in API.md. `arrays_by_path[descriptor.path]` is a primitive ndarray. The
acquisition follows `filio_i_prepared_v1`; modality is GrC or CF and must be
present. Acquisitions with empty selected `views` or structural absence produce
no query; the complete owner census retains those distinct dispositions. The
helper refuses to invent fields or targets for an outside-selected acquisition.

The owner adds `encoding_binding` only after authenticating a pinned private
admission certificate. It contains:

* `status: authenticated`, `behavior_clock: tmpxx`,
  `rew_pos_clock: reward_aligned`;
* `dtb_seconds`, exactly equal to native `acquisition.dtb_seconds`;
* two identical nonempty `position_units` strings with established meaning;
  unknown/unspecified/arbitrary-unit labels do not pass;
* `event_clock_join`, `omission_clock_join`, `target_grid_join` and
  `trial_axis_join`, all strictly true.

Additional private evidence pins may remain in that binding but never enter
the returned feature record. These flags are assertions by a trusted admitted
caller, not self-authenticating evidence or permission for extraction to guess
units. The helper independently checks increasing finite behavior-clock samples
and uniform spacing against source dtb (rtol1e-9, atol1e-12), full original trial
axes, present cell count, target-grid descriptor dimensions, source outcome
eligibility masks, strict movement length>6, goodMvmt_source and event-derived
measured delay/duration consistency.

`rew_pos` has exactly `[original_trials,behavior_samples,2]`. For sample0 the
two velocities use the forward difference; later samples use the backward
difference divided by source dtb. Speed is the Euclidean norm. CF behavior
center is target time t; GrC center is t minus the source measured event delay.
The nine taps span ±0.4s in 0.1s increments on tmpxx. Interpolation uses only
neighboring finite samples inside native support; missing neighbors or outside
support return `None`. It never jumps across missing samples or extrapolates.
All-missing mandatory position components and infinite values refuse.

The additional movement coordinates preserve source units: movement_duration
is `movement_duration_ms` and movement_length is native `mvlen`. The reference
standardizes them using training-only weights. Event-relative time and measured
delay are seconds, authenticated at admission. No neural sample indices are
equated with behavior indices. No DLC, jaw, licking or additional movement
component is introduced.

`context_categories(acquisition, rewarded)` constructs structural vocabulary
tokens: planned_delay is `format(source_context.Delay, '.17g')`; first_reward_order
is the literal source FirstRew string; reinforcer is water for collection water,
otherwise literal source DAType; delivered_outcome is delivered or omitted.
The owner uses this same convention in its pre-fit complete structural census.
No category vocabulary is inferred from targets or favorable training rows.

Query construction reads target-time coordinates and shape metadata, and never
looks up `modal.targets.path`. It can operate with every neural target body
absent from `arrays_by_path`. M output contains only `movement`; C contains only
time, measured_delay and categories; combined profiles contain their union.
Private row/time arguments select the local record but are absent from its
contents. All profiles retain the same private target support.

`training_view(acquisition, arrays_by_path, modality, rows, profile,
cell_indices=None, permutation=None)` returns X, Y, weights, training_mean,
private_index, cell_indices, profile, requires_private_transport_permutation
and null_ineffective_singleton_rows. Rows are the exact nonduplicated training
rows authenticated/purged by owner lineage partitions. Optional cell_indices
support per-cell fitting; they do not authorize dropping final query cells.
Default is the full original present cell axis.

Y is `[training_trials*full_native_time, selected_cells]`; order is supplied
trial order then full native time. Weights are 1/(trial_count*time_count), so
each trial and its time bins have equal weight. Target bodies are indexed to
the supplied training rows before finite validation or moments; held-out rows
never affect those operations. A nonfinite required training target refuses
without dropping a cell, time or trial. training_mean is the weighted overall
training cell mean, suitable for the fold-specific R² diagnostic.

CM-shuffled requires an explicit source-row integer permutation, bijective on
exactly those training rows and confined to the four discrete source category
fields. The acquisition is already fixed by this call. Labels are reassigned
as complete trial×cell×time blocks before flattening. Paired-modality physical
trial joins and reuse of the same permutation are authenticated by the owner;
the helper does not generate seeds, infer pairings or receive query labels.
Other profiles reject permutation arguments. The exact mapping is not returned
in features or metadata. Singleton source strata are explicitly ineffective.

X order and private_index are operator staging data. The owner must independently
permute opaque training transport records and strip private_index/source order
before candidate exposure, particularly for M. It also seals actual permutation
receipts privately and provides the reference fitter's minimal attestation.

## Grading interface and hierarchy

`grade(expected_support, truths, predictions, training_means=None)` accepts a
sealed complete private query-record list and exact token→finite ndarray
maps. Every ndarray is the full ordered cell vector for one local query.
Required support fields are token, modality, acquisition, session, animal,
physical_trial, fold, time_index, time_count and cell_tokens. Identifiers are
opaque authenticated keys, never in candidate features. Optional stratum must
be provided consistently and contains reinforcer, planned_delay and
delivered_outcome. The owner preserves the complete native census, absence
dispositions and alias evidence separately from this query support.

The grader requires exact token sets, unique physical coordinates, stable full
cell/time axes per acquisition, all time bins of every trial, consistent
acquisition→session→animal joins and shared physical-trial identity/fold across
modalities. A duplicated alias, incomplete trial, missing/extra vector,
nonfinite target/prediction or unscorable arithmetic refuses the complete
profile. The sealed support's completeness relative to the source census is
the owner's admission responsibility; the grader cannot infer absent complete
trials from a truncated list falsely declared complete.

Within each cell it averages squared error across all native time points in a
trial, then equally across all held trials pooled over folds. It averages cells
within acquisition, acquisitions within session, sessions within animal and
animals within modality. RMSE is the square root of that hierarchical MSE.
GrC and CF remain separate; there is no combined-unit scalar. Empty complete
modality support is explicitly unavailable and does not become zero error.
Full per-trial/cell/acquisition/session/animal diagnostics and denominators are
returned, with the same hierarchy for every observed declared stratum.

If training_means are provided, their token set is exact and their full cell
vector must be constant within each acquisition/modality/outer fold. Signed
cell R² is 1 minus pooled squared-error sum divided by pooled squared-error
sum from that fold's training-only overall cell mean. Its hierarchy is the
same. A zero-denominator cell yields an unavailable diagnostic through the
affected hierarchy; primary MSE support remains intact. The grader cannot
prove the means were fitted on training rows, so the owner binds their fit
lineage before unsealing query truth.

`reference/views_scoring_controls.py` runs one small invented pure-array
control batch. It tests missing neural query bodies, exact clock shift and
velocities, boundary masks, profile masks, whole-trajectory reassignment,
omission/unit gates, held-target exclusion, uneven hierarchy sizes/folds,
signed and undefined R², exact support and alias/identity failures. It performs
no fit and stores no numeric arrays. Receipts preserve the exact tested source
pins; passing controls establishes engineering behavior only.
