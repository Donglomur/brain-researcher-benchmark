# Sealed journals to the existing session evaluator

This operator-side adapter converts all 56 original action journals to the complete current NEURAL-067 prediction interface. It preserves every binary64 action, including signed zero, in seven source coordinates across 14 query runs and four information arms. There are 34,490 rows per arm and 137,960 rows overall. It does not choose a new endpoint, split, threshold, access mode, unit convention, or metric.

The original full controller already exists. Its `runtime/candidate.py::converse` releases one current observation, checks one matching seven-value response, commits it durably, and only then requests another row. Its `query_phase` seals a journal after natural stream closure and producer cleanup; `host.py` requires all 56 blocks. This component leaves those sources, their work/cleanup deadlines, the accepted row/journal failure repairs, and runtime selection untouched. It is a compatibility seam, not another controller.

The old assembler reads journals in **run-major then arm order**, writes 56 NPZ prediction files, and emits `neural067_predictions_v1`. The current published scorer instead admits `neural067_session_predictions_v1` in **arm-major then run order**, with full row IDs and source session labels. The adapter reads the original sealed journals directly, avoiding the intermediate NPZ serialization. No NPZ loader, target loader, model, API client, or filesystem writer is included.

## Operator interface

`bridge.convert(descriptors, load_journal, source_inputs, scorer_path=None)` returns the current scorer submission object only after complete admission.

- `descriptors` is the exact original ordered host list: `run`, `arm`, `file`, `bytes`, `sha256`, `final_chain`. All 56 identities, filenames, extents, and digest formats are checked before the first callback.
- `source_inputs` maps all 14 query runs to their operator-selected original input `{bytes, sha256}` pins. These identify the original prepared input artifact, **not** the separately prepared 368-byte-row causal cache. No real packet pin is embedded or fabricated here.
- `load_journal(filename)` is a trusted operator callback returning captured immutable bytes. The adapter verifies the complete byte pin, canonical padded header, original input identity, ordered row numbers, seven finite values, record checksums, predecessor chain, and selected final chain.
- `scorer_path` defaults to the sibling `session-evaluator-v1/scorer.py`. Its source bytes must match the existing published pin before compilation. The adapter calls its prediction admission only; it never calls `grade`.

Descriptor and input metadata are copied before callbacks so a callback cannot silently replace later identities. The callback can raise; no partial submission is returned. The adapter neither writes nor emits partial artifacts. It uses the scorer's existing roster, session labels, coordinate order and contract hash instead of maintaining a second scientific definition.

The prediction mapping is lossless. **Old and current scores are not claimed equivalent.** The published session evaluator deliberately differs from the old force-finite constant-target convention. This adapter leaves that current evaluator byte-identical and performs no arithmetic on predictions. Its output retains the scorer's existing unverified execution/access-mode limitations.

## Enforcement boundary and remaining work

Caller-supplied pins and a valid hash chain establish internal consistency only. They do not authenticate the original observations, prove observation hashes, show when a journal was written, establish source terms, prove producer absence, or verify deadlines. The original controller must own source selection, program/state freezing, current-row release, filesystem capture, resource limits, process cleanup and complete causal execution. A valid journal can be manufactured offline; this converter makes no claim otherwise. All current task source-terms, timestamp/mask authentication and NEURAL-067/068 exposure holds remain.

Deployment still requires explicit source rebinding of the accepted row/journal repair into the original controller and selection of the journal-to-session grading path. Existing private locks, source descriptors and execution selection are unchanged. No complete runtime, benchmark readiness, native understanding or scientific result follows from this source-only component.

## Generated checks

Run `python3 -I -S -B test_bridge.py` through the existing shared two-slot test pool. Before installation, pass `--scorer-path` pointing to the unchanged published scorer. The controls construct synthetic journals in memory for the complete declared geometry; they write no neural arrays or journal fixtures. They check all output values and identities, full-panel order, support and pin refusals, headers, chain integrity, nonfinite actions, callback mutation/failure, and pinned scorer substitution. No authentic target, numerical fit, candidate program, model or scientific scoring is run.
