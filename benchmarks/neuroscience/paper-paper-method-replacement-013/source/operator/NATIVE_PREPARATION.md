# Native Neuroformer input producer

`native_dataset.py` adds a real, separately named native input producer to the
existing paper assignment. It consumes the authors' five original VisNav files
and builds the captured original `Tokenizer` and three `NFDataloader` objects.
It does not fit a model, reproduce a paper result, score a candidate, or create
the prospective five-millisecond bridge. This assignment remains source-partial
and scientifically unqualified.

## Actual caller path

`prepare(request, array_root, source_root=None)` first deep-copies and admits the
request. It authenticates the 6,237-byte source index and all 26 original text
bodies from revision `36ed94084628c253098d448048c980d3dea0050d` against both SHA-256
and Git blob identities. Only the selected function/class AST definitions are
compiled. Original imports, download code, training/inference entrypoints,
logging setup, path mutation and model construction are not run.

The producer captures four caller-specified provenance records, then each of the
five NPY files through no-follow directory/file descriptors. Captures reject
hard links, size changes and digest mismatches. NPY v1/v2 headers must match the
declared numeric dtype, C order, shape and exact payload length. NumPy arrays
refer to captured immutable bytes. No later array-path lookup supplies values.
All numeric dependencies are imported lazily inside `native_runtime()`; importing
the producer itself uses only Python's standard library.

The request is a dictionary with exactly these fields:

- `schema`: `neuroformer_native_recording_v1`.
- `cohort`: `medial` or `lateral`; `recording_id`: an explicit source identity.
- `seed`: a nonnegative integer below 2^32.
- `config`: one of the four captured `configs/Visnav/lateral/*.yaml` files listed
  in `CONFIGS`. `config_status` is `released_lateral_config` for lateral, or the
  explicit `lateral_config_on_medial_unqualified` for medial. There is no captured
  medial original configuration and this adapter does not invent one.
- `assets`: exactly `spikes`, `speed`, `stimulus`, `phi`, `th`. Each descriptor has
  `path`, `bytes`, `sha256`, `dtype`, `shape`; paths are canonical relative paths
  beneath the selected array root. All five inputs are required for either
  cohort, matching the original loader's actual file requests.
- `provenance`: `acquisition`, `clock_alignment`, `physical_units`, `run_mapping`,
  each an exact `path`/`bytes`/`sha256` descriptor. Body hashes establish capture
  identity only. They do not authenticate a scientific claim inside a record.
- `limits`: all five positive integer bounds `max_file_bytes`,
  `max_total_input_bytes`, `max_intervals`, `max_repetitions_per_window`,
  `max_scan_values`. Aggregate bytes include **381,385 source/index bytes, all
  four provenance bodies and all five arrays**. Provenance is additionally
  limited to one MiB each. No source read occurs before aggregate admission.

Native rates have shape `[1905,T]` medial or `[2022,T]` lateral, float32/float64,
on the ten-millisecond source clock. T must be divisible by five; an unaligned
recording tail is an unresolved acquisition case, not silently discarded.
Behavior streams retain their original scalar layouts `[T/5]` or `[T/5,1]` and
float32/float64 dtypes. Video follows the source-documented
`[T/5,1,64,112]` layout; float32, float64 or uint8 is admitted. Other authentic
layouts require a separate source-backed extension. No array headers or actual
recordings were opened to claim these declared layouts are present locally.

The producer scans full finite-value support and bounds all positive rounded
repetitions over each possible five-bin current/history window **before** the
original code allocates repeated ID/time lists. Negative values keep the original
empty-list repetition behavior and are reported; rates are not multiplied by dt
or asserted to be physical spike counts. Values are not thresholded, downsampled,
clipped or replaced by simulated observations.

`PreparedNative.intervals` retains complete `all`, `train`, `test`, `finetune`
vectors. `item(split,index)` calls the original dataset `__getitem__` and returns
its original `(x,y)`, including behavior and video. `tokens(split,index)` calls
the original previous/current interval and token producers. Both reject missing
splits and indices outside support; neither selects a convenient subset. Returned
observations, targets, IDs and support must remain operator-private.

`construct(request,bodies,arrays,runtime)` is the lower-level interface used by
the capture path and engineering controls. Its contract requires already
authenticated source/immutable arrays. Injected numerical/config-parser leaves
are trusted caller dependencies, not an alternative authenticity mechanism.

## Preserved source semantics and disclosed amendments

The original source draws 80% of interval indices without replacement, retains
draw order in training, forms the test complement in original order, and takes
the first floor(1% of training) for fine-tuning. A local NumPy `RandomState(seed)`
uses the source's MT19937 family while isolating unrelated global random draws.
This binding assumes no earlier RNG draws; a historical seed/split identity still
requires authentic run records. Initial zero and negative-history windows remain.
The source's early behavior-window shape mismatch may therefore still fail.

The selected last `round_n` definition matches Python's effective module binding.
Rounded-rate repetition remains ordered by time bin then neuron. Original ID and
dt overflow truncation remain asymmetric; original padding semantics remain.
Current/history are 50 ms, video context is 150 ms, and the actual default video
clock is 50 ms. The source requests video ending at neural endpoint + 50 ms;
this adapter makes no causal-prediction assertion.

One source-amended ownership boundary copies the exact selected video window
before calling the original callback with equivalent relative coordinates.
PyTorch does not enforce NumPy's read-only flag; the copy prevents a returned
video tensor from modifying immutable captured input bytes. The copy is at most
the selected frame window, not the full recording. It is an engineering ownership
change, not an inferred scientific preprocessing step. Native memory/runtime and
numerical parity remain unmeasured. The explicit input/expansion bounds do not
prove an RSS ceiling or grant authority to run this path on original data.

The original `get_interval` overwrites its `data` argument, defeating the released
generated-history override. This producer deliberately exposes no rollout API
that pretends that branch works. Original training receives the historical test
dataset, so those data cannot be described as a protected improvement holdout.

## Remaining assignment scope

All 63 predecessor ordinary source roles are preserved byte for byte, including
the full 46-slot PANEL (39 source-conditioned and seven prospective slots),
existing prepare/scoring interfaces and wider scientific source. The external
primary-paper PDF descriptor remains unchanged; its body is neither read nor
copied into this packet. Existing historical status/source maps remain evidence
of their time; `NATIVE_PREPARATION_STATUS.json` describes this successor.

No obligation is retired by this producer. Remaining work includes native
runtime/dependency qualification, authentic arrays and provenance, original
run/config/seed/split mapping, source-to-five-ms conversion or scientifically
justified protocol revision, speed class quantization, original training and
baseline recipes, current-source generation repair/evaluation, exact Figure 6
metric selection, full matched-support inference, and protected improvement
evaluation. The wider simulation, passive-control, variability, geometry,
representation probing, CEBRA and training-curve families remain required and
unimplemented or unqualified. These are not represented by the 46 primary slots
alone. No new benchmark count or scientific-ready count is justified here.

## Engineering evidence

The author controls execute actual selected source definitions, the native
constructor and request/file/NPY admission. Their RNG, ndarray, tensor and YAML
parser leaves are explicitly inert. They test both full cohort shape contracts
using virtual scalar controls, never an original biological recording. Independent
review separately tests source edge cases and the complete caller path. These
controls do not establish native-library equivalence, original split identity,
dataset availability, paper reproduction, model performance or SOTA.

Current construction authority is source work only. The future `prepare` call
above is an implemented interface, not an instruction to execute scientific work.

## Later source component

`protected_rollout.py` supplies a separate source-amended current-token and generated-only-history component. This preparation API still returns original datasets and performs no rollout. The new component does not qualify original run mappings, the5ms bridge or authentic native execution; see `PROTECTED_ROLLOUT.md`.
