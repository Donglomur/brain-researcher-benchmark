# Exact-byte rolling reference preparation

`rolling_reference.py` is an optional owner-side construction entrypoint for
NEURAL-EXP-005. It reduces repeated numeric serialization in overlapping
30-second windows. It still feeds every byte of each complete original payload
to SHA-256. It does not alter cases, input hashes, representation identities,
reference fields, labels, folds, support, packets, numeric spellings or scoring.

The existing `protocol.py`, `source_adapter.py`, `source_loader.py` and their
source pins remain unchanged. The optimizer has its own new code identity in a
future execution dependency closure. Do not substitute its hash for an old code
pin, add it to the already frozen representation identity, or add optimizer
metadata to a public/reference object. This private package does not activate a
preparation run or amend the current release cutoff.

## Owner integration seam

The caller must already have an admitted `SourceCorpus`, an authenticated full
description, the private case key and the actual source modules loaded by the
existing dependency loader. Dynamic module identities matter: pass the exact
protocol module belonging to that corpus.

```python
# Existing owner admission and policy construction precede this call.
stats = {}  # assessor-private diagnostics; never a reference/input field
reference = rolling_reference.prepare_reference(
    corpus.sources.current, description, corpus.read_samples, case_key,
    source_adapter=source_adapter, statistics=stats,
)
```

The returned object is the original protocol's `Reference` class. Existing
`protocol.packet(reference, rid, second, corpus.read_samples)` continues to
reconstruct and check full packets by the original method. No candidate-facing
code needs this optimizer or its cache. Do not reuse a cache between owner
contexts; the public entrypoint creates a fresh private cache for every call.

Fast eligibility requires the exact pinned protocol and source-adapter bodies,
the complete relevant callable code/default/global bindings, the exact
`SourceCorpus.read_samples` and `IntervalReader` types/bound methods, matching
corpus/source modules, the ordered montage, 256 Hz, uV and source geometry/hash
agreement. Custom callbacks, rational-rate inputs, subclasses, unsupported
method substitutions and custom description containers delegate with the
original arguments to the unchanged generic function. Once fast preparation
starts, reader/source/callable changes raise; cached data is not served from a
changed context. Source unchanged checks run before and after every window,
including a window consisting entirely of cache hits.

The guarded code/module checks are engineering compatibility checks inside a
trusted assessor process. They are not source authentication, Python sandboxing
or protection against arbitrary mutation of process globals/memory. An object
fabricated with `object.__new__(SourceCorpus)` is not authenticated merely
because its fields satisfy these checks. Original admission and external source
dependency closure remain necessary.

## Byte and memory behavior

The original adapter calibrates individual stored seconds before bipolar
subtraction, independently of the enclosing window. Each new second is validated
with the original finite-number rule and serialized by the actual pinned
canonical encoder. Cached fragments preserve row-major channel order and exact
numeric tokens. Numeric-only row boundaries allow partial-second slices without
reserializing numbers. Full sample brackets and separators are restored, and
metadata keys/values use the original binding and encoder in sorted order.

The LRU keeps at most 31 source-second fragments and, by default, at most 8 MiB
of cached payload bytes. `cache_bytes` may be 0 through 64 MiB; too-large single
fragments are streamed without being retained. The byte limit counts encoded
payload bodies, not Python object/row-offset overhead, the existing reader's
numeric cache, or the complete reference hash list. Those remain bounded by the
31-second fragment limit and existing complete-support contract. The full
reference is still built and returned; this is not a streaming reference-format
change. Clearing fragments retains source identity guards. Recording switches
and backward window requests use normal eviction/reconstruction.

## Generated validation and CI seam

The maintained test module imports named existing source/profile files and
constructs invented in-memory EDF-shaped bytes. It never runs authentic corpus
admission, opens authentic arrays, downloads data, fits a model or changes source
authority. It exercises the literal retained calibration and reader functions.
The 16 controls cover full 79-record reference/partition/case equality; existing
packet compatibility; exact payload bytes across overlapping and boundary
windows; partial rows; Unicode metadata; finite integer/float spelling including
signed zero and subnormals; invalid values; cache byte bounds; source/reader/
callable mutation; clock resets; isolated cache lifecycles; and unchanged generic
fallback semantics. Only the changed generated suite belongs in CI:

```sh
python -I -S -B benchmarks/neural/NEURAL-EXP-005/implementations/source-admission-v1/test_rolling_reference.py --repository "$REPOSITORY_ROOT"
```

Local construction used the existing two-slot pool, one thread and a 150-second
inclusive deadline. Run `nexp005-rolling-exact-byte-01` passed all 16 controls in
12.052 seconds; the entire call including measurement took 15.313216 seconds.
Recorded child peak RSS was 87,179,264 bytes (RUSAGE_CHILDREN scope, not a hard
process-tree memory limit).

The saved optional measurement used 40 overlapping windows over 69 invented
seconds, three alternating-order trials per path. Median generic time was
0.849245 seconds and rolling time 0.204004 seconds, about 4.16x on this fixture.
Both paths read 69 generated source seconds. Numeric serialization occurrences
fell from 5,529,600 to 317,952; each rolling trial still hashed all 30,466,558
original payload bytes. All 40 hashes matched in every trial. Peak cached
payload was 786,123 bytes across 31 seconds. This is a generated engineering
measurement on a shared local machine, not authentic-corpus speed, an end-to-end
runtime estimate, or a scientific result. No production run was restarted.

The separate structural workload 400,534 × 30 × 256 × 18 = 55,369,820,160 is a
metadata-derived count of scalar occurrences in complete windows. It is not a
measured serialization trace. Cache capacity, real numeric token lengths and
other preparation costs determine authentic performance, which remains untested.
