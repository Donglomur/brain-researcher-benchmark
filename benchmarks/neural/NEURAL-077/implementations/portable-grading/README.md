# Portable grading for NEURAL-077

This operator route scores the existing 400-trial, two-person exposed-development
contract from explicitly provisioned external files. It removes the old host
repository layout and author-specific Docker-location assumptions. It adds no
benchmark ID, data, model call, fitting, scientific threshold or task admission.

The adjacent `registered-runtime` package remains byte-for-byte unchanged. This
wrapper authenticates its pinned `CURRENT_SOURCE.json` and every source member
before importing code, captures that source in a fresh run directory, and runs
the unchanged current worker. This preserves the repaired target-read attempt
counter, exact validator, metrics, six reference arms and historical source
freeze. The old pilot and historical source remain separate evidence.

The existing `direct-response/portable` package collects waveform responses;
`complete-direct-condition-v1` (when present) delivers/collects that condition.
Neither supplies this external-artifact grading route. This wrapper accepts an
already completed NPZ; it does not create or run a candidate.

## Operator inputs

Provision an existing Docker CLI, local Unix Docker socket, Docker configuration
directory and the exact image already installed locally:
`sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156`.
The wrapper always uses `--pull never` and the existing network-disabled,
read-only, non-root, two-CPU, 4-GiB worker contract. It rejects remote Docker
endpoints and removes inherited `DOCKER_*` environment overrides. No image,
dependency or dataset installation is performed.

Create a private operator JSON descriptor with this exact schema. Locations are
absolute; values cannot contain commas, newlines or NUL. Pins are selected from
the unchanged authenticated `registered-runtime/assets.json`, never supplied by
this descriptor. No original repository directory structure is required.

```json
{
  "schema_version": 1,
  "candidate_id": "NEURAL-077",
  "public_features": {
    "development-001": "/operator/public/person-a/features.npz",
    "development-002": "/operator/public/person-b/features.npz"
  },
  "private_targets": {
    "development-001": "/operator/private/person-a/targets.npz",
    "development-002": "/operator/private/person-b/targets.npz"
  },
  "reference_grade": "/operator/private/grade.json",
  "reference_commit": "/operator/private/prediction_commit.json"
}
```

For `validate`, omit all three private keys (`private_targets`, `reference_grade`,
`reference_commit`); that action accepts only the public descriptor. Grading needs
the six frozen reference scores in the grade and their frozen commit, not newly
fit predictions. Raw signals, training packets and reference prediction arrays
are unnecessary for this route. Numerical assets remain outside Git.

```sh
python3 -I -B /checkout/benchmarks/neural/NEURAL-077/implementations/portable-grading/score.py score \
  --package-dir /checkout/benchmarks/neural/NEURAL-077/implementations/registered-runtime \
  --artifacts /operator/artifact-locations.json \
  --docker-cli /absolute/path/to/docker \
  --docker-host unix:///absolute/path/to/docker.sock \
  --docker-config /absolute/path/to/docker-config \
  --submission /operator/completed-predictions.npz \
  --output-dir /operator/existing-parent/new-grading-run
```

The output parent must already exist. An existing output directory or symlink is
rejected before any input is read. Use operator-controlled inputs and a private
output parent without concurrent hostile filesystem mutation. This is a trusted
operator route, not a sandbox for operator-provided executable/configuration
files. Docker Desktop must be allowed to share the selected host paths.

## Validation and evidence

The first container mounts only the authenticated source, captured submission
and the two public packets. The unchanged worker checks their frozen hashes and
all 400 public IDs and then validates the complete NPZ. No private path is
statted, opened, hashed or mounted until this public-only worker has succeeded
and its cleanup is verified. An invalid candidate stops at that boundary.

The scoring container uses the same captured candidate and current source. It
again validates both public cases before opening the frozen grade/commit and
targets. All private pins, the target/public-ID join, reference source lineage,
391-check arithmetic receipt and all six signed comparisons remain enforced by
the unchanged worker. Private numerical assets are bound read-only in place;
the wrapper does not copy or export them. The repaired worker counts each target
loader attempt before checking that target's pin, including failures.

Each stage has a 48-second work deadline and cleanup deadline at 59 seconds;
scoring comprises validation plus scoring, so allow up to 118 seconds plus
bounded source capture and receipt writes. Each created container is inspected
before start and force-removed afterward, with exact absence verification. A
cleanup failure prevents a successful top-level result; the owned container name
remains in its receipt for operator recovery. No other containers are removed.

The fresh directory retains `result.json`, `receipt.json`, the captured
`submission.npz`, authenticated source snapshot, and per-stage ownership,
prestart-inspection, worker and execution reports. Files are exclusively created
and set read-only. This prevents accidental rerun overwrites; it is not WORM
storage against a privileged operator. The receipt hashes the result and captured
submission, records source/asset identities, explicit runtime, stage dispatch and
elapsed time. Keep this directory private: worker reports contain aggregate
reference/target-derived metrics and operator paths.

Exit codes distinguish `0` (complete validation/scoring), `2` (worker-rejected
submission), and `3` (operator/source/input/runtime/scoring/cleanup failure).
Unreadable or oversized host submission files fail operator capture; malformed
captured NPZ content is classified by the unchanged worker. A failed private
pin keeps the worker's `scoring_error` and target-attempt count with exit `3`.
Failed runs and partial receipts are preserved; never treat them as a score.

## Checks and scope

```sh
python3 -I -B -m unittest discover \
  -s benchmarks/neural/NEURAL-077/implementations/portable-grading \
  -p 'test_*.py' -v
```

These generated controls check orchestration and failures; they do not establish
scientific performance or supply replacement targets/references. Authentic
admission evidence, when run, belongs in a separate private operator record with
the exact wrapper/source/runtime/artifact hashes and all attempts/costs retained.

Scores remain equal-person balanced accuracy at `p >= 0.5` and equal-person
natural log loss with metric-only clipping at `1e-15`. Both historical development
people were exposed during construction. This route does not qualify an unseen
holdout, population inference, physical P3 timing, a motor-independent mechanism,
native LLM understanding, or the complete canonical scientific specification.
