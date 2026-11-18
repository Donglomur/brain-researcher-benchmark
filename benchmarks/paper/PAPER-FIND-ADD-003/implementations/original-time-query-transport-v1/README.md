# Protected original-time query delivery

This additive operator component binds seven already-prepared neural feature
vectors to the accepted opaque mapper and records a durable first-final claim.
It is a source-level delivery interface, not a qualified participant runtime or a
completed reproduction/improvement benchmark. No authentic arrays or targets
were inspected, no models were fit, and no scores were calculated here.

## Exact source boundary

The selected endpoint is the original seven-bin whole-trial leave-one-out time
decoding task, not the legacy five-window odor programme. Authenticated
`TimeDecoding.m` at revision `5e74479bbf97d47c14133cab5fea40a496ec7d94` establishes:

- Lines 45–62: source `spks` is ROI × source trial × frame; select `iscell > 0.3`,
  then take the mean over each ten-frame interval 97:106 through 157:166.
- Lines 69–83: retain eligible ROI order when there are at most 10,000 cells;
  otherwise use the original RNG-dependent 10,000-ROI selection and order.
- Lines 275–306: observations are rows and ROIs are columns after transpose;
  all seven bins of the held-out trial are excluded from fitting together.

`transport.py` does **none** of this preprocessing. The operator supplies the
already-prepared vectors, exact full source keys and private commitments to the
original processed input, preparation and ROI order. It rejects inconsistent
keys, duplicate/missing bins, dimension mismatches and nonfinite features rather
than repairing, clipping, normalizing or dropping observations. Zero eligible
ROIs or unavailable preparation remain an undeliverable fold, not reduced
scientific support. These checks cannot prove that a vector really came from the
source, that its ROI-order declaration is correct, or that signal values contain
no identity fingerprint. Authentic extraction and common preparation across both
access conditions remain unresolved.

## Private API and public packet

`SignalDelivery.create(path, roster, context, secret)` makes an exclusive private
store. `new_context(candidate_sha256, access_condition, preparation_sha256)`
creates a fresh 32-byte nonce; retain its exact result and a cryptographically
random 32-byte secret for recovery. The outcome is fixed to `improvement` and the
access condition is exactly `paper_data` or `paper_data_author_code`. The
candidate digest must identify the independently frozen candidate package.
The caller is responsible for entropy, authenticity, independent freezes and
secret custody. The API cannot detect an operator deliberately reusing or
rolling back an entire store/context. Contexts bind the original input and
preparation; the HMAC-derived mapper key changes opaque identities with the
candidate, access condition, run nonce or preparation. Existing mapper logic
supplies fold-specific IDs and inverse maps unchanged.

For a selected operator `fold_id`, `issue(fold_id, prepared)` accepts exactly:

```text
prepared = {
  input_sha256, preparation_sha256, roi_order_sha256, roi_count,
  rows: [
    {animal, day, cue, control, trial_index, actual_bin, features}, ... seven rows
  ]
}
```

All source keys must match that fold, and actual bins must be exactly 1..7 once
each. Every `features` list has exactly `roi_count` finite numeric values in the
operator's source ROI order, with 1..10,000 ROIs. Prepared row order is ignored;
values and ROI order are preserved without conversion. The private join
commitment binds full source keys, source/preparation/ROI-order identities and
all seven vector digests. Only its HMAC-derived opaque delivery ID is public.
No raw vectors or inverse maps are persisted in the durable store.

The complete public field whitelist is:

```text
{schema, delivery_id, fold_id, queries: [{query_id, features}, ... seven queries]}
```

There are no source animal/day/cue/control/trial/bin labels, timing fields, ROI
identities, actual-bin order arrays, preparation/source hashes or inverse maps.
Query sequence is the existing mapper's secret-dependent opaque-ID order, never
prepared-row or deliberate actual-bin order. Random ordering can coincide with
another permutation by chance; it is not a claim that every permutation is a
derangement. The full public packet digest commits every vector and its ID.

The participant responds with exactly:

```text
{schema: h_original_time_signal_response_v1, fold_id, delivery_id,
 packet_sha256, predictions: [{query_id, predicted_bin}, ... seven predictions]}
```

`submit` verifies the full signal packet and delivery binding, then bridges to
the unchanged mapper response schema. Its collector validates and restores all
seven predictions to private actual-bin order. `finish()` returns the original
full-support prediction document through that collector, preserving unstarted
and failed folds across all 176 panels. It never invokes the scorer or returns
score feedback. Empty source cues retain their original positions under the
existing collector; this component does not rewrite their meaning.

## Restart and first-final semantics

This is a **first attempted final** rule, not first successfully validated final.
An issued fold is claimed durably before any participant response is validated.
Malformed responses consume the attempt. A crash after the claim but before a
complete durable result becomes a failed fold on recovery, without replacement
predictions or a retry. `fail` also claims first, even if its reason is malformed.

Each private record is written once with exclusive creation, authenticated by
filename and content, fsynced, and followed by a directory fsync. Initial store
creation also fsyncs its parent directory. A nonblocking POSIX file lock prevents
concurrent mutation/finalization within the same intact store. A busy store
refuses the operation without making a claim. Truncated, corrupt, replaced or
symlinked records are not repaired. Finalization is durable and repeatable;
late issue/submission is refused. `resume` requires the identical roster,
context and secret. `resume_packet` can recover only the identical prior packet
and private join before any final claim; it does not create a new exposure.

These are software-level operations on trusted operator-owned local storage.
The tests use generated files and injected interruption, not power-loss testing.
Durability depends on filesystem/fsync guarantees, honest operator custody,
intact ancestors/lock inode and no rollback or external deletion. Leaf symlink
checks and mode 0600/0700 are not a sandbox or protection against a participant
sharing the same filesystem credentials. There is no process launcher, timeout
supervisor, candidate isolation or cross-fold memory isolation here. Those
remain the responsibility of the existing lifecycle/runtime work, not a second
framework in this component.

## Unresolved delivery and scientific policy

The seven-query packet is an interface only; permission for joint inference
across those queries remains unfrozen. This component does not deliver training
observations, shuffle training labels, author code, paper assets or preparation
tools. Their exact common manifests and policy still need admission. Whole-trial
LOO exposes a held-out trial as labeled training data in other folds; each fold,
candidate and access condition therefore still requires a fresh isolated runtime
with no shared participant state or final-test feedback. Opaque identity changes
alone do not enforce this. Source/reference acquisition, MATLAB replay, complete
published vectors, superiority/effect criteria and mouse-level uncertainty remain
unqualified. The registration and numerical evaluator are unchanged.

## Generated controls and integration

Place this four-file component in `implementations/original-time-query-transport-v1`
next to the accepted `original-time-opaque-v1` and `original-time-v1` components.
The mapper is size/SHA-256 checked before executing its authenticated bytes; it
then checks the existing scorer source as before. No author bodies are copied.
Run the focused controls through the approved generated-test pool:

```sh
python3 -I -S -B test_transport.py --fixtures /operator/fresh-retained-fixture-dir
```

The fixture directory must not already exist. `--mapping-path` is only a named
private-build dependency override and still requires the exact mapper hash.
The 11 new methods test joins, field exclusion, content commitments, freshness,
replay/refusal and restart behavior; they do not rerun the prior 11 mapper tests
or call numerical scoring. A cumulative 128 KiB fixture-write guard preserves
failures and overwrites in the accounting. Central CI enrollment belongs to the
sole integrator; discovery is not assumed.
