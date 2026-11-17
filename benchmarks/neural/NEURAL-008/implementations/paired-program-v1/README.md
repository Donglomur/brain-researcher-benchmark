# Original paired sleep programme

This source restores the submitted-program route for NEURAL-008's original
two-person development comparison. One committed Python programme receives two
physically separate feature views in fresh offline containers. The existing
`../finite-paired-scorer/score.py` assesses both complete probability panels.
Source and generated controls are provided; the current native environment has
not been qualified, and no authentic programme or model run accompanies this
implementation. Canonical registration and unavailable observation modes do not
change.

The exact endpoint is six training people (16,290 epochs, 16,211 scored and 79
masked) and development-001 (2,780 epochs) plus development-002 (2,670 epochs),
5,450 epochs per arm. These development cases were already exposed. This is not
the later 153-night programme, a new hidden test set, or a population estimate.

| Access | EEG_clock | EEG_EOG_clock |
|---|---|---|
| Engineered signal features | 12 EEG columns | Same 12 EEG columns plus 6 EOG columns |
| Clock | 3 columns | Same 3 columns, bit-identical |
| Training supervision | Same six complete people and masks | Same six complete people and masks |
| Development context | Both complete nights together | Both complete nights together |
| Fresh runtime | One container, no previous arm outputs | A new container, no previous arm outputs |

The programme can fit models, use future context within each development night,
and inspect both development people together. It sees engineered features and
clock values, not waveforms or a viewer. This measures agent-built analysis.
Identical submitted code can branch on arm or feature count; it does not prove
identical fitted algorithms, a causal effect of EOG, or native neural-signal
understanding. Positive, zero and negative EOG-minus-EEG differences are valid;
both absolute performances remain visible. There is no reward for a larger
positive gap, which could be created by weakening the EEG arm.

## Existing input preparation

`INPUTS.json` retains the historical byte/hash identities of exactly 15 files per
arm: eight projected feature archives, six public training-label archives and
one public manifest. It contains only relative locators. `prepare.admit()` reads
these fixed files, validates the full chronological roster, 15/21-column finite
geometry, manifest membership, training support and bit-identical shared
columns, then returns individual readonly file mounts. It does not copy a whole
directory, re-extract signals, read development targets, read model caches, or
rebuild the original feature projection. Both physical views must already exist.
Changing pins or substituting another panel requires scientific review.

Source lineage: original `eog-program-completion-v1/ASSETS.json` SHA-256
`7623cc750adb930c4a5f4584329f1e3234b30e8aa3656be81eaba78e3db89236`;
projection metadata SHA-256
`8f7b3ba8e8a55287eb026b71548dae6798c9d3a35832aa1a5ac70b26ab9b15a2`;
original projector SHA-256
`33b4918a16e4b8272494abf83a1fc43f450f115b002afd1aa1ff7c63049126bb`.
The original metadata reports 9,921,504 projected archive bytes and 5,858 public
manifest bytes, with the six original label files referenced rather than copied.
No original array or label bodies were read during this source recovery.

## Participant contract

Submit one ordinary Python file of at most 200,000 bytes, plus `method.json` and
`claims.json`. The programme is invoked inside each isolated container as:

```sh
/usr/local/bin/python -I -B /program/program.py --input /input --out /output
```

Read `/input/manifest.json`. Each feature NPZ has `epoch_id` (`<U21`) and `X`
(`<f8`); training-label NPZs have `epoch_id`, `stage` and `score_mask`. Keep all
rows and the fixed class order `W, N1, N2, N3, R`. Produce only
`/output/predictions.npz`, at most 1 MiB, containing `class_order` and, for both
development people, `{case_id}__epoch_id` and `{case_id}__probabilities`.
The original scorer documents probability constraints and masks. No output
transformation, silent case subset or missing-person completion is performed.

`method.json` has exactly `schema_version: 1`, `method_id`, `method_description`,
`training_policy`, and `limitations`; the four text fields must be nonempty and
at most 4,096 characters. `claims.json` may omit a numerical claim using:

```json
{"schema_version":1,"candidate_id":"NEURAL-008","reported_contrast":null}
```

These files and the programme are frozen before public input admission. A fresh
runtime is created for each arm. Historical candidate limits are retained:
20 seconds, 1.75 CPU, 3 GiB, 64 processes, two numerical threads, and one 1 MiB
prediction archive. There is no network, host execution fallback, automatic
retry, candidate-selected image, or extra dependency installation. The complete
owned phase allocates 20 seconds setup, 20 producer, 10 capture and 10 cleanup;
both phases share one original 150-second controller deadline.

## Operator execution, after separate runtime approval

`run.py` uses the unchanged concrete Docker transport under NEURAL-007's
`whole-night-programme/program/vendor_transport`, pinned together with this
task and the existing scorer in `SOURCE.json`. This dependency does not adopt
that programme's larger scientific endpoint. The provider requires Linux with
procfs, a local Docker binary/socket, an already provisioned immutable image
containing Python and required numerical packages, and private disjoint control
and quarantine roots. The pinned image must be independently inspected for the
complete participant information boundary. Docker Desktop compatibility and
forced-stop recovery are not established by the generated controls.

The operator supplies `configuration.json` with schema
`neural008_native_configuration_v1`, `source` (the bytes/SHA-256 descriptor of
`SOURCE.json`), `image` (`sha256:` plus the immutable image ID), `docker_binary`,
`docker_socket`, `control_root`, `quarantine_root`, `mechanical_policy_path` and
`mechanical_policy_pin`. The independently reviewed policy has exactly:

```json
{
  "schema":"neural008_mechanical_boundary_v1",
  "approved_rule":"exact_original_paired_views_and_frozen_program_v1",
  "source":{"bytes":0,"sha256":"REPLACE_WITH_REVIEWED_SOURCE_HASH"},
  "image":"sha256:REPLACE_WITH_REVIEWED_IMAGE_ID",
  "image_inventory_sha256":"REPLACE_WITH_REVIEWED_IMAGE_INVENTORY_HASH"
}
```

The placeholders are not approvals and are intentionally unusable. This source
does not generate a scientific or runtime approval. The reviewed mechanical
rule binds each exact generated exposure, all input/source mounts and the image
inventory. The programme cannot supply its own policy or override input pins.
Source authentication assumes an operator-controlled, stable checkout. Python
imports occur before `source()` verifies the pinned dependency closure; these
hash checks are not a secure loader or a sandbox for modified operator code.

From the repository root, using operator-owned absolute paths:

```sh
python -I -B benchmarks/neural/NEURAL-008/implementations/paired-program-v1/run.py \
  --assets-root "$ASSET_ROOT" --program "$PROGRAM" --method "$METHOD" \
  --claims "$CLAIMS" --configuration "$CONFIGURATION" --output "$FRESH_OUTPUT"
```

This captures and publicly validates both panels. Adding `--targets "$TARGETS"`
invokes the existing fixed historical scorer only after both producers have
been removed, both captures validated, and `PAIRED_FREEZE.json` persisted.
Without `--targets`, no target loader is called and there is no scientific score.
The target directory is never mounted in a participant container.

Retain `COMMIT.json`, the two arm joins, provider receipts, `PAIRED_FREEZE.json`
and `ASSESSMENT.json`. A join records exact input/exposure/request/receipt and
programme hashes. Each receipt is re-read through the provider's independent
observer before the next arm. A failure after the source/programme commitment
creates `FAILURE.json`, preserves partial artifacts and does not retry, continue
to another arm, or grade an incomplete pair. Configuration, source or commitment
failures occur before that handler; they can leave no failure receipt or a
partial commitment. Preserve such partial files and do not reuse the output
directory. Inspect the exact owned resources and provider receipt on interruption;
absence is not inferred from a failed controller. Existing transport recovery
requires its own reviewed original-clock operation, not rerunning this command.

Expected future participant peak is bounded by the 3 GiB producer plus 128 MiB
holder and controller overhead. Source-read and host-write allocations are
96 MiB and 16 MiB across the provider; each phase reserves at most 48 MiB and
8 MiB respectively. These are transport ceilings, not measured full-machine I/O
or peak RAM. Original source files are reused, not duplicated. Generated fixture
costs and authentic runtime measurements must remain separate.

## Source controls

```sh
python -I -B benchmarks/neural/NEURAL-008/implementations/paired-program-v1/tests/test_program.py
```

Controls use a complete generated eight-person panel, corruption of shared
bits and case ordering, missing/extra/wrong-arm files, a live-producer refusal,
source mutation, malformed second output and target-last grading. The native
adapter's exact request/exposure/mount/observer wiring is tested with a generated
transport double. These are software controls, not Docker isolation trials,
neuroscience results, native understanding results or model performance.
