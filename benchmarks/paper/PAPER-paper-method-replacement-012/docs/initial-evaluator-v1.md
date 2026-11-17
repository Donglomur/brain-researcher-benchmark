# NuCLR Bugeon initial evaluator v1

This is an owner-side, executable readout component for the existing
`PAPER-paper-method-replacement-012` contract. It joins session-local identities,
checks author-split projections, fits the pinned linear readout to supplied
embeddings, selects checkpoints using validation labels, and computes paired
context-ablation diagnostics. It does not train NuCLR, acquire Bugeon data,
construct replacement author splits, or establish scientific qualification.
Every result retains `research_qualified: false`, `full_contract_complete: false`,
and the unresolved scientific and release holds.

## Source and estimand

The contract is unchanged (SHA256
`f754a7dba9f43a270143fe1bcd0654a29d4d660626724a07e81593d50dde1bff`).
The author code is pinned to
[`nerdslab/nuclr` commit 0fa409b304147ace00507063d44f03155691af62](https://github.com/nerdslab/nuclr/tree/0fa409b304147ace00507063d44f03155691af62).
The [NeurIPS paper](https://papers.nips.cc/paper_files/paper/2025/file/8f7dc9855bb4ae8ae4f2d649f3f4efe6-Paper-Conference.pdf)
Appendix D.4 defines three Bugeon panels, which this component keeps distinct:

| Panel | Split member suffix | Supervised readout topology | Representation exposure |
| --- | --- | --- | --- |
| `transductive` | `_transductive.pkl` | Author neuron-wise train/validation/test | Test-population activity is available |
| `transductive_zero_shot` | `_transductive_zs.pkl` | Four outer held-out subjects; three subject CV folds inside each | Test-population activity is available |
| `inductive_zero_shot` | `_inductive_zs.pkl` | One SB028 test subject; three subject CV folds | All five SB028 sessions excluded from representation training |

The panel is crossed with `ei`, `subclass`, or `11class`, retaining all nine
registered split variants. Source label maps remain authoritative; this component
does not infer the 11-class map or transfer exclusions from the online training
monitor. Vocabulary sizes are 2, 5, and 11. Source labels are supplied as strings
with an explicit bijection to the published source label family (EC/IN, the five
subclasses, or the eleven Appendix A.8 types); the exact acquired encoding still
requires owner verification.

[`eval_scripts/multi_split_eval.py`](https://raw.githubusercontent.com/nerdslab/nuclr/0fa409b304147ace00507063d44f03155691af62/eval_scripts/multi_split_eval.py)
and its single-split counterpart specify the readout. Training-only scaling
precedes logistic regression (`newton-cg`, C=1, tolerance 1e-4, maximum 1000
iterations). Embeddings are cast to float32 as in the source loader; nonfinite
values after casting are rejected. The `weight` branch uses balanced class weights. The optional
`resample` branch calls the author-specified RandomOverSampler with seed 42 before
scaling and requires an existing imbalanced-learn installation. Missing support
fails explicitly; it never silently changes the balancing method.

CV predictions are concatenated before macro F1 selects the checkpoint; the first
checkpoint in increasing epoch order wins ties. With `train_cv`, final fitting
uses the author outer train IDs (or their documented test complement). With
`val`, final fitting uses train plus validation IDs. Selected test predictions
are concatenated across outer splits before balanced accuracy and macro F1.
Accuracy, confusion counts, support, per-class metrics, and subject diagnostics
are also reported. Balanced accuracy averages recalls over true-present classes;
macro F1 averages over the union of true and predicted classes. A declared class
absent from both receives no invented source-metric contribution. Repeated
appearances across author splits retain the source's occurrence weighting.
Subject metrics are diagnostics, not a replacement for this pooled endpoint.

## Identity, input and use

`implementations/initial-evaluator-v1/evaluator.py` accepts JSON. The packet is
constructed and held by the benchmark owner; candidates must not control its
labels, split membership, provenance, or source-session manifest. This local
library does not implement a protected execution service. It deliberately does
not deserialize pickle or PyTorch objects. An owner must first inspect and export
trusted author artifacts into the JSON fields below, retaining their original
bytes and separate SHA256 acquisition receipts.

Required packet fields:

- `schema_version: 1`, existing `task_id`, pinned `source_commit`, `input_role`
  (`generated_engineering_control` or `authentic_candidate`), `panel`,
  `label_level`, `context_variant` (`population_context` or `ablated_context`), and
  explicit `class_balance` (`weight` or `resample`).
- `provenance`: SHA256 strings for `split_sha256`, `metadata_sha256`, and
  `data_receipt_sha256`; exact `split_member`; `split_release` chosen from
  `paper_era_candidate`, `december_2025_current`, or `other_explicit`; and a
  nonempty `split_release_detail`. These declarations do not authenticate bytes
  or prove that a paper-era candidate is equivalent to the published protocol.
- `source_session_manifest`: complete source session IDs. Authentic candidates
  must declare all 17 source sessions across SB025, SB026, SB028 and SB030.
  Labeled units need not appear in every session when the authoritative label
  map excludes them. `representation_training_sessions` declares all sessions
  used by the representation. Authentic candidates must retain the source's full
  pretraining-session cohort for the selected panel.
- `label_vocabulary`, an exact `source_label_mapping` bijection from those
  encoded labels to the published family, and authoritative `label_map` from
  unit ID to label;
  `metadata` with exactly those labeled IDs, `session_id`, `subject_id`, and
  zero-based `source_neuron_index`. Optional `repeated_cell_id` values are
  reported but do not establish complete linkage. Subject case is normalized in
  diagnostics; the source metadata may use uppercase IDs.
- Ordered `checkpoints`, each with a unique `id`, strictly increasing integer
  `epoch`, identical ordered `ids`, and finite rectangular `embeddings`. Every
  checkpoint must contain every author-labeled unit. No presence-mask omission
  or implicit label filtering is accepted.
- Ordered `splits`, each with unique `id`, `test`, and either `train_cv` (a list
  of `train`/`val` ID lists) or explicit `train` and `val`. The outer `train` can
  be omitted only for `train_cv`, matching the source complement rule. Every
  unused label-map ID must be listed in an `excluded` mapping with an explicit
  source reason. This records author exclusions without silently changing them.

`session_metadata(session_id, ttypes, activity_neuron_count)` reproduces the
source `_u<index>` identity and EI/subclass derivation while checking calcium
column and neuron-label counts. It does not supply repeated-cell linkage; the
source's `neuron.UniqueID` ingestion is commented out. The complete original
calcium, transcriptomic and split joins remain an authentic acquisition gate.

The test directory supplies a small generated packet builder and controls; these
are not empirical data. Run checks from the repository root with an existing
Python that provides NumPy and scikit-learn:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s benchmarks/paper/PAPER-paper-method-replacement-012/implementations/initial-evaluator-v1/tests -v
```

Evaluate a trusted owner packet or compare its matched ablation:

```sh
python3 benchmarks/paper/PAPER-paper-method-replacement-012/implementations/initial-evaluator-v1/evaluator.py owner_packet.json --output result.json
python3 benchmarks/paper/PAPER-paper-method-replacement-012/implementations/initial-evaluator-v1/evaluator.py context.json --ablated ablated.json --output comparison.json
```

Comparison requires identical labels, units, splits, provenance, exposure,
checkpoint identities and epochs; only embeddings and context-arm identity may
differ. Each arm selects its own checkpoint by CV. The report gives pooled and
subject-level differences, with no significance or improvement qualification.

## Prospective engineering policies and limits

Strict complete-ID joins, explicit exclusions, source-session checks, fold
subject checks, convergence rejection, finite inputs, declared archive releases,
and matched-arm validation are prospective safeguards. The source's permissive
presence masks are not used to silently omit units. Test fitting occurs only
once for each selected checkpoint instead of fitting and exposing every test
checkpoint. This preserves the deterministic selected source readout while
reducing unnecessary test exposure. It does not provide process isolation.

The component consumes author splits rather than regenerating the paper's
approximate 80/20 proportions. Exact released split membership, stratification,
repeated-cell linkage, post-conference changes, reference tolerances and split
rights still require owner review. Neither a successful packet validation nor
an `authentic_candidate` label closes those gates.

Local controls cover all three split topologies, earliest checkpoint ties,
selected-test-only fitting, train-only scaling under a large test-only feature
shift, complete identities, leakage rejection, context-ablation matching, and
hand-derived confusion matrices checked independently against scikit-learn.
The existing Homebrew Python 3.11 runtime was used without installations;
imbalanced-learn was unavailable, so that branch is explicitly unverified beyond
its missing-dependency rejection. Generated controls establish implementation
behavior only. Native baseline runs, multi-seed paper figures, calibrated
minority-class/label-efficiency improvement, protected references, scientifically
independent replication, and the native resource envelope remain open.

The source code license is Apache-2.0, and original Bugeon data are recorded as
CC BY 4.0. Author metadata and split archive redistribution rights remain
unresolved. No upstream payloads, archives, model weights or paper results are
redistributed in this package. `provenance.json` records the source-to-component
mapping and distinguishes immutable source revision pins from browser-rendered
retrieval evidence hashes.
