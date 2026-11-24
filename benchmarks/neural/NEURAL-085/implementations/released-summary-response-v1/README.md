# Complete released-summary numerical observations

This source component prepares NEURAL-085's existing candidate summary views
for restricted numerical observation and collects complete immutable replies.
It validates every selected job before exposing any observation: all18 original
people, five text folds and nine information arms (810 jobs), preserving13,302
query presentations per arm. Source files, original cohort/splits, query targets
and the registered matched NTGE log-loss scorer are unchanged.

These are released sentence summaries, **not raw EEG**, cleaned waveforms or
scalp maps. This package does not provide a model/provider transport, no-tools
enforcement, an adaptive actor, process isolation, qualified source data or a
scientific result. Complete serialized source output is not evidence that a
model received, retained or understood it.

## Preserved information

`PreparedJob` consumes exact already-prepared candidate `training.json` and
`query.json` bytes emitted by the shared ZuCo `Engine.chain`, plus an independent
issuer binding frozen before participant exposure. It rejects reference/control
views, raw/cleaned waveforms, `band_spatial` and other feature ABIs. The latter is
currently an N085 feature alias but remains a separately declared condition.

All rows, their order, literal text, numerical values and nulls survive. Every
training label, positive weight and person/item grouping relationship survives;
all17 training people must have both labels. The output replaces opaque row and
group IDs with local aliases. Original IDs, identity/source hashes, held-person
administration, source paths, reference-only raw records, protected control
observations and query labels stay operator-private. Training labels are
permitted demonstrations, not query targets.

| Arm | Exact feature blocks |
| --- | --- |
| TEXT | text |
| GAZE | gaze |
| EEG | eeg; nuisance with eeg_support only |
| TEXT_GAZE | text, gaze |
| JOINT | text, gaze, eeg |
| NUISANCE | full nuisance |
| NTG | text, gaze, full nuisance |
| NTGE | text, gaze, full nuisance, eeg |
| NTG_SHUFFLED_E | text, gaze, full nuisance, source-shuffled eeg |

EEG retains840 source-ordered values (eight bands ×105 channel slots); it is
never reduced to eight scalp means. Gaze retains12 slots: mean/valid-fraction
pairs for FFD, GD, GPT, TRT and nFixations, then omission rate and sentence
duration. Full nuisance retains840 EEG-support flags,12 gaze-missing flags,
source word-slot count and five gaze-valid fractions. Masks are checked against
available values; missing amplitudes are not reconstructed. No channels, names,
units, topography, normalization, imputation or extra masks are invented.

Two complete JSON frames preserve the engine's availability schedule:

1. Calibration contains every training row.
2. Inference contains the same complete training array plus every query row.

The repeated training copy is deliberate. The engine exposes the complete query
file after fitting, not one query row at a time. This adapter's phase boundary
records frame issuance only; it cannot attest to an actual fit or frozen model
state. The participant must receive the full frames and retain the declared
context. This version implements no cropping, selective retrieval, pagination,
compression, feature averaging or rolling context.

## Operator interface

Use a trusted operator process; never give a participant the Python objects,
issuer bindings, private receipts or original byte captures. Construct every
job with already-bound bytes and a finite shared capacity specification:

```python
job = PreparedJob(training_bytes, query_bytes, issuer_binding, capacity,
                  measure_complete_context_tokens)
```

The issuer binding has exactly `training` and `query` byte/SHA256 pins (no
paths), `identity_sha256`, `training_census_sha256` for the ordered training-ID
list, and the exact ordered `query_ids`. A pin authenticates supplied bytes;
it does not independently prove that an issuer selected the complete source.
Deriving bindings from a participant's chosen subset invalidates the experiment.

`capacity` has positive integer limits `input_bytes` (whole-condition sum),
`condition_transport_bytes`, `frame_bytes`, `job_retained_bytes`,
`job_retained_tokens`, `condition_tokens`,
`response_reserve_bytes_per_job`, `response_reserve_tokens_per_job`, plus a
nonempty `token_measurement_id`. Observation byte counts are exact. Transport
and retained-byte accounting include the declared response reserve. Each reply
reserve must cover a conservative ASCII wire bound for all probabilities; the
token reserve must be at least that bound too. These source bounds do not
qualify a provider's framing/tokenization behavior.

The required token callback measures the **complete two-frame context**,
including the host prompt/framing it intends to use; the source then adds the
response reserve. Actual final nonce and alias bytes are already in the measured frames; no
smaller template is measured. There is no default token estimate. The measurement is
explicitly operator-supplied and provider-unqualified. Context/memory limits,
output framing and actual provider behavior need independent qualification.
Encoded bytes fitting a cap do not establish feasible retained model context.

Freeze an independent list of all810 issuer bindings, then stream prepared jobs:

```python
condition = Condition(prepared_job_iterator, frozen_810_bindings, capacity)
preflight = condition.preflight_operator()  # operator only

# Reload an immutable input capture; revalidation must match initial preflight.
job = condition.open(training_bytes, query_bytes, issuer_binding,
                     measure_complete_context_tokens)
calibration_bytes = job.calibration()  # participant frame1
inference_bytes = job.inference()      # participant frame2, retains training
job.answer({"session": session_token, "token": query_token, "p_tsr": 0.5})
# Repeat exactly once per query, then:
collected = condition.collect(job)     # operator only; restores original IDs
```

No job can issue frames before the complete condition passes. Condition admission
validates every real prepared job and its frame/receipt pins, exact issuer
membership, unique person/fold/arm coordinates, original739 presentations per
person/arm across folds and identical per-fold arm counts. It retains only
receipts, identities and totals, not810 decoded views or serialized frames.
The operator retains immutable original captures separately and streams one
active job back through `open`. Recomputed frames, input pins, token counts and
receipts must exactly match before issuance. A changed or missing capture fails;
no fallback subset is substituted. This is not a filesystem immutability or
memory sandbox guarantee. The host must admit its preparation storage and memory
budget separately before source use.

Capacity failure raises `CapacityError` with an explicit whole-condition,
no-exposure disposition. Other preparation failures also leave all jobs
unexposed. A conservative source bound is12,563 training plus739 query rows
per job before fold exclusion, or11,173,680 EEG positions before nuisance,
gaze/text and repeated training-frame overhead. This is a bound, not a measured
authentic packet or provider capacity. If full input or retained context cannot
fit the declared host/model limits, refuse the entire condition. No smaller
scientific endpoint is selected automatically.

## Replies, equality and custody

A fresh unpredictable nonce distinguishes every newly prepared logical session,
even for identical input bytes. Reopening uses its already-frozen nonce and is
allowed once per admitted job. Replies have exactly `session`, local query
`token` and finite `p_tsr` in[0,1]. Query order is unchanged; duplicates, revisions,
unknown/cross-session tokens, extra fields, nonfinite values and partial closure
are refused. Empty query folds remain explicit and must still be opened and
collected. Condition closure requires all810 jobs, including empty dispositions.

`condition.collect(job)` restores the ordered `{id,p_tsr}` list and binds input,
preflight and issued-frame hashes. It never reads protected targets or scores.
Issuance is not delivery attestation. These collections are not programme
FIT/INFER receipts, authenticated immutable model states or globally admitted
campaign products; existing source, target-last, fixed-reference and scoring
gates remain downstream. The full-source J/63-obligation reconciliation and
chronology limitations remain unresolved.

`require_same_prepared_exposure(a,b)` compares exact issuer bytes/censuses and
phase policy while permitting fresh session nonces. This supports reuse of one
frozen prepared view pair across routes. Different mode-specific source jobs
have different HMAC sorting and cannot be declared equivalent from aggregate
scores or equal row counts. Original occurrence correspondence, full ordering,
availability, runtime restrictions and resource comparability need their own
trusted prospective qualification. No native-versus-programme result is claimed.

## Generated controls and integration

`test_response.py` invokes the pinned real `public_rows` exporter on generated
original-shaped rows for all nine arms. It checks complete fields/masks, labels,
weights/group relations, original-ID suppression, invalid inputs, nonce/order
mismatches, source-byte and token preflight refusal, actual810-job streaming
preparation/reload and immutable complete response collection. Its small
training fixtures validate engineering behavior, not an authentic population
or independently qualified original split. Complete coordinate/count tests do
not promote scientific readiness.

After installation beside the unchanged shared source:

```sh
python3.11 -I -S -B benchmarks/neural/NEURAL-085/implementations/released-summary-response-v1/test_response.py --control-timeout-seconds 360
```

Nine distinct generated methods passed across bounded affected invocations.
The complete810-job control passed in125.03 seconds with307,167,232 bytes peak
RSS on macOS. These are engineering-control costs, not participant performance.
The test footer reports native RSS units with platform (bytes on macOS; KiB on
Linux); CI must not interpret the native value as universally byte-denominated.

The construction invocation uses `NEUROBENCH_TEST_SOURCE_ROOT` to locate the
read-only checkout. Python3.11 or newer is required by the unchanged shared controls source
(starred subscripts); the test otherwise needs only the standard library, creates no
data files and does not fit a model. The full810-job control uses the explicit360-second alarm shown above; shorter
focused controls default to120 seconds. This is a generated-control runtime
allowance, not a scientific or participant execution budget.
The sole integrator must enroll this exact test command in real CI and register
the additive component. Current task guidance should acknowledge source-only
complete numeric preparation/collection while retaining `not_delivered` for
actual direct transport and its empirical/no-tools/runtime limits; no canonical
or historical source contract is rewritten by this package.
