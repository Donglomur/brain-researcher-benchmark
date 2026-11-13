# NEURAL-059 complete process source

This additive source distribution supplies the complete NEURAL-059 caller for
29 sessions, 13 animals and 7 laboratories. The sibling `complete-process-v1`
contains the unchanged 42-file process implementation. Its source manifest is
`f2ff8dae17f93ce10a4986f69f73bf86800f4863e21c0279edc4f243d6d6b56b`.
The existing task manifest and older exposed 93-query pilot are unchanged.
This component remains inactive and scientifically unqualified. Public source
availability, configuration acceptance and process closure are distinct from a
scientific result; none adds another benchmark to the count.

The four information conditions are SH, SHN, SBH and SBHN, each comparing frozen
programme F with investigation I under equal role and model ceilings. The full
caller preserves all 29 sessions and both actor arms, the prior and original L/H
reference families, and 40 reference diagnostic panels (20 D-label and 20
D-neural). Its 61,132 declared reference fit slots are 1,972 primary plus 59,160
diagnostic slots. Declared slots do not mean successful completed fits. Native
failures and unavailable scientific cells remain failures or unavailable cells.

## Files and source capture

Keep the two directories as siblings. Do not add Python files beneath
`complete-process-v1`: its captured loader rejects a changed Python roster.
`prepare_selection.py` is the concrete configuration entry point. It authenticates
the accepted capsule, imports its captured schema validators, verifies the public
ordinary member roster, reads three explicitly supplied JSON configurations,
and writes one new selection. It does not start Docker, import native numerical
packages, load a model, open described data or checkpoint files, or acquire assets.

`members.json` is the original ordered, seven-field public asset-descriptor
projection: 8,148 bytes, SHA256
`2d7b37af47a41fceedef09c4591984b942ee40ab2d3ea5530827e8f7dd32db58`.
It names the original sessions and public asset identifiers; it contains no spike
arrays or targets. The source also checks the seven-field projection without its
terminal newline (8,147 bytes; SHA256
`1ca385428a08c993dc68ba21992601f70b4fad7917bcbbc74533b710536b4ffc`).
No asset named by this metadata is bundled or opened by configuration preparation.

## Prepare a future selection

1. Copy `selection.template.json`, `model.template.json` and
   `native-profile.template.json` to a private configuration directory on the
   intended deployment host. Supply actual identities and finite resource limits.
   Keep five fields null for derivation: `source_sha256`, `deployment.code_root`,
   `members`, `model.configuration` and `native_profile`. Every other null must be
   replaced explicitly. Do not substitute zero for an unknown measurement.
2. Supply the complete raw structured input descriptor, all eight frozen policy
   descriptors, a complete immutable checkpoint file manifest, native package
   manifests, and actual global F-development measurements and evidence. Input
   descriptors contain literal absolute `path`, `bytes` and lowercase `sha256`.
   Checkpoint manifest paths are relative to its selected root. Nothing is
   discovered, downloaded, or guessed by the preparation command.
3. Invoke the command below using actual absolute paths. `ABS_*` denotes a value
   to replace, not a supplied path. The command writes `ABS_NEW_SELECTION` with
   exclusive creation and emits a JSON instruction record on stdout. It leaves
   the original configurations intact. Save the actual stdout and status.

```text
ABS_CONTROLLER_PYTHON -I -B ABS_PUBLIC_DIR/prepare_selection.py ABS_FILLED_SELECTION_TEMPLATE ABS_FILLED_MODEL_CONFIG ABS_FILLED_NATIVE_PROFILE ABS_NEW_SELECTION
```

The output includes the selection's exact SHA256 and `future_operator_argv`.
The interpreter in that argv is the interpreter running preparation, not a
qualified or pinned deployment claim. Prepare on the final selected host/source
location and separately qualify that exact controller interpreter. Changing a
configuration, source location or selection requires a new explicit preparation;
do not edit a prepared selection while retaining its old digest.

Configuration preparation has fixed source/configuration limits: the manifest
and Python source closure are below 2 MiB; each of the three supplied JSON files
is capped at 8 MiB. The emitted selection is capped at the unchanged operator's
1 MiB bootstrap ceiling; the roster is exactly 8,148 bytes.
There is no native or benchmark execution in this command. It may reject an
incomplete template before writing. An output-write or stdout failure can leave
an actual partial or complete selection file; preserve that original outcome and
choose a new output path for any separately selected retry. It never removes or
overwrites an output.

## External deployment and runtime dependencies

The supported backend is an explicitly selected privileged Linux controller with
a dedicated local Docker daemon and cgroup v2; Docker Desktop on a workstation
is not an equivalent admitted host. The selected whole cgroup must already have
separate controller and daemon leaves, cpu/memory/pids controllers enabled,
enforced whole memory and PID maxima, and zero swap. The controller is the sole
initial member of its leaf. The dedicated daemon starts with no containers and
uses its explicitly selected local socket, root directory and cgroupfs driver.
The Docker client and daemon executables are exact hashed operands. A separate
empty credential-free Docker config directory is required. Source does not
provision or qualify this privileged deployment.

Every worker uses an explicitly selected immutable `sha256:` OCI image, nonroot
UID/GID 65534, read-only root and selected source mount, no network, no additional
capabilities, no-new-privileges, active seccomp, isolated processes, and bounded
`/work` and `/channel` tmpfs bytes/inodes. The owner validates these properties and
retains original process/container/cgroup observations and unknown-create
recovery. It refuses unresolved closure. Image IDs and host paths are external
selections, never examples promoted to facts.

The controller needs the Python standard library and NumPy for the retained
preparation reduction. That host NumPy path is separate from the reference
container profile: the source records `package_authenticated=False` and
`authentic_source_parity=False` for those reductions. Providing a reference image
does not resolve that hold. The reference image needs NumPy 2.2.6, SciPy 1.15.3
and an explicitly selected scikit-learn version, complete non-bytecode package
manifests, exact original HGB/optimizer signatures and a finite native-state byte
cap. The native profile validator checks runtime capability when actually run.

The model image needs explicit compatible PyTorch and Transformers/tokenizer
dependencies and a complete locally supplied checkpoint. No model or package is
downloaded. The checkpoint root must already be read-only to the controller and
match the entire selected file namespace. Two arm-owned resident model services
load immutable CPU float32 weights once. Each request uses a fresh message/tensor
state, the same frozen seed, greedy generation, `use_cache=False`, no carried
conversation/KV state, and exact token accounting. Candidate access is only the
bounded owner RPC mediator. Runtime/template compatibility and practical cost
remain to be demonstrated for the actual chosen model.

The source reserves one concurrent actor, 29 reference workers and two model
services, plus controller/daemon headroom. All eight actor roles and model token
ceilings must match across F/I and the four conditions. Whole-lifetime budgets
include managed reads/writes, CPU, wall time, files, model calls and streams;
per-role limits add memory/PIDs/tmpfs/inodes, request/response/artifact/journal
caps, CPU and wall time. `closure_reserve_seconds` is part of the whole wall
ceiling. Native physical I/O and internal candidate fit counts are not inferred
from managed counters. These limitations survive publication.

## Candidate and protected-scoring boundary

Each globally frozen F source and I policy is captured before authentic input
opening. `fit(calibration, tools)` receives the selected session/condition's
labeled training and validation views. It returns nonempty byte bodies with exact
keys `source_body`, `config_body`, `state_body`. F must return its original frozen
source unchanged; I may produce a captured session-specific prediction source.
Both are then closed. Every query runs `predict(view, config_body, state_body,
tools)` in a fresh process with the exact committed artifacts and no query label.
It returns a probability of left choice. `tools.model` accepts exactly
`{"messages": [...], "max_new_tokens": ...}` and returns text and actual usage.
The resident model prepends the selected common system prompt; candidate messages
may contain user/assistant roles only.

`prior_policy.example.py` is an unselected, intentionally simple ABI example.
It demonstrates byte artifacts and the real `/input/policy.py` source mount;
the worker's `__file__` value is a captured-source sentinel. It is not a
scientific baseline result, a selected F/I comparison or an improvement claim.
Do not silently assign it to all eight policy operands.

The complete prediction barrier and actual worker closure precede each protected
grading activation. Target-bearing operands are never candidate/model inputs.
The operator preserves scientific unavailable states, failed-cost prefixes and
uncertain process outcomes. Its final record explicitly requires an **external
supervisor** to observe controller exit and final whole-group/daemon closure,
including startup/exit outside the owner's last sample. Running the emitted argv
without that selected supervision is not qualification. No generic wrapper or
synthetic receipt in this distribution claims otherwise.

## Scientific and release status

All G01–G24 authentic source/science gates remain unpassed. The structured input
extractor, authentic inputs, qualified deployment/images/interpreter/model,
measured global F development and actual native/scientific execution are external
requirements. See the input and rights notices shipped alongside this document.
The retained dormant donor modules `donor/seals.py` and a dormant contrast-report
function in `donor/resource_policy.py` refer to their original `.registry` or
`.reporting` modules. Those are not active imports/calls of this selected
operator/worker graph and are not supplied as a reusable donor library API.
No missing dependency is invented to activate those unrelated donor paths.
