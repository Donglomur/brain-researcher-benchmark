# Trusted numerical worker ABI

`numerical_worker.py` implements concrete future reference fit/query and passive
candidate model admission. It consumes the owner's already bounded `artifacts.Store`
instances and calls `save_model`/`load_model`; it never creates a new Store or
resets a counter. The owner controls trusted staging, partition/cell/configuration
loops, isolation, original deadlines, resources, complete support and result
publication. Authentic execution remains paused.

## Reference training

`fit_reference(train_manifest, input_store, output_store)` accepts exactly these
required TRAIN keys:

* `schema: paper_i_reference_train_v1`, `profile`;
* `feature_schema`: the encoder schema, matching profile;
* `configuration`: an exact member of `encoder.configs(profile)`;
* `cell_tokens`: complete ordered opaque cell tokens for the shared population TRAIN;
* `X`: the legal feature-record list in private transport order;
* `Y`, `weights`: exact primitive NPY descriptors in input_store.

The optional fields are `label_provenance` and `selected_cell_indices`.
`selected_cell_indices` is reference-only: null/absent uses all cells; otherwise
it is a nonempty list of unique in-bounds integers (booleans are rejected).
The worker loads the full population Y, verifies its complete cell axis, then
selects exactly those columns and tokens for the numerical fit and saved model.
No duplicate selected-Y files are emitted and the caller retains full-Y candidate
training. Returned logical fits count only selected cells. Candidate public TRAIN
must reject this field. The accepted candidate fit REQUEST may name selected
indices/tokens for its exported output axis while still providing full-Y
population training; this is a separate external candidate ABI. The previous frozen source is
retained at `reference/history/numerical_worker-before-selected-cell-indices.py`.

`label_provenance` is the operator-private attestation
required by the encoder for CM-shuffled; it must never be included in candidate
TRAIN or candidate-model metadata. The caller supplies already reassigned labels
and verifies the exact private receipt/partition binding. The helper does not
generate permutations, expose source order or choose any configuration.

It loads the bounded training arrays, verifies the target cell axis and calls
the independent encoder once. It saves `MODEL.json` plus primitive state arrays
through `artifacts.save_model`. The returned result includes the exact model
manifest/pin/path, configuration ID, ordered cells, training-example count,
one fit call, logical_cell_fits equal to the number of target columns, and one
SVD factorization for a ridge model or zero for context-average. Those counts
describe the actual batched numerical call and its per-cell logical fits; they
do not replace the full 1,200-per-cell reference attempt accounting.

Candidate final fits may use the full cell matrix for population methods;
fixed-reference selected-configuration groups may use column subsets. The owner
records those different logical/resource denominators, selects configurations
using complete inner support and never ranks on outer targets.

## Reference prediction bundle

`predict_reference(bundle_manifest, input_store, output_store, record)` accepts
exact bundle keys schema, profile, cell_tokens and groups, with schema
`paper_i_reference_bundle_v1`. Each group has exactly model_path, model_pin,
cell_tokens and output_indices. Model paths are bounded relative POSIX names
ending in MODEL.json, with no absolute paths, traversal, empty segments or
backslashes. Pins contain exactly positive bytes and lowercase SHA-256.

The master cell_tokens list is the complete ordered target axis. Every output
index appears exactly once across all groups, and each group's cells equal
the master tokens at those indices in the same order. Missing, duplicated or
misbound cells fail before model bodies are read. A model path cannot repeat.

For each group the worker invokes the owner's `load_model` on the same Store.
Its descriptors resolve relative to that MODEL.json's parent, while all reads
charge the existing shared Store counter. The worker verifies reference model
version/count and the same complete feature schema across groups, predicts the
same single legal record once per group, and assembles the full output vector.
It writes exactly one primitive `PREDICTION.npy`. Its small return value contains
the descriptor, full cell order, profile, consumed-record count1, group-call
count and context-fallback flags. The outer worker writes RESULT.json and its
transport envelope; this helper does not write a competing RESULT.json.

Prediction receives no target array, other query record or feedback. No model
is fit during query handling. Loading different selected cell models is not a
per-cell query exposure: one local record still produces the full ordered
cell vector, as accepted by root and the sole reviewer.

## Passive candidate model admission

`admit_candidate_model(model_path, model_pin, input_store, profile, cell_tokens)`
uses the same pinned model reader, verifies the declared profile/cell axis and
returns passive metadata plus primitive arrays. NPY1 headers, little-endian
primitive types, exact dimensions/extent, no trailing content and finite state
are checked by the owner reader and admission helper. Object/pickle arrays and
callables/modules/custom objects are never interpreted or loaded.

Candidate metadata may describe an opaque architecture as strict passive JSON.
The helper does not require a reference architecture or claim that arbitrary
parameter dimensions implement the declared predictive algorithm. It verifies
the model's transport cell axis and every numeric descriptor/header; algorithmic
shape meaning remains the candidate program's responsibility.

Reserved operator-private keys for label attestations, permutation/seed/receipt
or inverse mappings, private indices/source rows and physical-trial identities
are rejected recursively (including when nested). Ordinary candidate-local
`random_seed` is permitted. This does not establish that arbitrary encoded
strings cannot conceal a secret; the owner's exposure boundary must ensure
that candidates never receive private mapping/attestation material to begin
with. Reference models can contain their private label provenance and remain
strictly outside candidate namespaces.

`validate_bundle(..., kind='candidate', profile=..., cell_tokens=...)` checks
`paper_i_candidate_bundle_v1` with the same complete group/output-cell rules.
`admit_candidate_bundle(...)` additionally admits every primitive group and
returns a compact artifact-admission report. It never executes candidate code,
architecture imports or predictions. Valid artifacts do not establish model
competence or task readiness.

## Focused integration control

`reference/worker_controls.py` runs one bounded invented RAM-only batch using
the actual owner save_model/load_model/put_numeric/put_json/strict NPY1 header
logic. Its RAMStore replaces filesystem capture/publication only; all model
and array bodies stay in RAM. Two tiny invented fits exercise raw ridge and
context-average groups, nested paths, reordered complete cell assembly and
unchanged cumulative Store accounting. Further controls reject incomplete
bundles, traversal, profile/cell substitutions, bad pins, executable metadata,
private shuffle records, object NPY headers and nonfinite primitive state.

The control does not instantiate a disk Store, run Docker/native tools, read
scientific data or claim durability/native/model competence. The receipt pins
the exact owner dependency source used, including the relative-parent Store
fix, and retains every expected rejection. Later owner changes require their
own review; the receipt is not a claim about untested future versions.
