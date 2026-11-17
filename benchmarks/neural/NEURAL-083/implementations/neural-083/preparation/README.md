# NEURAL-083: complete cohort preparation source

This component connects the retained OpenBMI MAT projection and record validator to the canonical store consumed by the existing 54-person programme. It adds no baseline, score, task identifier, independent attestation or scientific result. The full scope remains 54 people × two sessions: 108 records and 10,800 query trials. All four settings, three arms and both candidate/reference panels remain, giving 2,592 conditions and 5,184 later native fit/infer phases.

The ten original modules in `source/original` and `source/program` are retained byte-for-byte. Original channel selection, resampling, filter, inclusive 251-sample windows, class semantics, identity generation, index schema and numerical store reader are unchanged. `source/SOURCES.json` lists the exact member identities with public source provenance; the direct entry pins that manifest. Public documentation and provenance-location changes do not provide new scientific admission.

## Direct source inspection

Run from the task root, `benchmarks/neuroscience/neural-083`. Replace the cache placeholder with an absolute, fresh absent path whose parent directory is owned by the invoking user and is not group/world writable:

```sh
python3 -I -S -B -X pycache_prefix=ABSOLUTE_FRESH_ABSENT_PREFIX \
  preparation/source/prepare_entry.py inspect
```

The operator must externally select the exact entry, source manifest and trusted interpreter. Inspection authenticates all ten source members and records the direct entry's stable identity. It opens no request, inventory, record, identity key, MAT file or array and returns before constructing the captured module graph. NumPy and SciPy are unnecessary for this branch. Ordinary Git source modes 0644 are supported; the runtime product permissions described below are separate.

The entry is outside its own source manifest. Recording its identity is not self-authentication: the caller retains source, interpreter and cache-parent custody. Existing producing records bind particular entry/manifest identities and cannot be silently reassigned to this public counterpart. Source checks do not solve hostile privileged races or qualify an interpreter or scientific environment.

The public repository does not yet provide generic source-component discovery for this task. The supported source route is the direct command above. The repository-root checker path is `benchmarks/neuroscience/neural-083/test_preparation_source.py`; its role is finite source/entry validation, not scientific execution.

## Exact external inventory and captured dependencies

The original provider inventory remains a required external operator input: 41,063 bytes, SHA256
`4c7713e7e82b9c48f718e0c65811d21e70f42734626cd1af35d2808fe9cb3b44`.
It is not bundled here. The retained provision validator's fixed logical inventory read is routed to the request's explicitly pinned `source_inventory`. The hash is fixed; there is no caller-chosen replacement roster or fallback inventory. This guide grants no acquisition or data-use authority.

Captured local imports resolve to the selected original protocol, transport, array and provision sources. Legacy import-path setup receives an isolated path list instead of changing the host search path. The array module is lazy: its NumPy import occurs only when actual array operations are selected. Program index/store receive explicit common, contracts and original-protocol bindings. Raw direct imports of those dependent files, or the old provision CLI without this bridge, are not supported substitutes for the entry.

The actual preparation routes still require external NumPy/SciPy and authentic source/array semantics to be qualified. No numerical library, original dataset, identity key, protected target or native runtime is bundled by this source component.

## Requests and planning

All other commands require `--request ABSOLUTE_PATH --request-bytes N --request-sha256 HEX`. The request is an exact-schema object with the original monotonic `deadline_ns` and explicit positive cumulative `limits`: `read_bytes`, `write_bytes` and `retained_bytes`. No command creates fresh authority by supplying a receipt or a plan.

`plan-project` and `plan-finalize` authenticate the selected request, provider inventory and verified source manifest. They do not open the original MAT files, projected record arrays or identity key. They describe future operations; a plan is neither permission to run them nor evidence that they ran.

## Future complete projection

`project` requires exactly these `neural083_project_request_v1` fields:

- `schema`: `neural083_project_request_v1`.
- `source_manifest`, `source_inventory`: explicit `{path, bytes, sha256}` descriptors.
- `source_root`, `records_root`: absolute disjoint roots, with a fresh records root.
- `schema_bindings`: all 108 numeric-order `{person, session, binding}` rows, each binding an explicit descriptor.
- `max_record_output_bytes`: greater than 4,116,000 and at most 8,000,000.
- `deadline_ns` and the three `limits` fields above.

All binding metadata is admitted before the first numerical call. The caller visits all 108 original rows and invokes unchanged `project_mat.project` for each. It retains every actual record/array output and writes `PROJECTION.json` only after all 108 succeed. A failed attempt retains partial output and its separately reserved `FAILURE.json`; it does not restart, erase failed work or publish a smaller complete cohort.

The implementation has not been qualified on authentic full-cohort inputs. Approximately 64.85 GB of original MAT input and 433,728,000 numeric output bytes remain external. An independently selected supervisor must enforce actual CPU, memory, allocation, free-space and native-dependency limits for the complete operation. Source-level reservations do not measure physical I/O or native allocation and do not establish that deployment capability.

## Future finalization and existing consumer

`finalize` requires exactly these `neural083_finalize_request_v1` fields:

- `schema`: `neural083_finalize_request_v1`.
- `source_manifest`, `source_inventory`, `projection_record`, `identity_key`: explicit pinned descriptors; the separately selected private key is exactly 32 bytes.
- `records_root`: the owned complete original projection root.
- `product_root`: a fresh, disjoint, operator-only destination.
- The original `deadline_ns` and `limits` fields.

The producing record binds the current entry/source closure, exact inventory and manifest, and all 108 source/schema/record/array pins. It is evidence for independent review, not the review itself. The finalizer invokes original `prepare.read_records`, joins each record to its producing capture and authenticates every array's full bytes and original NPYv1 dimensions before changing any array permission. It then removes write permissions and invokes the actual `store.authenticate_array` consumer on all 108 members.

The key's owner, private permissions, parent custody and identity are admitted before mode effects. Its body is opened only after complete array admission, against the same identity. Record identities captured during `read_records` must still match at sealing, including after the full array pass. The key is neither copied nor logged.

Original `make_panel` and `index.make_index` produce the panel, protected targets and canonical index. Equality with `contracts.canonical(index)` and the complete 2,592-condition schedule is required. Online labels are absent from the index. Finalized private files are mode 0400 and directories mode 0500; original records, targets and the key are never made world-readable. The products are `index.json`, `panel.json`, `targets.json`, exact `projection_provenance.json` and last `COMPLETE.json`.

The completion receipt precedes the final directory mode/fsync closure. Its presence alone is insufficient: retain natural exit zero and the immutable result, then obtain the existing independent preparation admission. Any error after receipt publication still fails the operation. Metadata counters are snapshots before their enclosing receipt write; the continuing original Budget charges subsequent publication. A receipt does not claim to include its own future write cost. Failure publication uses a pre-reserved 65,536-byte allowance and never replaces the original exception.

The canonical descriptor/root can be supplied to the existing controller with a separately produced independent preparation review binding the same provenance and canonical pins and satisfying its existing review policy. This component does not issue those review booleans or bypass the controller. Authenticity, observed channel/class semantics, original numerical correspondence, complete physical capacity and reference competence remain unqualified.

## Provenance, existing programme and terms

The already-published [28-file programme manifest](https://github.com/Donglomur/brain-researcher-benchmark/blob/d3e2c5c27276a36eaa23c53a0502ef06c3bfbef3/docs/neuroscience-benchmarks/NEURAL083_SOURCE_MANIFEST.json) records the existing programme sources under their historical public paths. This preparation component does not relocate that programme or claim a new complete controller/runtime deployment.

The retained [reference attribution](https://github.com/Donglomur/brain-researcher-benchmark/blob/d3e2c5c27276a36eaa23c53a0502ef06c3bfbef3/authoring/delivery-20261105/neural083/public/REFERENCE.md) distinguishes the original GigaScience subtree's GPLv3 terms, the LoadData subtree's MIT terms and other helper/third-party terms. The Python preparation/reference counterparts are described as independent prospective implementations. SciPy preprocessing is not claimed to reproduce MATLAB bit-for-bit, and the probability reference is not a native-score parity result. No original MATLAB/helper source is newly bundled here, and no blanket relicensing of external code or data is implied.

Source inspection and engineering checks establish only their stated source behavior. They do not establish authentic NPY/MAT semantics, preprocessing parity, empirical probability quality, model performance or a completed scientific study.
