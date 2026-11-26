# Run the exposed EEG and sleep development routes

A fresh checkout can verify the delivered source, inspect explicitly provisioned
inputs, stage the existing programme packet and invoke the existing native graders.
No download, Python package installation or solver call occurs automatically.
The packaged data descriptors fix the required bytes: arbitrary recordings from
the same study cannot replace those artifacts.

These routes cover **NEURAL-077: 400 EEG trials** and **NEURAL-007: 5,450 sleep
epochs**, each from the original two development people. Both people were already
exposed during construction. Successful execution is evidence about this software
and supplied submission; it does not establish an unseen holdout, direct LLM
understanding, complete task qualification or scientific improvement.

## Verify and inspect

From the checkout, with Python 3.11 or later:

```sh
python3 -I -S -B scripts/neurobench.py operator routes
python3 -I -S -B scripts/neurobench.py operator inspect NEURAL-077 \
  --data-root /operator/asset-root --output /operator/evidence/inspect-eeg
python3 -I -S -B scripts/neurobench.py operator inspect NEURAL-007 \
  --data-root /operator/asset-root --output /operator/evidence/inspect-sleep
```

Every output directory must be new, outside the checkout, with an existing private
parent. Source checks authenticate the bounded current executable closure in
[`operator-sources.json`](../src/neurobench/operator-sources.json) before importing
or running task code. The checkout and its inventory remain trusted inputs; a hash
is not an independent attestation. Missing or changed sources fail closed.

`--data-root` supplies the paths relative to the native
[EEG assets manifest](../benchmarks/neural/NEURAL-077/implementations/registered-runtime/assets.json)
or [sleep public manifest](../benchmarks/neural/NEURAL-007/implementations/registered-runtime/public_assets.json).
EEG inspects six training and two development feature packets; sleep inspects six
training and two development packets, the shared model outputs and two helper
files. All files are hashed against the packaged pins, and complete development
IDs are checked. Only the explicit public allowlist is opened; no recursive scan
of a private data root occurs. Training labels are part of the selected public
training assets. Development targets are never inspected by this command.

For an existing frozen-lifecycle packet, pass its **`inputs/` directory** with
`--layout prepared`. The original native manifest, rather than that packet's
self-reported receipt, authenticates the same members. `prepare --layout prepared` also accepts this directory: it first authenticates
the complete allowlist, copies only those pinned members into the original relative
layout inside its fresh output, and invokes the unchanged native preparer. Both
copies remain in the evidence directory; allow about 23 MB for sleep or 21 MB for EEG.

`operator.json` preserves member-level mismatches, missing inputs and the exact
source identities. `routes` reports source availability only. It does not infer
local data availability, successful grading, a model evaluation or qualification.

## Stage and run a frozen programme

```sh
python3 -I -S -B scripts/neurobench.py operator prepare NEURAL-077 \
  --data-root /operator/asset-root --output /operator/evidence/prepare-eeg
python3 -I -S -B scripts/neurobench.py operator programme NEURAL-077 commit \
  --run /operator/evidence/prepare-eeg/lifecycle --source /operator/method \
  --output /operator/evidence/commit-eeg
python3 -I -S -B scripts/neurobench.py operator programme NEURAL-077 execute \
  --run /operator/evidence/prepare-eeg/lifecycle --output /operator/evidence/execute-eeg
python3 -I -S -B scripts/neurobench.py operator programme NEURAL-077 freeze \
  --run /operator/evidence/prepare-eeg/lifecycle --output /operator/evidence/freeze-eeg
```

The dispatcher uses the existing [frozen lifecycle](../benchmarks/shared/frozen-neural-lifecycle-v1/README.md),
which retains complete-method commitment, separate per-person processes, complete
response coverage and failures. Authentic programme execution requires the existing
Linux 2 GiB hard-memory admission and a suitable isolated Python environment;
macOS refuses authentic execution before candidate code. This revision's controls
do not execute a new authentic candidate. `programme ... inspect` returns its
recorded history; the dispatcher also authenticates the packet and task identity.

For sleep, prefer the existing externally anchored
[finite-attempt audit](../benchmarks/neural/NEURAL-007/implementations/finite-attempt-audit/README.md).
Use `operator sleep-audit NEURAL-007 commit|complete|verify --run RUN --output NEW`
with the audit's `--witness`, `--source`, `--entrypoint`, `--witness-bytes`,
`--witness-sha256`, `--final-witness`, `--final-bytes` and `--final-sha256` arguments
as appropriate for that step. The dispatcher accepts the same named fields and
forwards them to the existing audit. `complete` executes and freezes the committed
programme; it is not just a metadata check. Keep commitment and completion digests
in independent operator custody. Neither the lifecycle nor a finished-file score
proves unobserved authoring history or hostile-host isolation.

The [EEG complete waveform delivery](../benchmarks/neural/NEURAL-077/implementations/complete-direct-condition-v1/README.md)
and [visual viewer](../benchmarks/neural/NEURAL-077/implementations/visual-viewer-v1/README.md)
remain distinct input conditions. Do not give feature packets, their training
labels, raw arrays or scoring reports to a viewer-only participant.

## Validate and grade completed submissions

Provision a local Docker CLI, local Unix socket, Docker configuration and the
exact already-installed image required by the adapter. Pulling is disabled.
The [EEG portable adapter](../benchmarks/neural/NEURAL-077/implementations/portable-grading/README.md)
and [sleep portable adapter](../benchmarks/neural/NEURAL-007/implementations/portable-grading/README.md)
document their small task-specific artifact-location descriptors. Each separates
its public validation locations from private target/reference locations; pins
come from published source, never from an operator replacement hash.

```sh
python3 -I -S -B scripts/neurobench.py operator validate NEURAL-077 \
  --artifacts /operator/eeg-public-locations.json --submission /operator/submission.npz \
  --docker-cli /absolute/path/to/docker --docker-host unix:///absolute/path/to/docker.sock \
  --docker-config /operator/docker-config --purpose development-control \
  --output /operator/evidence/validate-eeg
python3 -I -S -B scripts/neurobench.py operator grade NEURAL-077 \
  --artifacts /operator/eeg-score-locations.json --submission /operator/submission.npz \
  --docker-cli /absolute/path/to/docker --docker-host unix:///absolute/path/to/docker.sock \
  --docker-config /operator/docker-config --purpose development-control \
  --output /operator/evidence/grade-eeg
```

Use `NEURAL-007` and its descriptor for sleep. `grade` first validates the whole
submission in a public-only stage. A rejected or incomplete submission cannot
start the private stage. The native scorer preserves the original metrics and
fixed references, resource admission, network-disabled/read-only containers and
owned-container cleanup. Grading requires 4 GiB; run under the operator's shared
resource allocation. Only explicit owned container identities may be removed.

`--purpose` is mandatory: `development-control` labels an engineering control;
`model-evaluation` labels a supplied model output. The latter still records that
independent method provenance is missing. To substantiate a programme evaluation,
retain and verify the separate frozen-method history and bind its exact submission
pin to the native result. Purpose text, receipts and source hashes cannot confer
scientific qualification.

Each command preserves `operator.json`, the exact dispatch, stdout/stderr and the
native adapter's source capture, submission capture, result and stage/cleanup
receipts under `native/`. Preserve failed runs and use a new destination for every
attempt. Exit 0 indicates completed operation, 2 a native-rejected submission and
3 an operator/source/input/runtime/scoring failure. After a child returns,
`operator.json` records its exact `child_returncode`, including negative signal
codes. Nonzero prepare/programme/sleep-audit exits map to 3; validate/grade retain
native 0/2/3 and map unexpected exits to 3. A missing or invalid native result can
still make the operation fail with 3 regardless of the child return code.
Outputs can contain private
aggregate scores and operator paths: retain them outside public Git and participant
access. Filesystem permissions prevent accidental exposure/overwrite; they are not
a security boundary against the trusted host owner.
