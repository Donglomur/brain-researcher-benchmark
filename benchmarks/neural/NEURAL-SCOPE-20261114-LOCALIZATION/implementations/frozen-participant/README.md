# Complete localization participant callback lifecycle

`participant.py` executes one hash-frozen candidate source on the complete
**11 cells × 16 conditions × 5 realizations = 880 cases**. It connects the existing
normalized observations to the existing `localization-predictions-v1` scorer
interface. This supplies a participant programming route beyond the fixed
geometry-centroid negative control. It does not supply a competent localization
method, original-data normalizer, hostile-code sandbox or qualified runtime.

The existing nearest-contact proxy, strict `<50 um` endpoint, separate spike and
template reporting, grouped aggregation, complete requested support and stability
diagnostics are unchanged. There is no authentic/model execution or task-count
increase. Generated controls demonstrate software behavior, not understanding.

## Owner interface

Keep this directory next to `participant-packet` and `centroid-scorer`. The loader
authenticates the unchanged packet source before importing it; that component in
turn authenticates the unchanged neutral contract. Exact dependencies are in
`SOURCE.json`. Python's standard library and Unix descriptor interfaces are used.

```python
submission, receipt = participant.produce(
    normalized_neural, source_root, frozen_program_path,
    expected_manifest_sha256=canonical_normalized_manifest_sha256,
    expected_program_sha256=frozen_program_sha256,
    program_bytes=exact_program_bytes,
    total_input_byte_budget=complete_unique_npy_bytes,
    maximum_artifact_bytes=largest_npy_bytes,
)
# In a separate trusted owner context, after reference authentication:
report = neutral_contract.score(
    normalized_neural, trusted_owner_reference, submission,
    frozen_program_sha256=frozen_program_sha256,
)
```

The owner supplies an independently qualified normalized manifest and files at
`SOURCE_ROOT/inputs/<sha256>.npy`. Canonical hashes use the existing compact,
sorted-key ASCII JSON representation. There is no reference argument. The API
returns objects in memory; the owner must capture complete outputs and preserve
failed attempts. An exception returns no partial submission or score.

The complete grid, manifest hash, positive byte allocations, entry-source hash,
all body hashes and byte extents, primitive NPY values and per-cell contact maps
are checked before any candidate code executes. Full input is decoded once;
decoded Python values require more memory than NPY bodies. Allocations are input
byte ceilings, not process-memory enforcement. Final symlinks and special bodies
are refused by the existing loader. Parent-directory trust remains external.

## Candidate interface

The candidate is a single Python source file of at most 256 KiB defining:

```python
def predict(case, observations):
    # A deliberately constant negative control, not a localization method.
    return {request['request_id']: [0.0, 0.0]
            for request in case['requests']}
```

`case` contains the existing per-case participant projection: opaque case and
condition IDs, sampling frequency, `uV` voltage unit, complete sample offsets,
ordered channel IDs, role-to-digest bindings and every spike/template request.
It also carries the projection's permitted top-level `axis_names` and
`coordinate_unit`, so the predictor can interpret geometry columns in the
verified order and micrometre units.
Owner cell and realization identities, animal/recording groups, references and
source paths are absent. Requests identify `kind` and `array_index`.

`observations` maps `waveforms`, `template`, `probe_geometry` and
`observed_support` to a dictionary with `dtype`, `shape`, `fortran_order` and
`values`. Shape and values are tuples; values retain flat physical storage order.
The shape is `[spike, sample, channel]`, `[sample, channel]`, `[channel, axis]`
or `[channel]` respectively. For C order the last index varies fastest; for
Fortran order the first index varies fastest. Probe axes are the manifest's
ordered axes, with coordinates in micrometres. The wrapper applies no transpose,
crop, mask, normalization, template recomputation or estimator. A fresh case and
observation dictionaries prevent ordinary callback mutations from affecting the
next case. Immutable value tuples may be shared.

The result must map exactly every requested ID for that case to two finite
numeric coordinates in the declared axis order and micrometres. Extra, missing,
Boolean, nonfinite or malformed output aborts the whole operation. All 880 calls
use one loaded source body. The original entry file is authenticated again after
the complete panel; an altered file invalidates the result. Stateful Python
globals can persist between calls in deterministic sorted opaque-case order;
the owner must freeze any intended stateful policy before evaluation.

Declared imports are limited to `math`, `statistics` and `struct`; no third-party
or author-code dependency is admitted through this component. The basic builtins
listed in `_load_predictor` support numerical programs. This deliberately scoped
interface does not establish the separate official-code access condition.
The owner must freeze the Python/runtime environment for a real comparison; the
receipt records its version but does not authenticate that environment.

## Boundaries and controls

**This is not a Python security sandbox.** Same-process reflection can bypass
the import/builtin restrictions and inspect host state. Candidate deadline,
memory, filesystem/network access, protected-reference custody, isolated
authoring, external dependency closure and output persistence are operator
requirements before admitting an untrusted candidate. A source hash neither
proves those boundaries nor detects a file that was changed and restored between
checks. The loaded entry bytes remain fixed for this operation.

The six generated checks cover full 880-case/2,640-request output through the
existing scorer, waveform sensitivity, allowed argument fields and mutation
isolation, missing/extra/invalid/failed responses, complete-input and program
admission before candidate execution, changed source, declared dependencies and
geometry-trajectory refusal. They run with:

```text
python3 -B -m unittest discover -s benchmarks/neural/NEURAL-SCOPE-20261114-LOCALIZATION/implementations/frozen-participant -p 'test_participant.py' -v
```

They reuse only the existing generated packet fixture; no source payloads,
private targets, notebooks or scientific models are read. Authentic normalization,
coordinate/gain provenance, patch/probe and animal/recording joins, competent
COM/triangulation/grid-convolution references and empirical comparison remain
unqualified. Direct-observation, viewer, tool and frozen-program scientific
qualification flags remain false.
