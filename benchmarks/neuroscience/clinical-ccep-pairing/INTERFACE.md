# CCEP complete-block pairing interface

See [README.md](README.md) for placement, private operator inputs and commands.
The unchanged [primary interface](../clinical-ccep-artifact-grading/INTERFACE.md)
defines the complete original policy and targets.

## Deterministic mapping and its proof

The grouping key contains the original patient, session, VTC recording contact,
repetition count, complete normalized layout hash, and exact acquisition identities
for montage, pulse waveform/intensity/duration/rate, sampling grid, reference,
filter and baseline. The layout binds every relative time, units and both masks.
No response values/hash, anatomical class, target hash, predictions, reference
outcomes or recipient-context values determine the map. Stimulated-site identity
is operator-only and used solely to forbid within-site moves and construct the
target-free candidate order. Site IDs must represent actual stimulated sites,
not an invented alias for anatomical class or an arbitrary per-pulse identifier.

Let a complete stratum have N blocks and largest site multiplicity M. If M>N/2,
its M blocks have only N−M possible distinct-site donors, so an injective
assignment is impossible. The **entire** stratum is unsupported; no minority
subset is selected. A singleton is also unsupported. Original non-ready source
coverage is retained as its own unsupported reason.

For M<=N/2, place each site's blocks contiguously in a circular order. For each
seed 0..19, sort sites by SHA-256 of compact sorted-key ASCII JSON encoding of
`[algorithm, seed, group_hash, "site", site_id]`; break hash ties lexically.
Sort blocks within each site identically with `"case", case_id`. The algorithm
identifier is `ccep-hash-ordered-distinct-site-rotation-v1`. Group hashes are
SHA-256 of the exact grouping dictionary. Let

`shift = M + int(SHA256([algorithm, seed, group_hash, "shift"]),16) % (N−2M+1)`.

The donor at position i is position `(i+shift) % N`. This is a bijection. Each
site occupies an interval of length m<=M. Equal-site positions have circular
distances in `[0,m−1]` or `[N−m+1,N−1]`, whereas the selected shift lies in
`[M,N−M]`; consequently no donor has its recipient's site. It also has no fixed
point. This establishes sufficiency and necessity of M<=N/2 for the complete
multipartite distinct-site assignment problem.

The complete map across feasible strata is one constructive candidate per seed,
and therefore the first admissible candidate within the contract's maximum of
100. Zero candidates are needed when no stratum is feasible. There is no
outcome-dependent retry or group relaxation. Identical complete donor maps are
deduplicated by their complete canonical contents; the report retains all 20
seed dispositions and the actual distinct-transform count. The family is **not
a uniform sample of all admissible permutations**, and maps are not independent
biological replicates. No permutation p-value or exchangeability claim is made.

Unsupported rows remain in the census and in each original-condition score.
They have no fake unchanged null packet or transformed prediction. Supported
rows move all response repetitions and samples together, without pulse/sample
selection, interpolation, shuffling within blocks, or invented boundary joins.
Identical response bytes at different sites are reported after map freezing as
unchanged-content pairs; they never cause map rejection or favorable selection.

## Operator files and custody

The previously accepted primary policy and its externally supplied expected
SHA-256 are unchanged. It declares exactly five people, their LOPO folds, all
blocks, planned four classes and fixed probability floor/tolerance. Do not let
a contestant supply either trusted policy path/hash or protected targets.

The additional `ccep-pairing-policy-v1` JSON has exact fields:

- `schema`, `task_id`, `primary_policy_sha256`, `algorithm` as above;
  `envelope_schema: "ccep-complete-block-v1"`;
  `source_protocol_sha256`, binding the independently authenticated normalized
  preparation and target-free metadata procedure.
- `arms`: 2..16 objects with exactly `id`, `role`, `provenance_sha256`. At least
  one role is `candidate` and one is `reference`. Freeze the complete required
  arm/reference roster and all provenance before outcomes. More than one
  candidate/reference is supported. A provenance hash does not prove competence,
  correct training membership, equal information or an actually executed model.
- `rows`: every primary-policy case exactly once, with `case_id`,
  `stimulated_site`, `nuisance`, `response_sha256`, `layout_sha256`,
  `context_sha256`. The nuisance object has exactly `montage`, `pulse_waveform`,
  `pulse_intensity`, `pulse_duration`, `pulse_rate`, `sampling_grid`, `reference`,
  `filter`, `baseline`; each value is the SHA-256 of the complete authenticated
  source/configuration identity for that property. These must not be labels,
  response-derived categories, target-selected bins or placeholders. All three
  component hashes bind their exact decoded bytes.

No hash is a replacement for scientific source authentication. Genuine raw
stimulus/contact/site correspondences and all exact nuisance signatures are
still missing inputs, not manufactured in this implementation. The existing
primary `site_block` token and this physical `stimulated_site` identity are
different concepts; repeated blocks from one site remain that same site.

Maps are produced without opening targets. The evaluator freezes their exact
output bytes/hash **before** candidate/reference predictions. The source checks
that a later supplied map is exactly reproducible from the trusted policies,
but hashes cannot independently prove chronology or physical isolation. Map
files include donors, site identities and nuisance strata and stay private.
Reports include class composition and support details and also stay private.
No automatic contestant feedback or publication is selected.

## Normalized full-block envelopes

An original block is a strict UTF-8 JSON object with exactly `schema:
"ccep-complete-block-v1"`, `task_id`, `case_id`, `response_b64`, `layout_b64`,
`context_b64`. Its whole original file hash must equal the original primary
policy's `packet_sha256`. Base64 must be canonical and decode to the exact bytes
bound by the corresponding control-policy hash. Components are strict JSON:

- Response: a matrix with exactly the declared repetition count and all native
  samples. Every observed sample is a finite JSON number, never a bool; missing
  samples remain explicit JSON null. There is no numeric transformation.
- Layout: exact fields `relative_times_seconds`, `units`, `missing`, `artifact`.
  Times are increasing decimal strings (at most32 characters each) within the
  original 0.011..0.500 second interval. They are checked with Decimal rather
  than round-tripped through binary floating point. Both masks are complete
  repetition×sample boolean matrices. `missing=true` requires null response;
  other cells remain finite, including artifact-marked finite observations.
  Units are an explicit 1..32-character printable ASCII string.
- Context: only `recording_location`, a nonempty string of at most1024 characters.
  The authenticated producer must make it target-free; the scorer cannot infer
  whether a string secretly encodes a target. Stimulating-site/contact IDs,
  anatomy classes, labels, BPC labels, source filenames and private person IDs
  are prohibited participant context. Complete semantics/privacy audit remains
  an external requirement.

Recipient and donor original files are authenticated and every component is
parsed/shape-checked before a paired packet is emitted. Their layout bytes must
be identical, not merely similar hashes of an incomplete descriptor. The output
is `ccep-paired-complete-block-v1` with recipient `case_id`, `transform_id`, the
**complete donor response base64**, and the **unchanged recipient layout/context
base64**. No donor ID/site/label is emitted. The exact original target/case/context
join stays fixed; target files are never opened by packet materialization.

This normalized envelope is a new explicit interface, not proof of raw/native
equivalence or a converter for ds004457 files. The genuine producer must verify
all original samples, repetitions, masks, units, baseline and clock semantics
before binding these files. No producer, source record or clinical answer is
invented here. The packet command emits one complete supported case; an operator
uses it for **every** supported recipient of every distinct map and every arm
receives the same bytes. Full original packets remain available separately.

Each document inherits the primary regular-file, no-follow/nonblocking, strict
JSON and 8MiB ceiling. A normalized block has at most100,000 response cells.
The original20,000-case ceiling remains. These are fail-closed engineering limits,
not exclusions: a larger genuine complete case or artifact needs prospective
resource/source revision, never truncation, decimation or a favorable subset.
Actual full-cohort memory and runtime remain unprofiled.

## Commands and Python API

Run from this public component directory. All capitalized paths/hashes below are supplied
by the trusted operator. All outputs except complete paired input packets remain
evaluator-private. Commands print their exact result JSON to stdout; freeze its
complete emitted bytes, including the final LF, and do not overwrite an earlier
selected map or result. API functions return the same structured objects.

```sh
python3 -I -S -B pairing.py maps --policy POLICY.json --policy-sha256 POLICY_SHA256 --control CONTROL.json --control-sha256 CONTROL_SHA256
python3 -I -S -B pairing.py packet --policy POLICY.json --policy-sha256 POLICY_SHA256 --control CONTROL.json --control-sha256 CONTROL_SHA256 --map MAP.json --map-sha256 MAP_SHA256 --transform-id TRANSFORM_ID --recipient-id CASE_ID --recipient-packet RECIPIENT.json --donor-packet PRIVATE_DONOR.json
python3 -I -S -B pairing.py score --policy POLICY.json --policy-sha256 POLICY_SHA256 --control CONTROL.json --control-sha256 CONTROL_SHA256 --map MAP.json --map-sha256 MAP_SHA256 --artifact ALL_ARMS.json --targets PRIVATE_TARGETS.json
```

The corresponding API functions are `maps(...)`, `packet(...)`, and `score(...)`;
their explicit signatures match these command arguments. Map generation refuses
answer/prediction/packet arguments, materialization refuses answers/predictions,
and scoring refuses waveform paths. Missing mandatory expected policy/map hashes
fail before their respective protected input sequence. Return code2 indicates
invalid/incomplete input; scoring code3 reports an unavailable null or unresolved
original construction; code0 is successful source-interface execution only.

## Complete matched-arm artifact and equations

The `ccep-paired-predictions-v1` artifact has exact fields `schema`, `task_id`,
`primary_policy_sha256`, `control_policy_sha256`, `map_sha256`, `class_order`,
`arms`. Every frozen arm occurs once as `{id, original, transforms}`. `original`
is the complete unchanged `ccep-predictions-v1` artifact for every original case.
Each transform is `{id, rows}`, exactly once per distinct map; each row is
`{case_id, probabilities}` for exactly its supported recipient IDs. Missing or
extra cases, arms, transformations, altered class order and invalid probability
vectors fail the **entire** paired artifact. An unsupported case cannot be filled
with unchanged predictions. All arms, including references, pass validation
before any private target bytes are opened. No success-only comparison is made.

For each arm a and transform t, on each person's identical supported original
and transformed case IDs S_it, use the unchanged primary floor and compute

`d_it(a) = mean_{j in S_it}[loss(p_transformed_ajt,y_j) - loss(p_original_aj,y_j)]`.

Then `d_t(a)` is the equal mean over people with nonempty S_it. Every person is
reported, with full-original and supported counts, exact supported IDs, both
loss means, difference or explicit null, and a list of people without support.
The optional summary is the equal mean of d_t(a) over **distinct transforms**,
not seeds, trials or pooled cases. Candidate-minus-reference effect differences
use the exact same case/person/transform denominators. They are descriptive
comparisons, not proof of reference competence or physiological understanding.

The separate natural-condition full score for every arm comes directly from
the unchanged primary summarizer on all original blocks and all five people.
No supported-case diagnostic replaces it. If no stratum is feasible, the null
is unavailable while the complete original scores remain. If original source
coverage is unresolved, both full and diagnostic scores stay unestablished and
targets stay unopened. Post-freeze class coverage/cross-class versus same-class
counts and unchanged-response-byte counts are reported; they never select maps.
Matched execution, training/reference freezing and correct packet use remain
operator/runner responsibilities and are not authenticated by prediction files.

## Verification and limits

```sh
python3 -B -m unittest -v test_pairing
```

All fixtures are explicitly invented. They include exhaustive small matching
checks, every allowed shift across unequal site multiplicities, full matrices
with missing/artifact masks, source/packet/mapping boundaries, real three-command
CLI behavior, hand-derived equal-person and equal-transform means, unchanged
original primary results, unsupported groups and reference failure barriers.
No authentic waveform, clinical annotation, source conversion, fit, model, API,
dataset acquisition, permutation inference or scientific qualification occurred.
The source is original project MIT software; no external data/code rights are
granted. This completes additional source behavior within one existing task.

## V2 output boundary correction

V1 could emit a complete map larger than its own inherited8MiB reader limit.
V2 checks the exact compact ASCII JSON serialization **plus its final LF**
before every successful API/CLI output, including normal, null-unavailable and
construction-unestablished reports. The complete result is refused if too large;
no cases, maps, masks, unsupported rows or comparator arms are removed. The historical V1 failure and its correction remain in prior review evidence,
not in this public package. The production dependency is the same exact primary
scorer in the adjacent primary component. Only its relative source lookup changes
for public placement; all remaining scientific code and full generated controls
are unchanged. No authentic data or scientific results are supplied.
