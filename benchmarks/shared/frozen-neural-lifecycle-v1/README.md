# Frozen neural programme lifecycle

This operator controller closes the method-order gap exposed by the development
difficulty pilot. It serves the existing **NEURAL-007** and **NEURAL-077** feature
programme conditions. It adds no task IDs, new biological result, or scientific
qualification. No new agent solver or private grading was run to construct it.

The controller stages exact public assets, records a method and complete source
commitment before any development execution, starts a fresh programme process for
each person, admits complete responses, freezes one canonical submission, and only
then permits the unchanged registered native scoring CLI. Failures are terminal
within that attempt; source changes and reruns require a separately registered
attempt whose relationship to the failed attempt remains an operator obligation.

## What is enforced

- Exact public descriptors and byte/SHA256 pins are checked before copying only
  allowlisted inputs. No parent-directory copies from the authoring tree and no
  target reads occur. All six training people and both development people remain.
- `METHOD.md`, all candidate source and fitted artifacts, the entrypoint, Python
  executable, controller, child bootstrap, input inventory and native scorer
  source closure are committed before the first development process. The method
  directory must contain the complete programme and trained artifacts; undeclared
  external dependencies are not content authenticated by this controller.
- Both original and frozen method trees and public inputs are checked before and
  after each process. Each person receives separate source/input copies, scratch,
  output, process ID and process group. No mutable per-person state is carried by
  the controller. Read/write access outside those paths is prohibited by protocol,
  **not** by a filesystem sandbox.
- Each producer must exit successfully and be reaped with no surviving process
  group before capture. Timeout, descendant, resource setup, malformed output and
  unexpected receipt failures are retained; owned groups are killed and parents
  reaped on exceptional exits. Processes escaping the group are outside the
  cooperative containment claim.
- Responses reject duplicate/missing/foreign IDs, duplicate JSON keys, extra
  fields, booleans, nonfinite numbers, out-of-range probabilities and invalid sleep
  simplexes. No clipping, normalization, missing-row fill or easy subset is used.
- Both complete per-person responses are authenticated again before generating a
  deterministic uncompressed native NPZ. All 400 EEG trials or all 5,450 sleep
  epochs are committed before the private scoring route can be invoked.
- The native score route checks the frozen submission before and after invocation
  and retains the native failure. It does not substitute a grader or weaken any
  existing source, target, comparator, metric or Docker admission.

## Remaining boundaries

The append-only, hash-chained receipts detect ordinary later edits and sequencing
mistakes. The operator and storage are trusted. An actor with unrestricted host
write access can rewrite both state and receipts; this is not cryptographic
protection from that actor. The controller cannot prove that authoring tools never
read development cases or ran an earlier programme outside it. The author must
declare this commitment before their first development execution, and an external
study operator must track attempts and enforce authoring access. Existing exposed
development people are not an untouched confirmation panel.

Candidate programmes use the resolved Python executable under `-I` with
method-local imports and without inherited Python configuration. Only that
executable's enabled system site packages are available; user-site packages and
`PYTHONPATH` are disabled. Resolving a virtual-environment symlink does not retain
its environment, so this version requires the scientific packages in the resolved
interpreter's own enabled site path. The current macOS NumPy installation is in
user site and an independently retained generated import control failed under
`-I`; no usable scientific runtime is claimed here. The complete binary dependency
environment is not hermetically pinned. Seven common numerical thread settings are fixed to two;
these settings do not impose a hostile-program CPU quota. Authentic candidate
execution requires Linux and a successful **2 GiB `RLIMIT_AS`** admission, plus
CPU/file/descriptor limits and a 120-second wall limit per person. Unsupported
hard-memory setup fails before candidate code. The current macOS construction host
therefore prepared authentic inputs but did **not** execute authentic programmes.
Generated tiny standard-library controls run separate actual processes and record
their lack of hard-memory qualification; they cannot establish native execution
readiness or model performance.

Both registered native scorers require **4 GiB**. The default 2 GiB controller
budget refuses grading before dispatch. The construction wave did not raise this
budget or execute those scorers. They additionally require the exact qualified
Docker image and complete authenticated historical runtime layout. The public
repository's relocated `registered-runtime` directories alone do not satisfy that
layout. Native deployment and end-to-end private scoring remain unqualified here.

## Operator commands

Run from the repository with existing local public assets. `RUN` must be new and
outside the public repository. `ASSET_ROOT` is a root containing the exact paths
named in the original public descriptor. The controller accepts only known pinned
public assets; it never follows a whole parent directory as an input packet.

```sh
python3 -I -S -B benchmarks/shared/frozen-neural-lifecycle-v1/lifecycle.py prepare \
  --task NEURAL-077 --asset-root "$ASSET_ROOT" --run "$RUN"
python3 -I -S -B benchmarks/shared/frozen-neural-lifecycle-v1/lifecycle.py commit \
  --run "$RUN" --source "$METHOD_DIRECTORY" --entrypoint candidate.py
python3 -I -S -B benchmarks/shared/frozen-neural-lifecycle-v1/lifecycle.py execute --run "$RUN"
python3 -I -S -B benchmarks/shared/frozen-neural-lifecycle-v1/lifecycle.py freeze --run "$RUN"
python3 -I -S -B benchmarks/shared/frozen-neural-lifecycle-v1/lifecycle.py inspect --run "$RUN"
```

Use `--task NEURAL-007` for sleep. The candidate entrypoint receives `--request`
and `--output`. The request identifies the task and current person, complete IDs,
training directory, current-person observation directory and optional helper
directory. Write exactly one `predictions.json` at the requested output path:

```json
{"ids": ["the supplied IDs, each once"], "probabilities": [0.5]}
```

For EEG, each probability is a scalar target probability. For sleep, each item is
a five-number row in fixed `W,N1,N2,N3,R` order whose sum is within `1e-6` of one.
Every supplied ID is required; the one-row illustration is not a valid submission.
Only the controller creates the final registered NPZ. Author training and method
selection must finish before `commit`; inference cannot revise the committed
method or use the other person's observations. The EEG condition uses the pinned
engineered features and permitted nuisance/history variables. The sleep condition
also includes shared YASA outputs and its helpers. Neither is a claim of native
LLM waveform understanding, and matching cases with a waveform/direct condition
does not establish matching observations.

The optional `grade` command is for a later, separately authorized deployment with
the existing 4 GiB budget and native prerequisites. Supply `--runtime-root` pointing
to a legacy tree whose registered package is byte-identical to the committed
current package: `benchmarks/neuroscience/neural-077` or
`benchmarks/neuroscience/neural-007-whole-night-sleep-scoring`. Existing historical
asset/helper/source pins and scorer-owned Docker checks still apply. The operator
must populate that exact trusted layout; this package does not rewrite pins or
automatically move private data. `--memory-budget-bytes 4294967296` is an explicit
resource admission, not something to use under the construction wave's 2 GiB cap.

## Validation and authentic preparation

```sh
python3 -I -S -B -m unittest discover \
  -s benchmarks/shared/frozen-neural-lifecycle-v1/tests -v
```

The tests use full-size generated panels and real tiny per-person child processes.
They cover ordering, double execution, source/input/output/receipt tampering,
complete population, malformed probabilities, producer failure and cleanup, and
the private-action/memory gate. The instrumented private action is a test seam,
not a scientific reference or oracle. Native NPZ writing is standard-library only.

The construction operator independently authenticated and copied the authentic
public feature packet for both tasks: EEG six training people and two development
people /400 trials; sleep six training people /16,290 epochs and two development
people /5,450 epochs, retaining shared model outputs. Only input staging and
public identity extraction occurred. No candidate was fitted, no new prediction
on authentic data was generated, and no private targets were opened. These local
operator packets and receipts remain outside Git. The unchanged registered
scorers retain the pilot's metrics and fixed comparator sets.
