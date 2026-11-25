# LANGUAGE runtime-tree adapter

This adapter prepares the ordinary, immutable runtime tree required by the existing LANGUAGE exec-reset provider. It is a separate preparation component for `PAPER-ROOT-ADD-001`; it does not replace the provider or change the scientific endpoint.

`plan` authenticates one completed merged export of the fixed scientific image, inventories its complete tar metadata and regular-file byte ranges, and resolves aliases in a virtual filesystem. `apply` authenticates that plan and export, streams the declared ranges into independent ordinary files, checks the complete output tree, and publishes the provider manifest outside the tree. It never installs packages, downloads material, starts Docker, executes a candidate, or reads neural arrays.

The image is fixed to `sha256:ab2bea4ced8dac37524a995444e928b80c4db04e9f5e7fddd26ea5dd3962781e`. Production admission requires the authenticated 3,042-file installed numerical inventory plus the original Python executable. Their paths, sizes and content hashes must survive the projection. A generated test can exercise the lower-level projection functions with small synthetic files; that does not relax production CLI admission.

## Projection rules

Ordinary image files retain their bytes. Symlinks and forward hardlinks resolve only within the complete virtual image namespace and become independent files or directory subtrees. Resolution processes each linked component before a following `..`; it never follows host filesystem links. Cycles, root escapes, dangling or dynamic targets, duplicate or case-colliding paths, unsupported tar nodes, sparse/size-changing extensions, malformed termination and resource overflow refuse the operation. Directory-alias ancestry is included in descendant provenance and the 64-hop limit.

The reserved directories `input`, `candidate`, `artifacts`, `executor`, `tmp`, `proc`, and `dev` are replaced by empty directories, with only these empty mount-slot files:

- `input/features.npy`
- `input/responses.bin`
- `input/request.json`
- `executor/entry.py`

`etc/hostname`, `etc/hosts`, `etc/resolv.conf`, and `etc/mtab` become ordinary empty files. Other aliases cannot use those replacement domains to recover host identity or dynamic content. Directories are mode 0555; files are 0444 or 0555 according to original executable bits. No hardlinks, writable files, ownership privilege bits, ACLs, or xattrs are copied. These are explicit normalization choices, so the result is a runtime projection, not a claim of complete OCI filesystem equivalence.

## Runtime and commands

The host **planning and scanner-control path requires CPython 3.11.6** and the exact 106,231-byte `tarfile.py` source with SHA256 `d6957647c11b6592e58e37d4e9f02f6cf9ee695cb0653b1072b542b8afac700d`. A different Python patch release is not silently accepted, and scanner controls are not skipped. A compatible hosted environment still needs qualification.

Linux application does not call the tar parser; it consumes only the authenticated plan's ranges using standard-library file and hash operations. The actual operation requires reviewed, externally selected profiles, readonly input mounts and a fresh ordinary Linux filesystem output. Profiles are disabled unless `selected_for_execution` is explicitly true and the fixed schema, image, inventory, bounds, input hashes and finite expiry all match.

```sh
python3.11 -I -S -B prepare_provider_rootfs.py plan --profile PLAN_PROFILE.json --profile-sha256 EXACT_SHA
python3.11 -I -S -B prepare_provider_rootfs.py apply --profile APPLY_PROFILE.json --profile-sha256 EXACT_SHA
```

These are operation forms, not populated runtime permissions or a self-contained native launcher. The owner must bind the completed export, fresh outputs and all phase receipts. Both profiles carry the same original work expiry, with at most 540 seconds remaining; the existing owner separately enforces the 600-second total and 60-second cleanup reserve. Cumulative read charges carry into the application phase. Do not reset either the deadline or the read allowance between phases.

The standalone generated controls use the sibling adapter and an absent output leaf under an ordinary existing parent:

```sh
python3.11 -I -B test_rootfs_projection.py --output-root /absolute/fresh/controls --execute-generated-controls
```

The generated campaign exercises small invented tar/tree inputs. It does not process the authentic image, install a runtime, run a model, or qualify Linux containment.


The separate focused serialization regression preserves the nine original methods and exercises the complete-plan bound, document accounting and ordinary-read compatibility:

```sh
python3.11 -I -S -B test_plan_serialization.py --output-root /absolute/fresh/serialization-controls
```

These four generated methods do not repeat the scanner suite or establish authentic runtime qualification.

## Bounds and remaining qualification

The fixed stops are 512 MiB for the completed export, 128 MiB per regular member, 100,000 nodes, 1,024-character paths, 64 alias hops, 1 GiB of materialized file bytes, 32 MiB each for audit and ordinary metadata, and 4 MiB for the runtime manifest. The existing `plan_bytes` limit remains a 4 MiB path/file collection budget. A separate `plan_document_bytes` limit allows 40 MiB for the complete plan, which also contains normalization records, directories and required identities. This does not admit additional files, aliases or content.

The complete serialized plan is bounded by 41,942,205 bytes, including JSON escaping, separators and its final newline. File-row accounting contributes at most 4 MiB minus 1,023 bytes; normalization rows at most 32 MiB plus one byte; the admitted manifest bounds directories plus required identities by 4 MiB minus 107 bytes; the remaining fixed envelope and newline contribute 294 bytes. The 40 MiB document stop leaves 835 bytes of margin. Other admission limits can still refuse an operation. This bound applies to documents emitted after successful `project_roster` admission. The unchanged `verify_projection` does not replay the producer's collection charges or complete normalization provenance for arbitrary external JSON. A future owned application must join the exact authenticated descriptor of a successfully produced plan; the wider document read cap is intentional.

An application plan read has its own 40 MiB subtotal while retaining the 32 MiB ordinary scanner, inventory and profile metadata stop. All document reads remain counted in both `read_bytes` and `metadata_bytes`; the latter is an aggregate and may reach 72 MiB during application. Explicit controlled reads still share the 6 GiB stop. Existing profiles lacking the new limit are refused by the unchanged exact-profile check. Owners must refresh plan descriptor bounds, source/profile pins and resource quotes before using the larger document; no existing native allocation is implicitly enlarged.

Logical buffers and stream reads are bounded; the prospective 512 MiB construction memory allowance is not a hard aggregate RSS claim. Alias expansion or audit size can exceed finite stops, in which case partial evidence remains and no successful manifest is published.

The manifest uses the existing `language-frozen-public-tree/v1` runtime/generic contract. The unchanged provider must still authenticate the actual ordinary tree and exact mount/interpreter requirements. A separate trusted numerical recheck, bubblewrap/dependency qualification, and protected provider invocation are still required. Source and generated-control acceptance alone do not establish authentic runtime, provider, or scientific qualification.
