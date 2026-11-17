# Current NEURAL-073 input converter

The [NIfTI converter source](../implementations/registered-runtime/input-conversion-v1/README.md)
is available alongside the [complete catalogue evaluator](../implementations/registered-runtime/FULL_CATALOGUE_SOURCE.md).
The retained parent README and operator guide describe an earlier release in which
conversion was external. The converter source now supplies that input interface;
authentic conversion and its independent fidelity evidence remain outstanding.
The dated package documents and source manifests are unchanged.

The converter preserves all **9,532 maps**, covering 13 people, 25 declared
protocols and 300 available person/protocol cells. It produces the evaluator's
`n073_canonical_inventory_v1` inventory and header-free little-endian float64
files. This is a component of the [existing task](../task.json), with no new task
or scientific qualification.

## Current source paths and inspection

Run these assignments from the repository root:

```sh
N073_ROOT="$PWD/benchmarks/neural/NEURAL-073/implementations/registered-runtime"
N073_CONVERTER="$N073_ROOT/input-conversion-v1"
N073_EVALUATOR="$N073_ROOT/full-catalogue-v1"
python3 -I -S -B "$N073_EVALUATOR/run.py" inspect \
  --deployment "$N073_EVALUATOR/DEPLOYMENT.json" \
  --deployment-sha256 652b2d0194e61a74ade38e8e77bd0958b5cd2ddb7ea8954dbadade0f3b150b3f
```

Inspection uses Python 3.11 or later and the standard library. The digest above
identifies the supplied unconfigured deployment at this source revision. Inspect
checks source and deployment metadata; it does not open original maps, external
deployment sections, private keys or model files. It does not enable execution.
A future changed deployment needs its own reviewed bindings and qualifications.

## Original-map conversion

Use a separately prepared Python 3.11-or-later environment with exactly
**NiBabel 5.4.2 and NumPy 2.4.6**, as declared in
[requirements.txt](../implementations/registered-runtime/input-conversion-v1/requirements.txt)
and [CONTRACT.json](../implementations/registered-runtime/input-conversion-v1/CONTRACT.json).
Conversion requires a POSIX host supporting descriptor-relative `O_NOFOLLOW`
and `O_DIRECTORY` operations. No installation or download is performed by these
commands. Do not add `-I` or `-S` to the converter recipe: it imports its sibling
catalogue module and the selected installed scientific dependencies.

Before conversion, the operator must independently establish original file
identities, rights/provenance, a complete pinned input plan and execution limits.
All 9,532 record IDs are required. The input-plan schema, record fields and
capacity fields are specified in the
[converter contract](../implementations/registered-runtime/input-conversion-v1/README.md#explicit-authentic-inputs).
Its fourteen exact catalogue metadata bodies are supplied by the evaluator's
`full-catalogue-v1/static/catalogue/` directory; their presence does not supply
the original NIfTI maps or qualify their identities.

After those requirements are met, use the current paths below. Replace every
`/ABSOLUTE/...` path and both `REVIEWED_...` values with the selected operator
inputs. The plan byte count and digest must come from the reviewed plan, rather
than being silently refreshed from an untrusted replacement.

```sh
N073_PY=/ABSOLUTE/selected-python-environment/bin/python
CATALOGUE_DIR="$N073_EVALUATOR/static/catalogue"
(
  cd "$N073_CONVERTER"
  "$N073_PY" -B convert.py \
    --catalogue-dir "$CATALOGUE_DIR" \
    --plan /ABSOLUTE/operator/original-plan.json \
    --plan-bytes REVIEWED_INTEGER \
    --plan-sha256 REVIEWED_SHA256 \
    --original-root /ABSOLUTE/operator/original-maps \
    --output /ABSOLUTE/operator/new-canonical-corpus
)
```

Directory operands must be absolute and pass the non-following directory checks.
Each original must be a regular single-link file matching its complete pinned
extent and hash. The output directory must be absent. The converter checks the
full roster's storage and logical workspace reservations before signal reads;
these checks do not establish hard host limits or full-corpus feasibility.

Conversion retains every voxel on the native grid. It does no resampling,
masking, cropping, reorientation, normalization or fitting. It preserves source
scaling into float64, signed zero, complete geometry and declared spatial units.
Successful conversion publishes `INVENTORY.json`, `RESULT.json`, canonical files
and per-original conversion records. Retain both artifacts and process outcome;
the package guide explains partial-output and publication semantics.

## Generated source checks and remaining work

With the same selected dependency environment, the small generated-only checks
can run from the converter directory using a fresh absolute evidence directory:

```sh
(
  cd "$N073_CONVERTER"
  "$N073_PY" -B generated_checks.py \
    --evidence /ABSOLUTE/operator/new-generated-evidence
)
```

These checks use invented images. The separate fuller integration recipe in the
package guide also requires the evaluator package and its exact metadata. Neither
test route establishes authentic conversion fidelity or a scientific result.

Original producer lineage, identity adjudication, complete geometry/support,
rights, independent conversion fidelity, native isolation, reference competence
and full-capacity qualification remain required. The supplied deployment remains
unconfigured. Keep trusted inventories and labelled catalogue metadata outside
candidate access. The earlier finite interface and the complete catalogue
programme retain separate scopes; this guide does not qualify either for a run.
