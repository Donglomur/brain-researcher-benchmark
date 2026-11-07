# Spatial source composition

This source defines Stage2 transport, a separately named portable training-only
operator comparator, and protected grading. It does not establish a fitted
result, execution readiness, optimizer competence, native MATLAB parity or
scientific qualification. The five modules in `vendor/` are exact captured
copies of the prior reviewed source; `VENDOR_LOCK.json` records their original
paths and exact hashes. Review of this composition is separate from review of
those earlier equations. The parent must authenticate this entire source
directory, including the lock, before loading it from an immutable snapshot.

The complete selected scope is nine participants, 433 native electrodes,
eight conditions, 3,464 electrode-condition cases and 10,392 parameter vectors
per panel. All four panels are required: `reproduction_A`, `reproduction_B`,
`corrected_A`, `corrected_B`. Access conditions do not create extra benchmarks.
The historical 366-electrode quality mask, raw preprocessing, source permutation
fits, whole-paper results, native fitting and missing recorded gain-sign
provenance remain unresolved. No score cutoff silently promotes this program.

## Corrected producer API

`baseline.fit_context(context, rows, roster_sha256, *, limits, clock,
solver=None)` returns `(canonical_output_bytes, audit)`. Production omits the
solver argument. The injection hook exists solely for invented solver-control
tests; an injected solver cannot receive a production qualification receipt.
`clock` must use the controller's monotonic clock. `limits` contains exactly:

- `origin`: original absolute context origin, including capture/preparation.
- `deadline`: finite absolute deadline on the same clock.
- `max_forward_calls`: positive integer shared by the complete context.
- `max_residual_calls`: positive integer shared by the complete context.

The parent separately enforces hard wall/CPU/memory/storage limits, source
custody, process cleanup and complete receipts. This library checks deadlines
between operations; a Python call cannot interrupt blocked native BLAS work.
The parent freezes equal candidate/comparator context envelopes before numeric
exposure. There is no default wall-time or process-memory qualification here.

`rows` is the complete operator-bound 3,464-row public parameter roster; it
contains metadata, not another participant's responses. `context` has exactly
`participant`, `role`, `response_indices`, `signals`. Role is `full`,
`train_first`, or `train_second`; original zero-based indices are respectively
0..74, 0..37 and 38..74. `signals` has all four released signal keys. Each value
contains exactly:

- `responses`: native float64 ndarray `[native_electrodes, training_samples]`.
  Only that role's responses exist in this process. All original source nonfinites (NaN and either infinity)
  remain for the fixed finite-support mask.
- `aperture`: float64 `[100,100,75]`, preserving signed nonbinary values.
- `aperture_identity`: exact 64-hex SHA256 bound by authenticated typed ingress.
- `band`: the exact source band, including `FaCLbBW` for p10/p11 corrected alpha.

Parent ingress owns aperture identity validation, including both p05 apertures.
Repeated identities must also have exactly equal arrays before this code reuses
a basis projection. Full apertures contain permissible query covariates; held
response samples never enter half-role seed scoring, normalization or fitting.
Stage2 uses fixed released timecourses, never a candidate Stage1 output.

There are 27 fresh participant-role contexts for each corrected panel and for
the operator comparator. Full-role state, learned means, seeds and predictions
must never cross to half roles. A function call does not supply that isolation;
the parent launches separate restricted processes. Saved public fits and
private reference arrays are absent from these producer contexts.

Output schema is `visual_alpha_context_parameters_v1`, with
`roster_sha256`, `participant`, `role`, and `cases` containing exact `case_id`
and five `parameters`. `contracts.admit_context` enforces the complete context
bijection and original source bounds. `contracts.assemble_contexts` requires
exactly all 27 `(participant, role)` byte payloads and assembles the original
`visual_alpha_parameters_v1` full/first/second submission. Candidate `S=0` and
`GR=1` remain admitted explicit unsupported endpoints; they are never repaired.

## Operator method and resources

`ALGORITHM_PROPOSAL.json` freezes the source-shaped grid, role training-only
analytic gain/DC objective, four starts, SciPy settings and explicit numerical
guards. The method is `visual_alpha_trainonly_sourcegrid_varpro_scipy1171_v1`.
It is a prospective portable adaptation, not the historical optimizer. The
closest native alternative would rerun the author MATLAB routine with seeds
derived exclusively from training samples; that alternative is unqualified.

All 3,969 fixed in-bound OG grid entries are evaluated; exact duplicates retain
their original ordering. The best four distinct geometries generate all 72
GS proposals. Both mandatory generic starts and two distinct selected starts
run. Finite `status=0` evaluation-limit results are recorded as such, without
claiming convergence. Any failed start, unsupported numerical trial, deadline,
or call limit fails the complete context. Remaining starts are explicitly
`not_entered`; no successful subset becomes a result. All-nonfinite training cases
remain as `S=0` unsupported records and make complete aggregation unavailable.

The gain arithmetic scales centered training vectors before dot products;
finite tiny Gaussian tails cannot silently become a zero denominator. A
nonzero SSE that is unrepresentable in float64 causes typed refusal, including
during grid selection. Such seeds are not discarded. Training DC removal is a
nuisance objective; it is distinct from evaluator centering of held test folds.
No fitted intercept is added to the returned model.

`baseline.prospective_resources(person, role, distinct_apertures=...)` derives
array sizes, projection multiply-add pairs, shared forward/residual caps and
four-start/500-NFEV limits from metadata. The actual distinct aperture count
must come from authenticated identities. Defaults conservatively allow four;
ordinary shared apertures permit one cached grid, and p05 can require two.
Each cache remains within its one participant-role context and contains only
input-derived basis projections. Kernel blocks have 16 columns (1.28 MB at
100x100), avoiding a dense 317.52 MB complete kernel matrix. The block result
uses the same source formula; changed BLAS summation order prevents a bitwise
parity claim. A focused signed/nonbinary toy agrees with scalar source math and
an independent pixel sum at rtol/atol `5e-14`.

Dynamic geometries depend on training responses and cannot be reused across
roles. Array formulas exclude Python, BLAS and allocator workspaces, so they
are not complete RSS bounds or an empirical runtime forecast. If the operator
cannot support the unchanged full cohort and four-start cap, the program stays
unqualified rather than shrinking the scientific task.

## Protected grading API

`grading.grade_panels(candidate_raw_by_panel, persons, roster_sha256, *,
capture_operator_baseline, expected_baseline_pin, load_person)` first validates
all cases of all four candidate byte payloads. Only then may it capture and
authenticate the sealed complete operator baseline payload. Only after that
admission may it call `load_person(participant)` for private arrays. Candidate
fields cannot supply a baseline score, parameters, branch choice or gain.

The operator's source, algorithm and budget are frozen before data exposure;
the independently executed baseline output is sealed before protected grading.
Baseline execution may occur after candidates. A content hash alone cannot
prove source independence, execution chronology or training isolation. Those
claims require the parent's process/source receipts.

`persons` is ordered metadata with `participant` and `electrode_ids`.
`expected_baseline_pin` has exactly `bytes`, `sha256`. The trusted baseline
callback returns exact bytes in original `visual_alpha_parameters_v1` schema.
`load_person` returns a dictionary with exactly:

- `participant`: requested native participant.
- `signals`: all four keys, each containing `responses` float64 `[n,75]` and
  its correct `aperture` float64 `[100,100,75]`.
- `references`: all eight condition keys, each containing
  `published_xval_percent` float64 `[n]`, `native_branch_verification`
  (`verified` or `unverified`), and `native_parameters`. The latter is `None`
  when unverified. When verified, it maps all three roles to float64 `[n,5]`
  after the existing source-supported seven-to-five conversion. An unavailable
  conversion (`native_five` returned `None`) uses an explicit all-NaN five-vector
  sentinel; any such role leaves that case's native baseline null. Partially
  nonfinite and infinite native rows are refused. This is transport of an
  unavailable native result, not a new fitted result or case exclusion. A filename
  cannot establish `noneggain`; only authenticated recorded provenance can.

Reproduction reports preserve the original saved-published-xval comparison.
An unknown native gain branch leaves native same-formula scores/gain null.
Corrected comparisons use the separately sealed portable comparator. Source
fold-centered CoD and literal uncentered paper Eq6 remain distinct percent
endpoints; changes are percentage points. The primary corrected endpoint is
equal-person mean gain for `corrected_alpha__GS__positive_gain`. All eight
conditions and complete native cohorts are retained. Any undefined electrode
propagates unavailability; no candidate-dependent case omission is allowed.

`private_cases` contains per-case metric dispositions and geometry and belongs
only to private operator output. The report always says qualification false.
Publication decisions and complete-program gates remain outside this library.

## Source controls

`test_controls.py` uses invented numerical/metadata inputs, including full
case-identity transport and late invalid candidate refusal. It never loads
scientific inputs, imports SciPy, invokes a real optimizer, or runs a scientific
score. The four-start test uses a host stub returning its supplied initial
point. Small forward evaluations verify equations and unsupported boundaries;
they are correctness controls, not neural-data experiments.
