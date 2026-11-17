# Laser EEG condition packets

This owner-side Python 3.11 module turns a **reviewed normalized input ledger**
into the complete task's common evidence packets. It implements nine outer folds,
all 678 nominal participant-within-experiment records, eight training examples,
two labeled calibration trials and one unlabeled query. The same immutable query
bytes are returned for direct answer (A), frozen program (B), and investigation
with tools (C). The existing [full-assay scorer](../full-assay-scorer/README.md)
accepts the private targets produced here.

This is source construction, not an authentic benchmark result or a runnable
candidate sandbox. No real EEG, labels, native loader, model, trained reference,
tokenizer, environment image or downloaded scientific code is included. The
generated tests establish source behavior only. Scientific, execution and
submission qualification remain false.

## Owner API and boundaries

Load `packets.py` with `importlib.util.spec_from_file_location`, or incorporate it
as an owner-only module. Its import does not read files or execute experiments.
All structures below are ordinary Python JSON-compatible objects. Every listed
field is required; unlisted fields are rejected by the executable validators.

```python
assay = PreparedAssay(
    reviewed_ledger, reviewed_protocol, reviewed_representation,
    epoch_loader,  # private callback: one (experiment, person_key, trial_key) tuple -> bytes
    protocol_sha256=reviewed_protocol_pin,
    representation_sha256=reviewed_representation_pin,
    support_salt=frozen_32_byte_support_salt,
    opaque_key=separate_private_32_byte_key,
)

receipt = assay.prepare_all(
    owner_authoring_staging_sink,  # (opaque_fold_id, packet_bytes)
    owner_query_staging_sink,      # (opaque_query_id, packet_bytes)
    actual_tokenizer_and_framing_counter,
    tokenizer_sha256=reviewed_tokenizer_pin,
)
targets = assay.private_targets()          # evaluator-private
selection = assay.private_selection_audit()  # owner-private, includes source IDs

authoring = assay.authoring_packet(heldout_experiment)  # exactly eight examples
mode_packets = assay.packets_for_modes(one_query_id)   # same bytes for A/B/C
```

The owner must never expose `assay`, its loader, the input ledger, private targets,
selection audit or all-query staging directory to a candidate. Only a fold's
authoring bytes, then the current query's permitted bytes, cross that boundary.
The constructor detaches input metadata by value, but the trusted owner object
is not an adversarial sandbox or an immutable security container.

Construction validates the complete ledger before loading any EEG. Epoch bodies
are checked lazily when materialized. `prepare_all` visits every query and all
nine authoring packets, checks capacity for each, and streams them to owner-only
staging without retaining every packet in memory. It returns the complete receipt
only on success. A failing sink, changed body, invalid epoch or over-capacity
packet aborts; partial staged outputs are not a release. Atomic publication and
storage permissions are the owner's responsibility. Returning `private_targets`
alone does not establish complete epoch or packet coverage.

## Normalized source schemas

Canonical object pins use ASCII JSON with sorted keys, compact separators and
finite numeric values: `sha256(object)` in `packets.py`. Epoch pins instead hash
the exact UTF-8 JSON bytes returned by the loader. The loader body limit is
32 MiB per complete epoch; a larger source must remain on hold, never truncated.
Duplicate JSON keys and nonfinite constants are rejected. Receipt hashes identify
reviewed records; this code cannot establish that the review actually occurred.

`lep-packet-protocol-v1` has these exact fields:

| Field | Contract |
| --- | --- |
| `schema`, `task_id` | Exact schema and this task's canonical ID |
| `documentation` | Complete owner-reviewed common scientific documentation |
| `documentation_sha256` | SHA-256 of that text's UTF-8 bytes |
| `context_review_sha256` | Owner's source-context review receipt |
| `contexts` | Map of private normalized IDs to `{device, reference, rating_protocol}` |
| `stimulated_sides` | Distinct source-reviewed side-category identifiers |

Device names are `BioSemi`, `ANT`, or `BrainProducts`. Source experiment devices
are bound to `BioSemi, ANT, BrainProducts, ANT, ANT, BrainProducts, BioSemi,
BrainProducts, BrainProducts`. Context text, channel labels and category names
are trusted reviewed content: an exact-field schema cannot recognize target
information covertly embedded in allowed text or scientific operands.

`lep-normalized-representation-v1` has these exact fields:

| Field | Contract |
| --- | --- |
| `schema`, `task_id` | Exact identities |
| `normalization_review_sha256` | Source timing, filtering, units and lineage review receipt |
| `endpoint_convention` | Explicitly `right_open` or `inclusive`; no default |
| `times_us` | Every 10,000 µs from −1,000,000 to before +2,000,000, or through +2,000,000 respectively |
| `sample_rate_hz`, `bandlimit_hz`, `quantization_uv` | Exactly 100, 30 and 0.01 |
| `montages` | Map of private IDs to `{coordinate_system, channels}` |

Every montage preserves its complete EEG roster; each channel is
`{label, xyz_mm}` with a unique label and a finite millimetre triplet or explicit
null coordinates. Variable montages are retained. Both 300- and 301-sample grids
can be represented **only by explicitly declaring the corresponding convention**.
Supporting both does not resolve the scientific source ambiguity or approve a
production convention.

`lep-normalized-ledger-v1` has these exact fields:

| Field | Contract |
| --- | --- |
| `schema`, `task_id` | Exact identities |
| `protocol_sha256`, `representation_sha256` | Match the frozen constructor pins |
| `inventory_receipt_sha256`, `producer_receipt_sha256` | Complete native inventory and reviewed normalized-producer receipt identities |
| `identity_receipt_sha256` | Reviewed person/session/raw-to-derivative identity linkage receipt |
| `identity_linkage` | `complete` or `unresolved` |
| `people` | All 678 nominal records with exact nine counts: 26, 29, 39, 30, 65, 95, 142, 223, 29 |

Every person is `{experiment, person_key, biological_group, trials}`. Experiment
is an integer 1–9, and `(experiment, person_key)` is unique. `biological_group`
joins all known recordings/sessions of a physical person across studies. It can
be null only when linkage is declared unresolved. A populated identifier does
not prove independently verified biological identity.

Every trial is `{trial_key, chronology, eligible, rating, exclusion_reason,
alias_group, epoch_sha256, montage_id, context_id}`. The private normalized key
`(experiment, person_key, trial_key)` is unique. Canonical keys must cover native
session/block/trial identity; filesystem paths are rejected. `chronology` is a
strictly increasing nonnegative integer in the source-ledger order. Actual
temporal source reconciliation is an owner admission obligation.

For eligible trials, `rating` is a finite number in [0,10], preserving decimals
and zero; `exclusion_reason` is null, and the epoch, montage and context bindings
are required. For excluded trials, the target and all three payload bindings
are null and an explicit predeclared reason is required. Excluded rows are never
silently removed. Every person must retain at least three eligible trials.
Booleans are not accepted as numbers.

`alias_group` identifies known copies of the same source trial, including raw
and derivative aliases, in eligible **and excluded** rows. A known alias group
may contain only one eligible record globally. An eligible duplicate would
permit calibration/query leakage or double scoring; intake refuses rather than
quietly dropping it. The reviewed producer must canonicalize it with documented
exclusions, while retaining full person/trial coverage. If that leaves fewer
than three eligible trials for anyone, the complete assay stays on hold.

`lep-normalized-epoch-v1` has these exact fields:

| Field | Contract |
| --- | --- |
| `schema`, `representation_sha256` | Exact schema and frozen common representation |
| `samples_uv` | Complete channel-major matrix of physical microvolts |
| `valid_mask` | Same complete dimensions, Boolean sample mask |
| `delivered_energy_j` | Source-recorded nonnegative physical energy or null |
| `stimulated_side` | One reviewed protocol category |
| `calibration_category` | Source-documented calibration target in [0,10], or null |

Masked values must be null and remain null; observed samples must be finite.
There is no arbitrary metadata passthrough. Current rating, unpleasantness,
event fields, source filenames and target-derived QC/category information do
not belong in an epoch. Physical energy and documented calibration category
are separate operands and must never be inferred from the current rating.

## Split and transform audit

Known biological-person links and shared trial aliases form a transitive graph
over nominal people. Excluded aliases remain in that graph. For each held-out
experiment, every connected component touching **any** held-out person is purged
from all eight training pools. A duplicate trial therefore excludes the entire
linked person's other trials too. Unknown identities remain unknown; unresolved
linkage permits only an experiment-transfer description, with no independent-
person or session-independence claim.

One eligible support per other experiment is the minimum of
`SHA256(support_salt + canonical_json(["lep-support-v1", experiment, person_key,
trial_key]))`, with the canonical key as a deterministic tie-break. The owner
freezes the salt before looking at outcomes and retains it privately for audit.
Target values and EEG bodies never enter selection. An empty post-purge pool
refuses the full assay rather than returning fewer than eight supports. Private
selection audit includes selected and purged source keys for every fold.

The first two eligible chronological trials per target person are calibration;
every later eligible trial becomes a query. No excluded row consumes a slot.
Opaque IDs use domain-separated HMAC-SHA256 with a separate private key and
fold-specific trial identifiers. Neither source IDs nor alias/person groups
are serialized in candidate evidence. The key must be protected and unpredictable
in a real preparation; tests use explicitly generated constants.

This module applies **no learned or fitted transformation**. Already normalized
microvolts are deterministically quantized to 0.01 µV integers with decimal
round-half-even, retaining every channel, sample, coordinate and mask. Each case
reports its maximum absolute quantization residual (at most 0.005 µV) and missing
sample count. There is no clipping, imputation, channel intersection, averaging,
per-person normalization or target-dependent scaling. Large representable finite
samples are retained. No training-fit or held-out-fit statistics are computed.

## Capacity and runtime limits

`check_context_capacity` hashes the exact complete bytes and calls an explicitly
supplied counter. The callback must use the actual selected tokenizer, full chat
framing and any additional permitted scientific context. If wrappers differ by
mode, account for every mode, using the largest complete live context. A byte
count, word count, arbitrary callback, or generated-test constant does not qualify
tokenizer fit. Positive exact integer token counts up to 1,048,576 are accepted;
larger packets refuse without truncation or case selection.

`prepare_all` records every packet hash, byte count and supplied token count, plus
the frozen representation/protocol, private-target and selection-audit hashes.
This is evidence for complete preparation only under the trusted owner's input
and counter assumptions. The source does not enforce per-query cumulative input
3,145,728 tokens/output 16,384 tokens, failed-call accounting, B's frozen-program
commitment, network denial, or process/cache isolation. A separate execution
harness must enforce them and destroy candidate state after every query and fold.
Matching packet bytes does not establish those runtime conditions.

## Remaining scientific admission gates

The [canonical task](../../task.json) remains authoritative. Source-specific
baseline/intervention trial membership, actual trial census, person/session
identity and alias provenance, channel typing, original units and timestamps,
the 300/301 endpoint choice, 30-Hz filtering/antialiasing/resampling, experiment
4/5 marker-delay sign and already-corrected derivatives must be resolved before
authentic preparation. This package deliberately implements no guessed MAT/SET
loader or raw signal preprocessing.

Inherited whole-session rejection/ICA/rereferencing may use future unlabeled
values. The reviewed normalization receipt must explain that lineage; this code
cannot turn it into train-only preprocessing or a causal online decoder. Report
onset/motor contamination, actual energy missingness, context-only reference
competence, representation-vs-full-precision loss, public-data contamination and
fresh untouched external acquisition remain task-level interpretation gates.

No extra benchmarks, study participants, valid authentic packets, model scores
or competence claims are created by passing these source tests.

## Generated checks

```sh
python3.11 -I -S -B benchmarks/neural/NEURAL-SCOPE-20261114-LASER-EEG-REPORT/implementations/condition-packets/test_packets.py
```

Run from the repository root. Python standard library only; no installs, network,
Docker, model, real data, or credentials. The 17 tests cover a generated complete
678-person roster, 2,712 trial rows, first-two calibration and all 678 queries;
an extra eligible trial verifies that the denominator is not hardcoded. They
stream nine authoring and 678 query packets, test scorer compatibility, target-
blind selection, whole-cohort and transitive-alias purge, duplicate eligible-alias
refusal, zero/decimal targets, variable montages, both explicit epoch grids,
half-even quantization, complete masks, target exclusion, byte equality between
modes, malformed inputs and capacity refusal. Capacity tests use a labeled fake
counter; they do not assert actual tokenization. On the development machine this
source suite took about 11 seconds with about 61 MiB maximum RSS.
