# THINGS-EEG2 operator preparation and complete plan compiler

This companion supplies the preparation and compiler caller for the curated S8 source at
`benchmarks/neuroscience/neural-055/complete_study`. It restores the six exact
retained preparation modules, calls their existing entry points, writes the
staging and full-ten-person indexes, finalizes newly owned public case trees,
and compiles the existing 960-cell campaign and fixed-image-feature plans.
It does not change the numerical methods or the original 200 registrations.

This is a curated public source profile; no scientific execution or qualification is asserted. Keep all five executable
files together: `operator_entry.py`, `source_closure.py`, `preparation.py`,
`plans.py`, `plans_v2.py`. The installed S8 manifest must have exactly 16641 bytes
and SHA-256 `1e3ec2628854c3038cc446a74e0bb29e786649ae2d84dbc17f69334529185bf9`.
Source capture authenticates its complete 78-body closure, lengths, modes and
hashes before loading controller support or dispatching scientific code.

## One invocation

Invoke an explicit operation with a pinned UTF-8 JSON request:

```sh
/absolute/python -I -B /absolute/adapter/operator_entry.py \
  --request /absolute/request.json \
  --request-bytes ACTUAL_BYTES --request-sha256 ACTUAL_SHA256
```

The request has exactly these keys:

```json
{
  "schema": "neural055-operator-request-v1",
  "operation": "stage",
  "runtime_root": "/absolute/installed/complete_study",
  "operator_root": "/absolute/operator",
  "output": "/absolute/fresh-output",
  "python": "/absolute/qualified-python",
  "limits": {
    "wall_seconds": 1, "cpu_seconds": 1,
    "read_bytes": 1, "write_bytes": 1, "live_bytes": 1,
    "files": 1, "model_calls": 1, "stream_bytes": 1
  },
  "stream_cap": 1,
  "spec": {}
}
```

The example illustrates fields, not viable resource values. Supply actual paths,
the selected operation's specification below, and an adequate explicit lifetime
envelope. Output must not already exist; its parent must exist. Paths are absolute
and canonical, with no symlink ancestors. The manifest and request reads count
toward the supplied controller read limit. Python and its scientific dependencies
must already be provisioned; this adapter installs nothing and retrieves nothing.

The existing process runner enforces the original deadline, CPU/stream lifecycle
and durable failure recorder. Explicit controller reads/writes are charged.
Scientific child logical I/O, total native memory and RSS are not measured by this
adapter. Its terminal states this limitation; supplying limits does not qualify
a host or establish total scientific resource observability. Partial owned
outputs remain on failure, and an existing output is never overwritten.

## Concrete preparation sequence

1. **`stage`**: supply `spec.metadata` as an absolute `{path,bytes,sha256}`
   descriptor for the legitimately acquired original image-metadata dictionary.
   Supply `spec.participants` in exactly `sub-01` through `sub-10` order. Each row
   is `{person,archive,archive_pin}`. `archive` is the absolute original ZIP path;
   its pin contains actual `participant`, `filename` (`sub-XX.zip`), `osf_id`,
   `version`, `bytes`, and `sha256`. All ten source archives must be distinct.
   The original staging executable verifies the archive bytes and reads its
   bounded original dictionaries; it forms all 4 training-repeat and all 80
   test-repeat means without changing row order. The restored modules remain
   byte-identical. The result contains `STAGING_INDEX.json` and ten actual
   `people/sub-XX/STAGED.json` descriptors relative to this invocation's output.

2. **`compile-feature-plan`**, then **`prepare-features`** when legitimately
   authorized to execute it: supply the same feature specification described
   below. Compilation writes a plan and exact original entry argv without
   executing it. The executing operation invokes the unchanged S8
   `central_entry.py prepare-features` and returns the actual resulting
   `FEATURE_MANIFEST.json` pin only after a complete original terminal. The
   original checkpoint/image/runtime/trust qualifications remain mandatory.

3. Obtain the existing **independent event-to-image and participant/archive join
   attestation** for the actual staging-index hash. This adapter never creates
   that evidence. Keep a legitimate operator-only 32-byte ID key outside public
   mounts. Existing source qualification and key custody remain operator duties.

4. **`assemble`**: supply exactly `staging_index`, `feature_manifest`,
   `join_attestation`, `id_key_file` (each an absolute `{path,bytes,sha256}`
   descriptor), and positive `maximum_case_output_bytes`. It calls the original
   case builder for all ten held-out people and then its original panel builder.
   Each case retains the other nine training participants; the held person's
   labeled training data stays excluded. Private ID joins/targets remain under
   `cases/sub-XX/private` and `panel/private`, outside the public case roots.
   The exact 16-file public tree is checked before changing its owned files to
   0444 and directories to 0555. An extra target, symlink, hardlink or unexpected
   namespace refuses finalization. No existing operator tree is recursively
   chmodded. The unchanged original `OriginalInputs.inspect` then checks the
   complete input index, all ten training contracts and 2,000 queries.

   Outputs include `INPUT_INDEX.json`, `PUBLIC_TREE_FINALIZATION.json` and the
   original public/private panels. The returned input-index descriptor is
   relative to the returned `artifact_root` (this invocation's output); public
   case roots and public-panel paths in the index are absolute. Copying or
   relocating inputs requires actual new pins and consistent paths. Do not treat
   this metadata inspection as original array/header or neural qualification.

5. Prepare genuine existing input, native-host, source/submission, reference,
   paired-schedule, semantic, scoring, exposure and interpretation evidence.
   **`compile-campaign`** accepts these explicit operands and emits the complete
   original 960-cell campaign (600 candidate and 360 reference cells), plus exact
   argv for `central_entry.py run`. **`run-campaign`** invokes that same original
   entry and requires its completed terminal. No campaign has been run for this
   delivery. F/I programmes and the interpretation responder must actually exist
   before an external operator can complete this step.

The source has six closed operations: `stage`, `assemble`,
`compile-feature-plan`, `prepare-features`, `compile-campaign`, `run-campaign`.
No operation is selected by default. The compile operations perform metadata
work only; feature validation also preserves the existing image-root symlink
metadata check. Execution operations perform real work when explicitly invoked
by an authorized external operator, rather than stopping at a disabled flag.

## Plan operands

The feature specification has exactly:
`checkpoint`, `image_metadata`, `image_index`, `image_root`, `environment`,
`runtime_qualification`, `closure_reserve_seconds`, `limits`, `trust`.
The file/evidence inputs follow the original descriptor format
`{path,bytes,sha256,mode,role}` under the chosen operator root. `image_root` is an
absolute path. Existing `FEATURE_PREPARATION.md` and `n055/features.py` define
the exact fixed environment and qualification semantics. The compiler invokes
their original metadata validator; it does not fabricate weight/image/evidence
descriptors or infer genuine qualification from syntactic admission.

The campaign specification has exactly:

```
system, submission, limits, phase_limits, native_profile,
input_index, input_qualification, pre_exposure_review,
reference_qualification, semantic_reviews, protected_scoring_authority,
trust, protected_panel, paired_schedule, interpretation,
exposure_declaration, runtime_environment,
diagnostic_incomplete_scoring, cell_limits
```

`submission` contains exactly `F`, `I`, `common_policy` descriptors, each for
existing actual source. Evidence operands stay unchanged. `limits` is the global
eight-field resource envelope shown above. `cell_limits` explicitly contains
`wall_seconds`, `cpu_seconds`, `read_bytes`, `write_bytes`, `files`, `model_calls`,
`stream_bytes`. The original runtime intersects each cell envelope with its
global envelope; no larger allowance or deterministic provider seed is invented.
`phase_limits` and all other structured operands retain the original source
contracts. The compiler derives the exact registry order, dimensions, four
contract pins, source identity, fixed isolation policy, broker contract and
resource-policy identity. Conflicting supplied identities are rejected.

`plans.py` supplies the base compiler. `plans_v2.py` adds the mandatory explicit
`policy.cell_limits` consumed by `Campaign.one_cell` and the original
`Budget.begin_cell`/`finish_cell` path. The adapter imports V2. Use the V2 entry
for complete campaign requests; the base V1 API omits that required operand.

## Remaining implementation and empirical work

This completion does not implement generation of F/I submissions, a hosted/API
model backend, or the post-score interpretation mailbox responder. The existing
runtime has a local Transformers provider and a fixed scientific-tool provider;
API access alone does not supply the local model image/cache/configuration.
The existing Linux process/cgroup/host source is reused. Real scientific inputs,
array qualification, genuine independent reviews and host/native qualification
remain prerequisites. No reproduction, accuracy improvement, benchmark validity,
SOTA, native-resource closure or scientific completion is claimed.

Historical engineering outcomes, original tool records and private review packets
are not distributed in this public source package. Source checks do not supply
scientific assets, execution authority or qualification evidence.

## Normal checkout and materialized runtime

First follow [the complete source guide](../complete_study/README.md) to authenticate
normal Git transport and materialize exact readonly modes into a fresh owned tree.
Set runtime_root to its complete_study and invoke its operator_completion entry.
The helper never chmods the checkout; the public sidecar does not add central-tool
discovery. All future compiler/environment/provider/authority inputs must bind
the new source and policy identities before exposure.

No credentials, signed evidence, F/I programmes, authentic EEG/images/targets,
weights or usable native deployment are supplied. Local model-system/F-I generation
and postscore operator orchestration are separate software work; this package
does not claim those implementations are completed. See [NOTICES](../NOTICES.md).
