# Selected combined-view and numerical-programme workflow

This entry point selects the existing seven-mouse combined calcium/behavior task:
seven fresh held-mouse folds, 120 labeled training windows and 20 queries in each
fold, and all 140 original probabilities. Neither folds nor access conditions
are new benchmarks. The original numerical programme owner, immutable image,
private grader, equal-mouse balanced accuracy/log loss and six fixed reference
results remain unchanged. The programme can build tools using its active fold;
the viewer receives typed images. This is a comparison of workflows and
representations, not a causal tools-only effect or no-tools model qualification.

The original image is locally available on the inspected Mac. The original
combined viewer has a separately recorded complete authentic scripted transport
control. This addition has source/generated checks only. No programme lifecycle,
private grading, fitting or model evaluation was run for this addition.

## Source selection and deployment

Use Python3.11+ with NumPy for operator commands and an installed framework
Python for the macOS viewer participant. `workflow.py` verifies its externally
selected `SOURCE.json` and the complete original portable source before launch.
`CURRENT_SOURCE.json` selects exactly three already-existing portable source
repairs (`provision.py`, `check_result.py`, `tests/test_relocation.py`) using the
original provisioner's explicit successor interface. The historical manifest
is retained byte-for-byte; execution source and scientific pins are unchanged.
The source tree must be trusted and quiescent through delegated execution.
The operator authenticates the published package before starting Python;
`deployment.py` is imported at startup. Internal hashes check consistency before
task dispatch, not safe execution of an untrusted package or hostile host.

Set `FLOW` to the absolute path of this directory, `PYTHON` to the installed
operator interpreter, and `RELEASE` to the independently authenticated published
SHA256 of `SOURCE.json`. Example commands below require the operator to supply
their actual canonical paths and an authorized attempt review; they do not
allocate resources or create approval records.

```sh
"$PYTHON" -I -B "$FLOW/workflow.py" --release-sha256 "$RELEASE" runtime-check \
  --docker /usr/local/Cellar/docker/29.4.0/bin/docker \
  --host unix:///Users/nicholas/.docker/run/docker.sock \
  --config /operator/empty-docker-config
```

The dedicated config directory must exist and contain nothing except an optional
empty `{}` config.json. The check uses an explicit Unix Engine socket, the exact
image ID, original Linux/ARM64 platform, six ordered layer identities and selected
configuration. It has a 10-second CLI deadline and 16KiB combined output cap.
It starts no container, pulls nothing and emits `runtime_qualified: false`.
Mutable tags, another architecture, image replacement and nonempty credentials
are refused. Docker executable symlinks must be resolved before selection.

The selected image is
`sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156`,
observed size539,583,315 bytes. Python3.12.8, NumPy2.2.6 and SciPy1.15.3 are
declared build dependencies, not an executed installed-version observation here.
The historical Dockerfile pins a mutable Python tag and top-level versions,
not the base digest, wheels or complete dependency resolution; rebuilding it does
not reproduce this image identity. No registry digest or exact transfer archive
is distributed with this package.

For a second machine, obtain a separately authorized export from a trusted daemon
already holding the exact image: `docker image save --output NEW_ARCHIVE IMAGE_ID`
using the same explicit `--host` and dedicated `--config`. Record the completed
ordinary archive's exact byte count and SHA256 through a trusted channel. The
recipient verifies both before `docker image load --input ARCHIVE` and repeats
the exact ID/platform/layer inspection afterwards. Saving/loading requires its
own storage and time allocation; neither operation is performed here. Image
availability is not relocated runtime or participant-isolation qualification.

## Provision the existing inputs once

The existing `neural034-portable/templates/input-locators.example.json` names the
ten external objects: all seven active-fold NPZs, public panel, private targets
and private references. Original input pins are unchanged, total30,649,610 bytes.
No download occurs. The input locator document and entire workspace are private
operator resources; another fold's training labels expose this fold's answers.

```sh
"$PYTHON" -I -B "$FLOW/workflow.py" --release-sha256 "$RELEASE" provision \
  --inputs /operator/input-locators.json --workspace /operator/neural034-workspace
```

The unchanged provisioner authenticates source first and all ten inputs while
streaming to a new0700 workspace, with its original120-second deadline. Keep its
terminal exit/stdout: the on-disk receipt deliberately says
`inputs_copied_pending_receipt_and_terminal` and cannot alone prove success.
Provisioning does not confer execution authority or runtime qualification.

## Numerical programme, all seven folds

Supply one frozen UTF8 Python file, at most65,536 bytes. It receives `--input`
and `--out` directories; the active input is `public.npz`. It must produce exactly
20 unique original IDs with finite probabilities in `probabilities.json`, using
the original schema. `fixed_program.py` is a non-learning engineering control:
it loads only query IDs and emits0.5. It is not a scientific baseline or AI attempt.

```sh
"$PYTHON" -I -B "$FLOW/workflow.py" --release-sha256 "$RELEASE" program \
  --workspace /operator/neural034-workspace \
  --program /operator/neural034-workspace/candidates/fixed_program.py \
  --review /operator/neural034-workspace/operator/current-review.json \
  --other-reserve-bytes ACTUAL_OTHER_NONIMAGE_RESERVATION_SUM \
  --docker /usr/local/Cellar/docker/29.4.0/bin/docker \
  --host unix:///Users/nicholas/.docker/run/docker.sock \
  --output /operator/neural034-workspace/artifacts-build/control01
```

The operator copies the selected fixed candidate into `candidates` and pins that
copy in the review. The entry point checks image availability then replaces
itself with the original owner; it adds no background owner, retry or timeout
layer. The owner still requires independently supported exact task/image/Engine
qualification, root attempt authority, source review, fresh output, current
closed cost lineage and the complete dynamic capacity/reservation census.
Disabled templates remain disabled. Metadata availability must never be used to
manufacture `qualified:true`. Existing historical costs cannot be reset.

Each fold retains20 seconds,1.75 CPUs,3GiB and two numerical threads; the whole
owner retains480 seconds (420 work +60 cleanup) and16,000,000 reserved artifact
bytes. Candidate/holder/volume closure precedes the next fold, and all140 outputs
must close before protected grading against original targets and references.
After a successful natural owner exit, inspect the existing result chain:

```sh
"$PYTHON" -I -B "$FLOW/workflow.py" --release-sha256 "$RELEASE" check-program \
  --workspace /operator/neural034-workspace \
  --output /operator/neural034-workspace/artifacts-build/control01
```

That checker validates retained commitments and cleanup metadata. Independent
runtime evidence is still required; internal self-consistency is not a forgery
proof. Failure receipts and unresolved cleanup prohibit success or automatic retry.

## Original restricted combined viewer

Run `viewer-fold` separately for fold0 through6, with the same frozen client,
framework interpreter and budgets, writing `SESSIONS/fold-00` through`fold-06`:

```sh
"$PYTHON" -I -B "$FLOW/workflow.py" --release-sha256 "$RELEASE" viewer-fold \
  --workspace /operator/neural034-workspace --fold 0 \
  --client /operator/frozen-client.py \
  --client-python /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 \
  --max-actions 161 --max-images 140 --max-output-bytes 67108864 --wall-seconds 900 \
  --output /operator/sessions/fold-00
"$PYTHON" -I -B "$FLOW/workflow.py" --release-sha256 "$RELEASE" viewer-collect \
  --workspace /operator/neural034-workspace --sessions /operator/sessions \
  --output /operator/viewer-complete
```

This explicitly selects the original combined557 transport, including its
historical client-path disclosure limit, not the optional3802 modality successor.
The macOS boundary, same-client seven-fold collector and original renderer are
unchanged. Apple `/usr/bin/python3` is not the required framework interpreter.
These example budgets describe the old fixed control, not an AI study approval.
Collection includes replay renders and must be budgeted accordingly. It emits an
unscored140-row submission compatible with the original grader. A standalone
protected viewer grading owner remains a separate integration step; this command
does not bypass the programme owner's closure gate or silently invoke an older
unqualified scorer lifecycle. Therefore this addition alone does not finish
the complete graded viewer/programme pair.

`--plan-only` before the subcommand authenticates source and prints the delegated
command without opening inputs or invoking Docker/the task. It does not admit a
run. Neither viewer transport nor a Python client establishes an LLM's native
understanding: a live image provider needs its own fresh-context, tool-policy and
capacity qualification. The selected panel is historically exposed seven-mouse
development data, contextA/B prediction with processed calcium and behavior;
it is neither causal astrocyte evidence nor the paper's full eleven-mouse scope.

Generated controls: `python3 -I -B tests/test_workflow.py` in this directory with
NumPy. They exercise metadata refusal, bounded actual host CLI capture, immutable
source selection, original command construction and all140 generated fixed
outputs. They start no Docker container, read no original packets and score no
science. The prospective authentic protocol is separately reviewed and admitted.
