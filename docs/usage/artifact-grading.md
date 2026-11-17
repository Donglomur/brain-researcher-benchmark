# Direct artifact grading routes

These five source routes grade complete, finished submissions. The commands below
use the current repository layout. Linked package guides retain their release
text, including some former source paths; use them for the complete submission
schema, input/reference commitments and scientific scope.

Operators must separately provision the accepted assets and interpreter. This
checkout does not contain the private references or complete neural input packets.
Run from the repository root, replace every `/ABSOLUTE/...` placeholder with the
operator's own canonical path, and use fresh output locations as required by the
selected interface. The examples do not download inputs or construct references.

| Existing task/profile | Package contract and finished submission | Required external assets |
| --- | --- | --- |
| TMS fixed-region reconstruction (`PAPER-paper-signal-add-021`) | [TMS artifact commands](../../benchmarks/paper/PAPER-paper-signal-add-021/implementations/fixed-region-artifacts/README.md): validate and freeze both complete JSON arms, then `score-pair`. | Accepted four-file input projection; private fixed-region reference; lawfully supplied paper and selected official code for the declared A/B conditions. CPython 3.11.6 is required for scoring. |
| Across-day motor decoding (`NEURAL-023`) | [Motor artifact command](../../benchmarks/neural/NEURAL-023/implementations/registered-runtime/external-artifact-v1/README.md): `external_score.py` grades the complete 22,091-row prediction NPZ. | Exact source-day/calibration/assessment inputs and coordinate manifest; separate private assessment targets and reference metrics. Use the guide's Python/NumPy environment and explicit dependency root. |
| Purkinje morphology (`PAPER-FIND-REP-013`) | [Purkinje artifact commands](../../benchmarks/paper/PAPER-FIND-REP-013/implementations/artifacts/README.md): `inputs`, `freeze`, then `score` for the complete ten-tree numerical output. | Exact fifteen-file provider input packet and five private numerical references; CPython 3.11.6. Arbitrary raw SWCs do not replace the accepted packet. |
| Optogenetics central panels (`PAPER-FIND-ADD-015`) | [Optogenetics artifact command](../../benchmarks/paper/PAPER-FIND-ADD-015/implementations/central-artifact-scoring/README.md): `artifact_score.py` grades `central_submission.zip`. | Complete accepted 18-file participant packet and three private reference files; CPython 3.12.8 with NumPy 2.2.6. The guide retains the scope and provenance limits of this processed-data reconstruction. |
| Active-to-passive movement decoding (`NEURAL-022`) | [NEURAL-022 artifact command](../../benchmarks/neural/NEURAL-022/implementations/artifact-grading/README.md): `private/score.py` grades a commitment binding all 92 prediction rows. | Authorized local neural packet, actual case roster, private target/seven-reference NPZ, fixed-reference scalar checks and operator manifest in a private package copy; Python 3.12 with NumPy 2.3.5. |

## Current commands

### TMS fixed-region reconstruction

These assignments select the existing adapter and fixed-region source profile.
Actual `score-pair` requires CPython **3.11.6**; `inspect` authenticates public
source and reads no neural input or private reference.

```sh
TMS_PY=/ABSOLUTE/CPython-3.11.6/bin/python
TMS_PROFILE="$PWD/benchmarks/paper/PAPER-paper-signal-add-021/implementations/registered-runtime/fixed-regions-v1"
TMS_ARTIFACTS="$PWD/benchmarks/paper/PAPER-paper-signal-add-021/implementations/fixed-region-artifacts/artifacts.py"
"$TMS_PY" -I -S -B "$TMS_ARTIFACTS" --profile-root "$TMS_PROFILE" inspect
"$TMS_PY" -I -S -B "$TMS_ARTIFACTS" --profile-root "$TMS_PROFILE" \
  check-inputs --input-root /ABSOLUTE/accepted-input
```

The accepted input directory contains exactly the committed `INPUT.json`,
`values.f64`, `pair_counts.u8` and `missingness.json`. The paper and twelve selected
official source files for the declared A/B conditions are separately provisioned
as described in the package contract. After both producers have stopped, freeze
both complete JSON arms and score with the exact private fixed-region reference:

```sh
"$TMS_PY" -I -S -B "$TMS_ARTIFACTS" --profile-root "$TMS_PROFILE" \
  freeze-pair --submission-a /ABSOLUTE/participant-A.json \
  --submission-b /ABSOLUTE/participant-B.json \
  --output-root /ABSOLUTE/private/frozen-pair
"$TMS_PY" -I -S -B "$TMS_ARTIFACTS" --profile-root "$TMS_PROFILE" \
  score-pair --pair-root /ABSOLUTE/private/frozen-pair \
  --reference /ABSOLUTE/private/paired_region_reference.private.json \
  --output /ABSOLUTE/private/fresh-scores.json
```

`check-inputs` authenticates an existing packet; it does not prepare one from the
original MAT data. The package guide also describes `prepare-inputs` and
`validate`. A frozen pair does not attest protected execution or producer closure.

### Across-day motor decoding

Use Python with NumPy installed and the explicit public dependency directory.
This adapter has no command-line option to override the fixed asset identities.

```sh
NEURAL023_ROUTE="$PWD/benchmarks/neural/NEURAL-023/implementations/registered-runtime/external-artifact-v1/external_score.py"
NEURAL023_SOURCE="$PWD/benchmarks/neural/NEURAL-023/implementations/registered-runtime/external-artifact-v1/dependencies"
python3 -I -B "$NEURAL023_ROUTE" --source-root "$NEURAL023_SOURCE" \
  --submission /ABSOLUTE/predictions.npz \
  --target /ABSOLUTE/operator/assessment-targets.npz \
  --reference /ABSOLUTE/operator/reference-metrics.json \
  --output /ABSOLUTE/fresh-output-directory
```

The public preparation assets are `source.npz`, `calibration.npz`,
`assessment.npz` and `manifest.json`, committed in the package's
[ASSETS.json](../../benchmarks/neural/NEURAL-023/implementations/registered-runtime/external-artifact-v1/ASSETS.json).
The command grades all 22,091 assessment rows using the separate exact target and
reference-report bodies. Their example filenames above are operator locations;
their required contents are fixed by the adapter. The output directory must be
new. Keep the resulting score and receipt under the study's feedback policy.

### Purkinje morphology

All three operations require CPython **3.11.6** and the six pinned profile files.
The existing profile directory supplies those source files:

```sh
PURKINJE_PY=/ABSOLUTE/CPython-3.11.6/bin/python
adapter="$PWD/benchmarks/paper/PAPER-FIND-REP-013/implementations/artifacts/artifact.py"
profile="$PWD/benchmarks/paper/PAPER-FIND-REP-013/implementations/registered-runtime/program-v1"
"$PURKINJE_PY" -I -S -B "$adapter" --profile-root "$profile" --seconds 30 \
  inputs --source-root /ABSOLUTE/provider-input \
  --destination /ABSOLUTE/fresh/public-input
```

The provider packet must contain all fifteen files in
[INPUT_PINS.json](../../benchmarks/paper/PAPER-FIND-REP-013/implementations/registered-runtime/program-v1/INPUT_PINS.json):
ten released SWCs, `cells.json`, `author_sholl_totals.csv`,
`source_semantics.json`, `TASK.md` and `SCHEMA.json`. Arbitrary raw SWCs do not
replace this accepted packet. After the producer has stopped, freeze the complete
numerical output and record the receipt byte count and SHA-256 printed by `freeze`:

```sh
"$PURKINJE_PY" -I -S -B "$adapter" --profile-root "$profile" --seconds 30 \
  freeze --submission /ABSOLUTE/finished-output \
  --attempt /ABSOLUTE/fresh/attempt --producer-stopped
"$PURKINJE_PY" -I -S -B "$adapter" --profile-root "$profile" --seconds 30 \
  score --reference-root /ABSOLUTE/private-reference \
  --attempt /ABSOLUTE/fresh/attempt \
  --receipt-bytes RECORDED_INTEGER --receipt-sha256 RECORDED_HEX \
  --output /ABSOLUTE/fresh/private-score.json
```

Replace both `RECORDED_...` placeholders with the separately recorded values;
do not derive an expected pin from an untrusted replacement receipt. The private
reference directory must contain the exact `cells.csv`, `branches.csv`,
`author_sections.csv`, `components.csv` and `summary.json` named by
[REFERENCE_PINS.json](../../benchmarks/paper/PAPER-FIND-REP-013/implementations/registered-runtime/program-v1/REFERENCE_PINS.json).
The `--producer-stopped` flag is the operator's attestation, not process supervision.

### Optogenetics central panels

The adapter enforces CPython **3.12.8** and NumPy **2.2.6**. Use `-I -B`;
`-S` would hide the installed NumPy dependency. The accepted core and schema are
public source; `OPTO_GOLD` below is an external private reference directory.

```sh
OPTO_PY=/ABSOLUTE/CPython-3.12.8-with-NumPy-2.2.6/bin/python
OPTO_ROUTE="$PWD/benchmarks/paper/PAPER-FIND-ADD-015/implementations/central-artifact-scoring/artifact_score.py"
OPTO_CORE="$PWD/benchmarks/paper/PAPER-FIND-ADD-015/implementations/attenuation-source/central-program-v2/score_core.py"
OPTO_SCHEMA="$PWD/benchmarks/paper/PAPER-FIND-ADD-015/implementations/attenuation-source/independent-public-candidate-handoff-v2/public/OUTPUT_SCHEMA.json"
OPTO_GOLD=/ABSOLUTE/operator/accepted-opto-reference
"$OPTO_PY" -I -B "$OPTO_ROUTE" --core "$OPTO_CORE" --schema "$OPTO_SCHEMA" \
  --submission /ABSOLUTE/central_submission.zip --reference-root "$OPTO_GOLD" \
  --output /ABSOLUTE/private/fresh-score.json
```

Participants require the complete accepted eighteen-file packet described in the
package contract. The finished submission is one `central_submission.zip`; the
private reference directory separately supplies the exact committed
`windows.npz`, `paired_vectors.npz` and `report.json`. Scoring compares the
submitted statistical report and does not require SciPy. This processed-data
central-panel route retains the package's scope, provenance and licensing limits;
it does not establish whole-paper reproduction or a matched A/B result.

### Active-to-passive movement decoding

The public source package is
[NEURAL-022 artifact-grading](../../benchmarks/neural/NEURAL-022/implementations/artifact-grading).
Use Python **3.12** with NumPy **2.3.5**. Provision an intact private working copy
of this package with the operator assets described in its guide:

- `private/operator_manifest.json`, including the independently established
  `expected_fixed_reference` scalar checks;
- the actual `cases.json` roster named by its public descriptor, containing all
  92 ordered IDs;
- the private target/seven-reference NPZ named by its private descriptor, at the
  manifest's exact package-relative path.

The scorer resolves its package from its own location and has no separate root
or reference-root option. Invoke the scorer in the provisioned private copy:

```sh
NEURAL022_PRIVATE_PACKAGE=/ABSOLUTE/operator/neural022-private-package
python -I -B "$NEURAL022_PRIVATE_PACKAGE/private/score.py" \
  --submission /ABSOLUTE/committed/submission.json \
  --output /ABSOLUTE/reports/new-result.json
```

`submission.json` is the separate commitment to all 92 prediction rows, not the
prediction JSON itself. A valid submission with missing operator bindings is an
operator error. The public source package does not supply those bindings or a
replacement reference. Inspect the stored status; shell exit zero alone does not
establish a valid or scientifically successful submission.

## Interpretation and limits

Use these direct commands: the generic `neurobench score` command is not a
selector for all finite profiles. Artifact graders do not execute participant
programs or certify producer shutdown, fitting provenance or protected access.
Keep references and score feedback outside participant access according to the
study policy. Source publication grants no additional data redistribution rights
and adds no benchmark IDs, authentic runs or qualification claims.
