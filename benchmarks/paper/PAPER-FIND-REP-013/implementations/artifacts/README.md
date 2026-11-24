# Purkinje morphology: direct numerical artifacts

This component adds `inputs`, `freeze` and `score` commands for the existing **PAPER-FIND-REP-013** finite task. It uses the already published scorer, schema, task and hash inventories in [program-v1](../registered-runtime/program-v1/README.md). The production scorer is shared with that directory; its current source revision is described below.

The complete endpoint covers ten released trees, thirteen components, 21,116 branches and 12,603 retained author sections. The primary metric is equal-cell branch-length RMSE in micrometres; all other field and summary errors remain separate. Zero primary error alone does not certify caliber, counts or summary reconstruction. Exact topology and missingness joins prevent a partial submission receiving a matched-subset score.

This is a trusted-operator artifact interface. It does not execute participant code. The existing binary artifact scorer retains its original behavior; the isolated program interface shares the revised numerical scorer; the common CLI has no new profile switch. The program instructions in the shared TASK describe the older program route; for this interface, submit the same numerical files directly.

## Required assets

Use CPython **3.11.6** on a POSIX host. The `--profile-root` directory must contain the six existing, byte-pinned files: `schema.py`, `numeric_score.py`, `TASK.md`, `SCHEMA.json`, `INPUT_PINS.json` and `REFERENCE_PINS.json`. It need not contain the Docker bridge or private authoring modules. The adapter verifies all six before loading the captured scientific source.

Provision the exact fifteen public files in `INPUT_PINS.json` (11,990,405 bytes), preserving their relative names. They include ten SWCs, cell metadata, exposed author Sholl totals, the source-semantics excerpt, TASK and SCHEMA. The SWC release is [Zenodo record 15066697](https://zenodo.org/records/15066697); the recorded provenance lists **CC BY 4.0**, attributed to Busch and Hansel. The associated paper is [eLife RP105013](https://doi.org/10.7554/eLife.105013.3). The three task-specific data/metadata files must come from the exact accepted provider packet; downloading arbitrary raw SWCs does not establish the complete task input. TASK and SCHEMA are already present in `program-v1`. This component neither downloads nor silently regenerates missing members.

Separately provision the five fixed numerical references named by `REFERENCE_PINS.json` in an operator-private directory. They are required for scoring and are not included in this source release. Do not mount that directory, the repository root or the grading tools into the participant environment.

The input packet exposes source excerpts and author totals and does not include the paper. It is an exposed, source-assisted reconstruction audit, not a paper-only/code-access comparison or blind evaluation. Recorded licensing/provenance is inherited; no fresh availability or legal review is claimed.

## Commands

From the repository root, set:

```sh
adapter=benchmarks/paper/PAPER-FIND-REP-013/implementations/artifacts/artifact.py
profile=benchmarks/paper/PAPER-FIND-REP-013/implementations/registered-runtime/program-v1
```

Authenticate and copy the exact provider input packet into a new participant directory:

```sh
python3.11 -I -S -B "$adapter" --profile-root "$profile" --seconds 30 inputs --source-root /absolute/provider-input --destination /absolute/fresh/public-input
```

The destination parent must exist. Only the fifteen declared members are copied. The command prints their manifest and leaves no additional receipt inside the participant packet. A failed copy is retained without success acknowledgment and cannot be resumed or overwritten by this command.

After the producer has stopped, capture its completed numerical outputs:

```sh
python3.11 -I -S -B "$adapter" --profile-root "$profile" --seconds 30 freeze --submission /absolute/finished-output --attempt /absolute/fresh/attempt --producer-stopped
```

Required files are `cells.csv`, `branches.csv`, `author_sections.csv`, `components.csv` and `summary.json`. Optional `interpretation.json` is retained as opaque, unscored bytes. No extra source/prose file is required or accepted. Existing per-file limits and the 8,000,000-byte aggregate cap apply. Copy the printed receipt byte count and SHA256 into your trusted attempt record.

Score using that separately recorded receipt pin:

```sh
python3.11 -I -S -B "$adapter" --profile-root "$profile" --seconds 30 score --reference-root /absolute/private-reference --attempt /absolute/fresh/attempt --receipt-bytes RECORDED_INTEGER --receipt-sha256 RECORDED_HEX --output /absolute/fresh/private-score.json
```

Replace the two `RECORDED_...` placeholders with the values returned by `freeze`; do not compute an expected pin from an untrusted replacement receipt. The output path must be new, have an existing parent and be outside the attempt.

The scorer reauthenticates captured bytes and admits all candidate public syntax before opening any private reference. Exact topology/missingness comparison then uses the selected scorer revision. Reference identity/parse failures are operator errors, not candidate scores. Handled grades, including incomplete coverage and unsupported derived numerics, exit zero with their original status. Transport/operator errors exit two. Files from failed commands are not successful results.

The grade file has mode0600 and contains reference-dependent metrics and identity diagnostics. Keep it operator-private under the study's feedback policy. The component does not enforce one-use grading or cumulative feedback limits.

## Validation and limits

The original complete finite scientific evidence is reused; this export does not repeat an authentic reconstruction or grade. Thirteen inherited tiny generated transport checks cover capture, continuous scoring, malformed/changed files, private-pin failures, exact namespace, incomplete topology, source identity, output reuse and handled timeout. Four additional relocation checks cover public descriptor mapping, loading from only the six public dependency files, explicit external input/reference roots, and refusal of a mismatched provider file. The four new checks passed; a separate RSS-reporting control then verified Darwin bytes, Linux KiB conversion and an explicit unknown-platform fallback. The inherited suite was not rerun during export. The complete source suite now contains18 tests.

For the complete source test suite, use a fresh output directory whose parent exists:

```sh
python3.11 -I -S -B benchmarks/paper/PAPER-FIND-REP-013/implementations/artifacts/test_artifact.py --profile-root benchmarks/paper/PAPER-FIND-REP-013/implementations/registered-runtime/program-v1 --output-root /absolute/fresh/source-controls
```

These checks use invented files and public source only; they do not read released neural data, private answers, Docker or network resources. The unchanged full input copy and new authentic grading invocation remain unrun.

Stable file identities, fixed hashes/byte caps, no-follow opens, exclusive fresh outputs and captured read-only modes support a trusted operator convention. Producer termination is an attestation. Modes are not immutable against the owner/root; race-proof ancestor confinement, atomic multi-file snapshots and crash-atomic directory publication are not claimed. Each command has a requested 1–120-second wall alarm, with no hard memory/CPU quota or whole-study resource scheduler.

This endpoint does not establish donor-aware inference, all morphology findings, biological replication, full-paper reproduction, held-out improvement, new benchmark IDs, model performance or submission acceptance.

## Scorer revision: exact identity and signed bias

The current scorer rejects decimal identity tokens that become integers only after binary64 rounding, consistently rejects nonzero Unicode decimal underflow, and preserves small signed-bias cancellation residuals. RMSE, MAE, maximum absolute error, complete coverage and the output schema are unchanged. Ordinary bias can intentionally change in its last bits. This is a source correction, not a new authentic result. The earlier scientific results and `SOURCE_CONTROL_RESULTS.json` remain tied to the historical scorer/source lock. Fresh native qualification is still required for the revised source.

Submission receipts bind the scorer hash. An old receipt is refused by this revision; preserve historical attempts and grades, and freeze a new submission only under the selected revised source. No automatic regrading occurs.

Run the eight relocated numerical regression methods plus the scorer-receipt boundary check, using invented values only, from the repository root:

```sh
python3.11 -I -S -B benchmarks/paper/PAPER-FIND-REP-013/implementations/artifacts/test_numeric_score.py
```

The old scorer in `regression_fixtures/old_numeric_score.py` is a pinned regression fixture only. Production loads the single current scorer from `program-v1`; fixtures contain no authentic reconstructions or reference answers.

## Nonzero aggregate underflow

The maintained scorer now returns `unsupported_derived_numerics` when a positive RMSE or MAE rounds to zero during aggregation. This also covers the outer equal-cell RMSE, preventing a nonzero discrepancy from being reported as a perfect primary score. Representable results, exact-zero discrepancies, coverage and scientific metric definitions are unchanged.

The regression uses generated smallest-subnormal values within the declared finite-number interface. It is a numerical boundary correction, not evidence of a failure in the released biological data, a new reconstruction, or an improvement result. The portable predecessor and historical grades remain unchanged. New attempts must bind the revised scorer and current paired contract.

Run only the four new methods with:

```sh
python3.11 -I -S -B benchmarks/paper/PAPER-FIND-REP-013/implementations/artifacts/test_aggregate_underflow.py
```
