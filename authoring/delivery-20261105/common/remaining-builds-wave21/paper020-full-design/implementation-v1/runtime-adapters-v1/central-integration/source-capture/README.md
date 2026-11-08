# IT parent source capture

`capture.py` is a standard-library-only source snapshot helper. The central
bootstrap must authenticate this helper and its fixed binding and reject stale
registry/preference routes before calling it. Source identity does not grant
installation, original-input, provider, native-process or scientific authority.

```python
snapshot = capture_source(
    canonical_absolute_repo_root_string,
    read_limit_bytes=REQUIRED_READ_LIMIT_BYTES,
    origin_ns=original_origin_ns,
    deadline_ns=original_deadline_ns,
)
```

The original monotonic clock is required and checked before any source open and
after closure checks and descriptor release. The parent must bind that clock to
its admitted operation; this helper does not authenticate caller clock values.
`REQUIRED_READ_LIMIT_BYTES` is **477111**, including the **14843** binding bytes
and **462268** source bytes. A lower reservation fails before opening the root;
a larger bound cannot expand the source closure. These are logical body-read
bounds, not measured filesystem I/O, RSS or an OS deadline guarantee.

The frozen `SourceCapture` contains `.members`, `.read_bytes`,
`.binding_sha256`, `.scientific_source_digest` and `.merge_receipt_pin`.
Each frozen `SourceMember` has `source_path`, `staged_path`, `role`, `size_bytes`,
`sha256` and immutable `body` bytes. The merge receipt is a frozen `SourcePin`
with `source_path`, `size_bytes` and `sha256`. `CaptureError.read_bytes` retains
logical bytes read on failure. No partial source snapshot is returned.

All **34** members are mandatory: the accepted **15** adapter V3 production
bodies plus their adapter manifest, and the unchanged **18** scientific V2
members, including the programme and operator-protocol contracts. The fixed
binding derives from the accepted adapter manifest and scientific source
identity. There is no caller-selected file list, replacement manifest, loader,
callback or source-body operand. The helper neither imports nor executes any
captured member.

The returned relative layout is exact:

* `implementation-v1/runtime-adapters-v1/successor-v3/` for the adapter bodies
  and manifest;
* `implementation-v1/successor-v2/` for the complete scientific closure.

The parent owns authenticated staging and must preserve all paths and members
under one staging root so that `basis.scientific_root` resolves the same sibling
layout. Returning bytes does not itself establish staging custody, dependencies,
installation, authentic native compatibility or readiness to run the full
23786-phase programme. There is no staged data, key, original MAT header/body,
held answer, provider credential, weight or input operand in this closure.

Every path component is opened with `O_NOFOLLOW`; directories also require
`O_DIRECTORY`. Source files must be single-link regular files of the pinned
length. `O_NONBLOCK` prevents a substituted FIFO blocking before type checking.
Every traversed parent directory and source file descriptor stays owned until
the final descriptor/path identity checks. File identity includes device, inode,
mode, link count, size, modification time and change time. Every returned body
matches its mandatory SHA-256 pin. Parent-directory identity is checked without
rejecting unrelated sibling edits or performing a recursive repository census.
The maximum held descriptor count is 128. All descriptors close on success or
failure. Canonical absolute root strings and relative paths are required;
symlink root spellings are refused rather than silently resolved.

The fixed binding includes authenticated provenance for root's observed batch123
merge receipt: 2807 bytes, SHA-256
`b44aea0bf9d8e5e9e9af964c12d276a1a0a45a48c46d7783e6c378f1448fdcdb`,
reporting integrated commit `a6fbda99793e0f8beb6c1ac7f89e09ca3007e507`.
The helper audited that receipt as source metadata; it did not inspect Git refs.
At runtime this provenance is returned from the authenticated binding without
reopening the receipt or expanding the 34-member staging closure. No changing
WORK hash is embedded; the parent owns live stable registry/preference joins.

Eight focused controls passed. One read the exact accepted source closure and
verified that importing captured pipeline modules did not occur. Tiny invented
metadata controls covered budget and clock failure before source open, clock
expiry after capture, owned descriptor closure, path replacement, directory
replacement, symlinks, hardlinks, wrong hashes, unsafe paths and wrong sizes.
The final-clock control used an explicit private empty reader seam; it was not
a second authentic source capture or scientific execution. No tests called an
original executable, imported scientific code, opened authentic arrays/keys or
ran the full graph.
