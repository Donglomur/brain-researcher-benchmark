# Portable grading for NEURAL-007

This route validates and grades a finished probability file for the existing
**5,450 epochs from two exposed development people** (2,780 and 2,670). It uses the
unchanged registered grader, candidate validator, five-stage class order and
YASA/RF comparisons. It does not execute candidate code, infer programme provenance,
call a model, qualify an untouched test set, or qualify the complete canonical
neural-investigation task.

The operator supplies explicit external locations, an installed Docker CLI, a
local Unix Docker socket/configuration and the already installed exact image
`sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156`.
No original authoring directory layout is needed. No image, dataset or package is
downloaded; image pulls are disabled.

## Inputs and command

Keep this descriptor and all numerical files outside the public checkout:

```json
{
  "schema_version": 1,
  "candidate_id": "NEURAL-007",
  "comparators": {
    "YASA": "/operator/references/YASA.npz",
    "RF": "/operator/references/RF.npz"
  },
  "private_files": {
    "manifest.json": "/operator/targets/manifest.json",
    "development-001_labels.npz": "/operator/targets/development-001_labels.npz",
    "development-002_labels.npz": "/operator/targets/development-002_labels.npz"
  }
}
```

For public-only `validate`, omit `private_files` entirely. The full schema is
accepted only by `score`. Locations must be absolute and cannot contain commas,
newlines or NUL, name the same normalized path across roles, or traverse symlinks.
The descriptor selects locations, never replacement pins. The exact original
`operator_assets.json` supplies all target/reference/source hashes. The frozen
scorer generates the complete canonical epoch IDs, so grading does not need
observation arrays or training labels.

```sh
python3 -I -S -B /checkout/benchmarks/neural/NEURAL-007/implementations/portable-grading/score.py score \
  --package-dir /checkout/benchmarks/neural/NEURAL-007/implementations/registered-runtime \
  --artifacts /operator/sleep-artifact-locations.json \
  --docker-cli /absolute/path/to/docker \
  --docker-host unix:///absolute/path/to/docker.sock \
  --docker-config /absolute/path/to/docker-config \
  --submission /operator/completed-submission.npz \
  --output-dir /operator/existing-parent/new-grading-run
```

Use a fresh output directory with an existing trusted parent; evidence is never
overwritten. Docker Desktop must be allowed to share the chosen host paths.
Use operator-controlled files without concurrent hostile filesystem writes. This
is not a sandbox for an untrusted Docker executable, operator or configuration.

## Admission and retained evidence

The first container mounts only the captured submission, frozen references and
source needed for public validation. It calls the unchanged
`candidate_adapter.validate_submission` for the candidate and both reference
files. It requires complete canonical IDs/order, exact five-class order, bounded
stored NPZ structure, finite probabilities in `[0,1]` and row sums within `1e-6`.
It never clips, normalizes, drops epochs or fills missing values. A malformed
candidate or missing/mutated comparator cannot reach the private stage.

After the public receipt proves complete coverage and successful owned-container
cleanup, the second container runs the exact original `registered-runtime/grader.py`.
It revalidates the candidate/references before invoking the existing target loader.
The loader counts its invocation before checking the private manifest or targets;
a failed private hash remains an operator error with its attempted access count.
The host does not open or hash targets; it checks ordinary target paths only after
public validation. Both stages retain the original non-root, network-disabled,
read-only 4-GiB/2-CPU sleep container contract and inspect it before start. All
cleanup names are unique, proven absent before creation and owned by this run.

The new directory retains exact source snapshots, the captured submission,
`invocation.json`, `result.json`, `receipt.json` and per-stage ownership,
prestart inspection, worker output and cleanup receipts. Files are created once
and made read-only. On attached-output timeout, partial stdout/stderr and cleanup
remain in the execution receipt. Keep the directory private: reports contain
aggregate target/reference-derived metrics and operator paths. Source hashes and
self-authored receipts are integrity evidence, not scientific qualification or
external proof that earlier attempts were disclosed.

Each stage allows 48 seconds for Docker work and 59 seconds including cleanup;
the worker retains the original 10/11-second CPU limits. Exit `0` means successful
complete validation/scoring, `2` means candidate rejection, and `3` means an
operator, source, reference, private target, runtime or cleanup failure. Failures
remain in their fresh directories and are not scores.

## Source reuse and limits

`execution_pins.json` remains unchanged and anchors the original score controller,
grader and operator assets. The wrapper captures these bytes before importing the
controller's exact container-inspection checks. The validator is already published
at `../finite-attempt-audit/vendor/candidate_adapter.py` and is authenticated against
the original operator manifest. `vendor/integration_helper.py` supplies the missing
original target-header helper, copied byte-for-byte at **12,093 bytes**, SHA-256
`22482aa30371f91c548c80d83a76b09a7f903e31d4f3dc7f52733fed8f8d7921`, also required by
that same manifest. It contains source only; only its original `target_headers`
function is used by grading. No numerical asset is vendored.

Bounded file capture, JSON decoding, explicit Docker runtime selection and receipt
writing reuse the hash-authenticated EEG portable adapter. The sleep dispatch
retains its own original resource/mount inspection because its scorer has a
different container contract. Historical source pins are not rewritten.

The primary endpoint remains equal-person fixed-five-class macro-F1; balanced
accuracy and signed YASA/RF differences remain descriptive companion outputs.
The 5,450 epochs are not 5,450 independent participants. Both people were exposed
in construction. YASA and RF differ in pretraining/context, and no pass threshold,
population inference, model comparison experiment or native LLM understanding is
established by a successful software control. Use the existing finite-attempt audit
and frozen lifecycle for any separately authorized programme provenance claims.

```sh
python3 -I -S -B -m unittest discover \
  -s benchmarks/neural/NEURAL-007/implementations/portable-grading \
  -p 'test_*.py' -v
```

These generated controls test source admission, target separation, complete receipt
checks, exact native dispatch, failure preservation and owned cleanup. Authentic
end-to-end controls require separately retained external evidence for the exact
source/runtime/assets and must be reported as software controls, not model results.
