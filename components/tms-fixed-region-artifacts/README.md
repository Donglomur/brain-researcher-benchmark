# Run the complete TMS fixed-region artifact benchmark

This is an executable, trusted external-artifact interface for the existing
`PAPER-paper-signal-add-021.fixed-regions-v1` profile. With the accepted input and
reference files, an operator can prepare the full input, validate participant
answers, freeze both A/B artifacts and obtain the unchanged numerical scores.
It uses the existing accepted scorer; it does not require another reference
construction or authentic scientific run to install the interface.

The [participant task](../../benchmarks/neuroscience/paper-signal-add-021/fixed-regions-v1/TASK.md),
[method](../../benchmarks/neuroscience/paper-signal-add-021/fixed-regions-v1/METHOD.json)
and [output schema](../../benchmarks/neuroscience/paper-signal-add-021/fixed-regions-v1/SUBMISSION_SCHEMA.json)
remain unchanged. The normative scoring convention is CPython 3.11.6; the CLI
enforces that version for `score-pair`. The implementation uses the standard
library and POSIX ordinary-file operations. No Docker, GPU, model API or package
installation is needed by this artifact interface.

This interface consumes finished answers. It neither executes a participant's
program nor attests process closure, input dependence, authoring history or
isolated code access. The previously accepted selected-host protected route
remains available through its separate
[portable owner](../../benchmarks/neuroscience/paper-signal-add-021/fixed-regions-v1/portable/README.md).
A trusted artifact score and a protected runtime result have different evidence.

## Operator commands

From the repository root, set these two source locations. Use the admitted
CPython 3.11.6 executable in place of `python3` for actual scoring.

```sh
TMS_PROFILE="$PWD/benchmarks/neuroscience/paper-signal-add-021/fixed-regions-v1"
TMS_ARTIFACTS="$PWD/components/tms-fixed-region-artifacts/artifacts.py"
python3 -I -S -B "$TMS_ARTIFACTS" --profile-root "$TMS_PROFILE" inspect
```

`inspect` authenticates the unchanged task/method/schema/scorer and prints the
fixed profile and input/reference commitments. It reads no neural input or gold.
The commands below use explicit example paths: substitute the operator's own
canonical paths without symlink ancestors. Output parents must already exist;
each new directory or file must be absent.

If the complete accepted input packet is already in its intended location,
authenticate it once:

```sh
python3 -I -S -B "$TMS_ARTIFACTS" --profile-root "$TMS_PROFILE" \
  check-inputs --input-root /ABSOLUTE/accepted-input
```

If a separate participant input copy is needed, use this instead of the preceding
check. It authenticates while copying all four files, preserves every byte, seals
the files as 0400 and directory as 0500, and writes an operator-private receipt
outside the input directory. It streams without decoding or retaining the tensor
in memory. The receipt records the source-stream identity and successful writes;
it is not an independent second output-body hash pass.

```sh
python3 -I -S -B "$TMS_ARTIFACTS" --profile-root "$TMS_PROFILE" \
  prepare-inputs --source-root /ABSOLUTE/accepted-input \
  --output-root /ABSOLUTE/fresh-participant-input \
  --receipt /ABSOLUTE/private/input-import.json
```

An incomplete import remains in its failed namespace and receives no completed
receipt. Existing outputs are refused. Inspect a failure and select a fresh
destination if another attempt is warranted; the command never deletes it or
retries automatically. This importer copies an accepted projection; it does not
turn an arbitrary MAT file into a qualified input.

## Participant handoff

Give both conditions the same complete input directory, exact TASK.md,
METHOD.json, SUBMISSION_SCHEMA.json, lawfully obtained paper, tools and declared
budget. The original TASK uses the protected owner's `/input`, `/task` and
`/candidate` aliases. In the trusted artifact setting, supply an explicit map
from those aliases to the provided directories; participants may pass those
paths to their own programs. This interface does not create global filesystem
aliases or launch that program.

Only B additionally receives the twelve selected official source files listed
in the existing [catalog](../../benchmarks/neuroscience/paper-signal-add-021/fixed-regions-v1/portable/CATALOG.json).
Its complete allowlist and exact hashes are authoritative; a shortened source
set or a full repository is a different condition. The paper, code and data are
separately provisioned research assets, not included in this source component.
Keep scorer, reference, reference-producing tools and operator evidence out of
both participant material sets. Artifact mode relies on the trusted operator to
maintain these conditions; the receipts cannot prove them.

Each participant returns one UTF-8 JSON object, at most 2 MiB, in the existing
submission schema. It contains all 12 regions, 720 condition-position means,
36 effects with 540 paired differences, and all 540 leave-one-position-out
summaries. Preserve all four conditions and fifteen jointly ordered source
positions. Physical-person identity remains an explicit source-order assumption.
The declared method is the fixed-region extension, not the paper's primary
FieldTrip cluster analysis. Significance is not required.

The operator can validate finished JSON without opening any reference:

```sh
python3 -I -S -B "$TMS_ARTIFACTS" --profile-root "$TMS_PROFILE" \
  validate --submission /ABSOLUTE/participant-A.json
```

For a matched A/B study, withhold evaluator feedback until both participants have
finished. After both producers have closed under the operator's own procedure,
capture their complete outputs in one fresh snapshot:

```sh
python3 -I -S -B "$TMS_ARTIFACTS" --profile-root "$TMS_PROFILE" \
  freeze-pair --submission-a /ABSOLUTE/participant-A.json \
  --submission-b /ABSOLUTE/participant-B.json \
  --output-root /ABSOLUTE/private/frozen-pair
```

The output directory contains exactly `A.json`, `B.json` and `PAIR.json`, each
0400, inside a 0500 directory. Both complete public schemas must pass before any
snapshot is published. A and B may have identical numerical content, but need
distinct ordinary input files. A receipt binds the captured bytes and role
names; it explicitly does not certify protected execution or producer closure.

Grade the pair using the already accepted private reference:

```sh
python3 -I -S -B "$TMS_ARTIFACTS" --profile-root "$TMS_PROFILE" \
  score-pair --pair-root /ABSOLUTE/private/frozen-pair \
  --reference /ABSOLUTE/private/paired_region_reference.private.json \
  --output /ABSOLUTE/private/fresh-scores.json
```

The scorer source and reference identities are fixed in the CLI, with no command
option to substitute different pins. Both frozen artifacts are reauthenticated
and fully validated before the sole reference-body read. The report contains the
unchanged score dictionaries under `scores.A` and `scores.B`, including all seven
component losses, unit-specific diagnostics and complete 12/36/540 support.
There is no new combined-arm score or inferred causal code benefit. The primary
score remains one minus the equal mean of the seven component losses; no new
threshold or success criterion is introduced.

The score report is mode 0600. It does not copy the reference payload; it contains
reference-dependent losses and MAE/Linf diagnostics and remains private evaluator
feedback until the study's feedback policy permits release. Exit 0 means the requested
command completed; exit 2 is a refusal or malformed submission; exit 3 is a
private-reference intake/schema failure, never a participant score. Existing
outputs and partial writes are preserved rather than overwritten. File-byte
caps and stable snapshots are enforced; whole-process time, aggregate memory,
process isolation and producer supervision are not supplied by this trusted
artifact adapter.

## Full input acquisition and preparation

The immediately usable route is the accepted four-file projection. Its complete
size is **35,844,842 bytes**:

| File | Bytes | SHA-256 |
|---|---:|---|
| `INPUT.json` | 4814 | `a0e3328495f4ba090ba1b2e3b1fe78ed22793ce38a6c78963d9f5637b9b1ab70` |
| `values.f64` | 35616000 | `93e721d490676f232ae2ac11b065294c0e660f267bcdc466080791c91641264c` |
| `pair_counts.u8` | 222600 | `6c0d2c0bb833b9bb8efb1ff72400403abbf92882cb5ae1e96322e246f805b4d8` |
| `missingness.json` | 1428 | `a2d16bef2777c493df79bbdc83cb058908a6cd28b45723e1a0d11cbd83c61e20` |

The tensor is complete C-order `[4,7,53,200,15]`, little-endian binary64, with
source position fastest: 4,452,000 operands. Counts and missingness preserve the
full packet. Obtain these exact files from the authorized benchmark operator;
then run `check-inputs` or `prepare-inputs`. Do not regenerate a packet or reference
that the operator already holds and has accepted.

For reconstruction from the released original, the
[paper's official data route](https://osf.io/hf5a4/) identifies the study deposit.
The selected `masterTFR_allsubs.mat` is 298,290,277 bytes with SHA-256
`536e9513b13dc721cf60613334ee37ce546e7bf67154d95bd067ddc0f0023a95`.
The link and identity come from accepted source metadata; this delivery did not
recheck live availability or download it. The existing owner-private original
projection producer is the preparation route. It selects seven ROI labels in
original channel order across all four conditions, all 53 frequencies, all 200
times and all 15 positions; copies all binary64 values without normalizing,
averaging, imputing or dropping; and constructs the full count/missingness files.
Its accepted 14-file source lock and complete operation recipe are recorded in
the private `LOCAL_BINDINGS.json` delivered to the operator. Reuse that exact
producer/runtime and full output acceptance, then authenticate the four pins
above. A different MAT extractor is not silently declared equivalent.

The public artifact component does not include that HDF5 reader's owner/runtime
closure or redistribute the original data. An external operator lacking the
accepted projection therefore still needs the complete projection from its
provider, or the existing upstream preparation closure. This is the concrete
remaining distribution/preparation dependency; it does not prevent trusted
grading when the accepted files are already available. The source package
does not claim a self-contained public-data download or clean-host native setup.

Reuse the accepted **359,637-byte** private reference with SHA-256
`ceba59b4702c692c4e6819deb5cf72f8d6ebdb68b2a48228caf1860b266f30d8`.
The [reference producer](../tms-fixed-region-reference/README.md) supplies the
unchanged reconstruction route if a new copy must be generated; its numerical
output must match that commitment. No reference construction is needed merely
to install or use this artifact adapter with the existing reference.

## Registry and validation

The canonical `PAPER-paper-signal-add-021` manifest currently dispatches the older
135-participant-condition behavioral scorer. `tools/neurobench.py score` has no
finite-profile switch. The direct commands above select the fixed-region profile
explicitly. The additive registry proposal records them under the existing
parent's `finite_artifact_profiles.fixed-regions-v1`; it preserves the legacy
entrypoints and all canonical IDs. `neurobench show` will display that metadata
when adopted, but its legacy `score` command is not silently redirected.

Source verification uses generated complete artifacts and tiny invented input
files, including wrong finite predictions, malformed second arms, changed pins,
wrong references, aliases, output reuse and incomplete import failures:

```sh
python3 -I -S -B components/tms-fixed-region-artifacts/test_artifacts.py \
  --profile-root benchmarks/neuroscience/paper-signal-add-021/fixed-regions-v1 -v
```

The new interface reuses the accepted authentic input/reference/scorer evidence;
its generated controls are not a new authentic scientific score, a model trial,
an independent-person certificate or a protected runtime qualification. The
finite profile is usable with its exact owned assets. Dataset redistribution,
from-scratch external preparation, target-harness execution and model difficulty
remain separate questions. No benchmark ID or broad qualification count is added.
