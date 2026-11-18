# Original protected-executor layout and packed predictions

This component plans storage for the original language task and collects its
predictions without creating one file per invocation. It preserves all 14
sessions, eight people, 58,926 original jobs, 6,776,076 held-qid requests and the
224-array scientific result family. Candidate process isolation, preparation of
the authentic immutable store, and a full scientific run remain separate work.

The authenticated support census showed that serializing a fresh six-array
packet for every request would write 5.71 TB cumulatively. `layout.py` uses the
saved source-support signatures to identify reusable feature matrices and
response shards. It reads the pinned census and source geometry only.

A feature key includes session, feature family, sentence-swap condition, layer,
positive lag and exact ordered time support. Nonpositive lags preserve the same
features when support agrees; population, unit and time-shuffle jobs can reuse
the same context features. Feature and layer jobs remain distinct. Generated
controls compare every proposed shared key against the unchanged 4,209-job
source constructor. Shared keys require identical complete X, not merely equal
shapes. Each individual job already exposes its complete X through the union of
training and query features, so storing that same matrix once adds no feature
observation.

Response shards use the existing sufficient source-support partition. Each held
qid must expose exactly the other qid shards from its own response class. The
held shard, other response classes, private base targets and the full private
store manifest remain outside the candidate's view. The planner does not
construct those mounts or prove an OS boundary. It also reports the large number
of shard references a naive per-request mount strategy would create. Storage
reuse alone is not a runtime-throughput measurement.

`iter_source_contexts()` provides the exact source job order: session, field,
layer, lag. Its canonical JSONL digest is
`a56e01b3494ce66e66192c5cf5f18583c08dedaccfafb4a624ae526561dbc18b`.
The collector authenticates the complete expected context sequence once and
checks each job against it. The private store and request schedule have separate
frozen identities. Actual request identities must bind the exact selected
immutable views, not a candidate-supplied declaration.

The collector requires frozen expected request hashes but does not yet generate
them from authentic immutable views. Reusing the old bridge's full-array request
hashing would still traverse about 5.71 TB of cumulative request payload. A
different identity derived from preauthenticated store objects and selected rows
needs its own reviewed equivalence contract. Planner digests and the collector's
opaque expected hashes are not claimed to be existing bridge request hashes.

`PackedWriter` accepts raw NPY predictions only after its trusted caller provides
a closed-invocation receipt. It checks the raw byte cap before hashing, exact
query geometry, finite primitive float32/float64 values, original sorted held-qid
order and the frozen request identity. One job's predictions are assembled in
original row order and written once as little-endian float64. This matches the
original source's float64 pooled prediction array, including exact conversion
from float32. Noncontiguous held-qid rows retain their original positions.

There are three product streams and one manifest:

| Product | Contents |
| --- | --- |
| `PREDICTIONS.f64le` | Canonical prediction matrices in original job and row order |
| `REQUESTS.bin` | 192-byte records binding ordinal, job, shape, held qid, job matrix offset, raw dtype/order, view hash, raw transport hash, canonical prediction hash and closure hash |
| `JOBS.bin` | 256-byte records binding job coordinates, request range, matrix extent and qid/time/support-class/prediction hashes |
| `MANIFEST.json` | Frozen candidate/store/schedule/context identities, complete counts and stream hashes |

Request offsets name the job matrix base; they do not imply that a held qid's
rows are contiguous on disk. The authenticated private qid/time maps identify
those rows exactly. Incoming NPY header bytes are not retained. Every prediction
value and the incoming transport hash are retained. Original targets remain in
the separate private store, with exact source lag, permutation and support
lineage for independent observation recovery.

`PackedReader` authenticates each private stream once, then reuses stable file
identities while reading sequential job blocks. `recover_job` checks every
request-to-row join before returning the full matrix to the unchanged original
Pearson kernel. Generated controls verify exact pooled-score equality, including
big-endian, Fortran-ordered float32 input. Source correlation and figure reducers
are unchanged.

This design assumes a trusted host that keeps its authenticated base files
immutable. It does not claim resistance to a hostile host controlling file
identity or the kernel. The collector validates and hashes the supplied closure
receipt; it does not independently observe process teardown. The actual provider
lifecycle journal must remain retained, authenticated and independently verified
by the future protected execution protocol. A closure hash alone is insufficient.

The planner's byte and file counts are prospective storage arithmetic. They
exclude explicitly listed lifecycle logs, per-view metadata, failure artifacts,
filesystem overhead and runtime I/O. No authentic store, predictions, native
runtime or large output allocation has been created by these source controls.
Scientific and protected-execution qualification remain false.
