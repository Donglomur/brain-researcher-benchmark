# NEURAL-073 NIfTI input converter

This package supplies the original-image input step for the existing NEURAL-073 full-catalogue evaluator. It converts the complete 9,532-map catalogue into the evaluator's `n073_canonical_inventory_v1` and header-free little-endian float64 files. The scientific task remains 13 people, 25 declared protocols and 300 available person/protocol cells. This is one task's input converter, not another task or scorer.

The converter, catalogue parser, dependency contract and integration tests are unchanged from their reviewed implementation. `generated_checks.py` is a separate small generated-only test entrypoint. This source projection contains software and documentation. Original maps, catalogue rows, source identities, private references, original receipts and execution results are supplied or retained outside the package.

## Environment and generated checks

Use Python 3.11 or later on a POSIX host supporting descriptor-relative `O_NOFOLLOW` and `O_DIRECTORY` operations, with the exact dependencies in `requirements.txt`. The decoder checks the NiBabel and NumPy versions before conversion. Future environment and full-corpus resource qualification remain separate from source review.

From this package directory, run generated-only checks using a new absolute directory whose ancestors are real directories rather than symlinks:

```sh
python generated_checks.py --evidence "$GENERATED_EVIDENCE_DIR"
```

These checks need no evaluator checkout or catalogue metadata. They create only invented NIfTI images and a six-record invented corpus, and test scaled values, byte order, gzip, signed zero, native geometry, malformed headers, complete conversion, and refusal of incomplete rosters or destination reuse. Byte oracles and the hand-encoded fixture generator are reused from `controls.py`. An invented-corpus receipt never becomes an authentic-domain receipt.

For the fuller integration suite, supply the existing evaluator package explicitly:

```sh
python controls.py \
  --evidence "$INTEGRATION_EVIDENCE_DIR" \
  --existing-package "$NEURAL073_EVALUATOR_PACKAGE"
```

That directory must contain the existing `corpus.py`, its package dependencies, and `static/catalogue` with all fourteen exact metadata bodies pinned by `CONTRACT.json`. The integration suite verifies the actual evaluator inventory parser and full catalogue membership, while its image inputs remain invented. It additionally covers NIfTI-2, extension bounds, workspace admission and late-write failures. The integration suite cannot run from this small package alone. Both test entrypoints leave their evidence in the explicitly selected new directory; they do not download data or call a model.

The generated-only entrypoint completed one packaging validation run: all 18 checks passed using invented images. The fuller integration suite was not replayed for this projection. Source review and generated checks do not establish authentic conversion fidelity, a scientific result or benchmark readiness.

## Conversion semantics

Supported inputs are complete three-dimensional real scalar single-file NIfTI-1 or NIfTI-2 maps, optionally gzip-compressed. The converter validates the literal header, extensions, voxel offset and complete payload before decoding. Library header repairs are refused. Invalid or uncoded spatial transforms, extra dimensions, nonfinite values, complex/RGB voxels and incomplete maps are refused.

NiBabel applies the original scaling into float64 values. Every voxel is retained in little-endian float64 C order, with the last array axis varying fastest. Signed zero is preserved. There is no resampling, masking, cropping, reorientation, normalization or fitting. The coded sform takes precedence over a coded qform; both are recorded. Exact shape, affine, orientation and declared spatial units must agree across the complete corpus. Unknown units remain unknown; no physical unit is inferred.

See the [NiBabel NIfTI documentation](https://nipy.org/nibabel/nifti_images.html) for general format and scaling semantics. The operative dependency versions are those fixed in `requirements.txt` and `CONTRACT.json`.

## Explicit authentic inputs

An authentic conversion requires the existing evaluator's exact catalogue metadata, independently acquired original files, and a complete pinned input plan. This package supplies no original acquisition, participant roster or protected reference. All catalogue IDs are required; the converter cannot select a smaller subset or infer identities from filenames.

The input plan is UTF-8 JSON with these exact top-level fields:

- `schema`: `n073_original_conversion_plan_v1`.
- `domain`: `n073-full-declared-catalogue-v1`.
- `catalogue_digest`: the fingerprint issued by the included parser for the fourteen exact source metadata bodies.
- `limits`: positive integer `original_file_bytes`, `decompressed_file_bytes`, `canonical_file_bytes`, `total_original_bytes`, `total_canonical_bytes`, `metadata_output_bytes`, `max_workspace_bytes` and `whole_seconds`.
- `records`: every exact catalogue ID once. Each row has `record_id`, an explicit relative `path`, `original` containing exact `bytes` and `sha256`, plus `source_version`, `source_locator_digest` and `rights_evidence_digest` from independently established provenance.

The catalogue fingerprint can be inspected without opening original maps:

```sh
python - "$CATALOGUE_DIR" <<'PY'
import sys
import convert
contract, _ = convert.load_contract()
print(convert.load_catalogue(sys.argv[1], contract).fingerprint)
PY
```

After the complete original plan and execution resources have been independently selected, use:

```sh
python convert.py \
  --catalogue-dir "$CATALOGUE_DIR" \
  --plan "$ORIGINAL_PLAN" \
  --plan-bytes "$ORIGINAL_PLAN_BYTES" \
  --plan-sha256 "$ORIGINAL_PLAN_SHA256" \
  --original-root "$ORIGINAL_ROOT" \
  --output "$NEW_CANONICAL_CORPUS_DIR"
```

All directory operands must be absolute and compatible with the non-following path checks. Each original must be an explicit regular single-link file with the expected complete extent and hash. The output directory must not already exist. The full roster's storage and logical workspace reservations are checked before signal reads. Logical reservations and cooperative deadlines do not establish full-corpus feasibility or hard native resource enforcement; the host must enforce selected limits independently.

Successful conversion produces `INVENTORY.json`, `RESULT.json`, canonical files and per-original conversion records. The inventory matches the existing evaluator parser; the result describes native geometry for the future corpus section. Existing observation, duplicate screening, identity adjudication, transforms, folds, reference models and scoring remain the evaluator's responsibility.

Before publication, inventory bytes are staged, fsynced and closed. Atomic rename is the publication commit point. A preceding failure preserves partial artifacts and `FAILURE.json` without a final inventory. A later directory-close or reporting error cannot roll back a committed inventory; preserve both artifacts and process outcome. Directory-fsync crash durability is not established. There is no retry or previous-output adoption.

Receipt digests bind original bytes and conversion evidence; they do not independently establish source authority, rights, producer lineage, participant identity, geometry suitability or conversion fidelity. Authentic conversion and the scientific programme require their existing independent qualification. Candidate programs must not receive the trusted inventory or labelled catalogue metadata.
