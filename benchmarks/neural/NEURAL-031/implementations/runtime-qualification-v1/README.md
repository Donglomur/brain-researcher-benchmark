# NEURAL-031 full paired control and recorded runtime

This package connects the existing full input store, a fixed ratio-1 programme,
forty fresh Docker contexts and the unchanged protected ratio scorer. It is an
additive successor to `paired-executor-v1`; all older source and evidence stay
unchanged. **The corrected native control completed all forty contexts and
passed independent saved-proof review.** The first attempt failed during output
capture; that attempt and its verified cleanup remain preserved. The completed
run establishes the stated local fixed-control behavior, not AI performance.

The scientific task is prediction from processed spine morphology and
coactivity. Its two conditions are baseline information and baseline plus
neural measurements, with the same programme and missingness indicators. This
is a programme task, not direct waveform viewing. It does not reproduce the
source paper's pooled retrospective correlation statistic.

The complete panel remains 27 source members, 20 mice, 1,143 rows and 774
baseline-defined requests in each condition. All 43 requests without usable
follow-up still need predictions; the unchanged scorer evaluates the 731
observed dimensionless follow-up/baseline volume ratios. The earlier accepted
target/input bridge is reused without reprojecting or reconverting data.

## What the successor changes

The selected immutable image inherits three thread variables set to 2. Its
exact inspected configuration is now accepted only for that image, and every
candidate receives the existing explicit overrides to 1. Unknown inherited
variables remain rejected. The selected local image and provenance are in
`IMAGE_PROFILE.json`; another task's successful execution does not qualify this
executor, and an exact clean-machine image distribution is still unavailable.

Every Docker CLI call has exclusive private intent, stdout, stderr and result
files. The backend records the real exit and verifies the owned CLI process
group is absent, including when its direct leader has already exited. Evidence
or closure failure prevents ordinary execution and grading; bounded owned
cleanup is still attempted. Exact live inspect responses remain available for
independent review after the containers have been removed. Journal descriptors
are retained in the batch receipt, rather than embedding raw command bodies.

The original participant contract remains: one frozen programme; only the
current `data.npz`, `manifest.json` and programme mounted read-only; no other
fold or target mounts; non-root UID/GID 65534; read-only root; no network; 3 GiB
memory without additional swap; 1.75 CPU; PID ceiling 256. A keeper preserves
the bounded output tmpfs after the participant command exits. A trusted reader
captures output in the running container's namespace, then the container is
paused, inspected, removed and observed absent before those bytes are committed.
Confirmed absence precedes the next context.
All forty contexts share the original 480-second deadline. Failure-only
emergency cleanup has at most ten additional seconds and never earns success.

The first attempt used `docker cp` after pausing. Its candidate command exited
successfully, but the returned archive contained only the output directory and
no prediction file. The parser correctly rejected it before scoring. Docker
[documents that `cp` cannot copy tmpfs content](https://docs.docker.com/reference/cli/docker/container/cp/).
The successor replaces that command with a fixed Python reader; it adds no
writable host mount, shared volume, image or cross-context state. The reader
checks a sole, bounded, singly linked regular file with no-follow opens and
stable file/directory identities, then sends its bytes in an authenticated frame.

This is a snapshot of bytes observed **while the container is running**, followed
by verified container closure. It is not an atomic paused-filesystem snapshot.
The stability checks do not establish protection against every hostile,
concurrent process with the same UID. Qualification here is limited to the
frozen no-change control; stronger arbitrary-producer custody remains separate.

## Fixed control and protected scoring

`control.py` predicts exactly 1 for every requested row, in original order.
It decodes only the integer query identifiers; it does not decode feature or
training-label values, fit a model or select a method. Both views use identical
code. `CONTROL_METHOD.md` records why this particular control is matched.

Each control invocation also reports its actual Python/NumPy versions and
unprivileged identity, checks fresh temporary/output state, and checks fixed
write/network denials. Reports contain no authentic measurement values or row
IDs. These observations test the stated routes; they do not prove universal
hostile-code isolation.

`run.py` validates all 441 normal command records, their saved bytes and exact
ordering, all forty distinct runtime reports, all forty captured-output identities
and all 1,548 constant predictions
before the first private target read. Source-local review documents are captured
and authenticated with the code; caller-supplied review paths cannot be used
to read a private file during preflight. It then invokes the unchanged scorer.
Both absolute MAEs must equal the no-change reference, with exactly zero paired
gain for every mouse and the macro result. Zero is the expected engineering
control result, not a scientific success threshold.

The completed control produced all 1,548 predictions in 33.33 seconds. Baseline,
neural and no-change macro MAE were each **0.3342934008378292**, with exactly zero
paired gain. Independent review checked all 441 commands, 80 container
inspections, 40 runtime reports, 40 captured-output chains and owned-resource
closure. The 731 observed and 43 unavailable target policy was preserved.
`RUNTIME_VALIDATION.json` records the accepted scope and evidence identities;
`RUNTIME_HISTORY.json` retains both attempts. `SOURCE.json` remains the immutable
pre-execution closure used by the successful run.

The operator remains trusted and the participant runs only in its isolated
container. The complete operation has a separate 600-second outer limit,
covering source checks, the original batch, protected scoring and final records.
Starting the batch requires at least 570 seconds left; subsequent public-proof
verification requires 90 seconds left, and protected scoring requires 60. These
are admission windows within the same outer clock, not additional phase clocks.
Unused time may be shared, while the participant batch retains its exact limit.
An interrupted operation or a hard timeout with unknown resource closure is a
failure. A successful driver receipt still requires observed terminal exit and
independent saved-proof review. There is no automatic retry.

## Prepare and run

Use `configure.py` to prepare a fresh operator plan. It authenticates the local
source closure and writes metadata; it does not open data or invoke Docker.
Supply the release's reviewed `SOURCE.json` hash and absolute operator paths:

```sh
python -I -B configure.py \
  --source-sha256 '<reviewed SOURCE.json SHA256>' \
  --store-root /operator/existing-paired-store \
  --targets /operator/accepted-private-targets.json \
  --output-root /operator/fresh-full40-attempt \
  --docker-binary /operator/docker \
  --socket /operator/docker.sock \
  --plan-output /operator/fresh-plan.json
```

The returned plan hash binds the complete fixed cohort, accepted target digest,
immutable image and source-local method/profile documents. Once the concrete
operation and resources have been admitted, run:

```sh
python -I -B run.py \
  --source-sha256 '<same reviewed SOURCE.json SHA256>' \
  --plan /operator/fresh-plan.json \
  --plan-sha256 '<returned plan SHA256>'
```

The image must already exist locally; no tag fallback, pull, package install or
image build is performed. The backend creates a private empty Docker config so
the command cannot inherit account configuration. The operator output parent
must exist. Targets remain outside the repository and participant mounts.

`run.py` is specifically the fixed construction-control route. The copied
`executor.py` CLI does not supply the required journal/configuration and should
not be advertised as a ready standalone command. For a later arbitrary
candidate study, an operator must explicitly construct this backend with fresh
`journal_root` and `docker_config` directories, and pass it to
`executor.execute` or `executor.run_and_score`, together with a frozen programme
and independently reviewed method declaration and output-custody policy. The
running-capture control alone does not qualify arbitrary hostile producers.
Such a study does not use the
constant-output acceptance checks. Identical source alone cannot prove matched
learning or tuning across the two information conditions.

## Verification limits

Generated tests cover the constant control, source/plan and public/private
barriers, complete saved transport joins and the new backend failure modes.
Small local helper processes test owned CLI-group cleanup; they are not Docker
qualification. The original accepted delivery/scorer suites are not repeated.
`TESTING.json` records exact controls, preserved failures and tested source
cutoffs once construction review is finalized.

The complete fixed-control run and its saved-proof review are finished. Future
participant studies still need their own frozen methods, output-custody review
and measured performance. No model, fit, AI accuracy, neural-information gain,
paper improvement or submission readiness is claimed by this source package.
