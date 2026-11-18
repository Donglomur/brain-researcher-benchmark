# NEURAL-002: source-authenticated expected file pins

This compiler fills the missing translation from the selected MorseEEG source
objects to the existing `morse-pinned-cohort-v1` manifest. It does not replace the
registered provider, import recordings, create windows, issue approval, or run a
participant. The fixed benchmark still uses all32 people, both `dotcount` and
`firstlast` recordings, six task/speed cells and9984 protected windows.

The production trust anchor is the existing80770-byte `SOURCES.json`, SHA256
`3ec6ba3dcf60c49ee381126958a617a87eadfcbabce09a5cf8bd3eb12ab0af8e`,
selected at benchmark repository commit
`8e9eeddf8327094d631a2f015d9334b9078e98f5`. It binds OpenNeuro ds007655 source
commit `d2e09f610d267b8b3679997f8bc4e52fe6ca402a`. There is no source-hash or cohort
override in the public API or command line.

## Supplied inputs

An operator must separately obtain the exact256 raw **Git blob bodies** named in
that source roster:192 symlink metadata blobs and64 ordinary events blobs. Place
them as `<40-hex-Git-object-id>.blob` in an ordinary directory, with no extra
entries. These files are source-object bodies, not resolved annex recordings.
The selected source extents sum to640964 bytes:602056 event bytes,12800 header
pointer bytes,12800 marker pointer bytes and13308 signal pointer bytes. None of
those pointer extents is the extent of its actual raw recording.

The directory reader accepts only bounded, stable, singly linked regular files;
symlinks and hardlinks are rejected. The API equivalent is
`compile_pins(source_bytes, supplied_rows)`, where all256 rows have exactly
`path`, `git_mode`, `git_object`, and immutable `body` bytes. Input row order may
vary; the output follows the fixed source order. Any missing, additional,
duplicate, wrong-path, wrong-mode, wrong-extent or tampered object aborts the
whole projection. Every object authenticates using Git's framed blob SHA1 before
any pointer is interpreted.

## Supported source pointer form

Three independently selected metadata responses were captured once from the
GitHub Git blob API, with exact decoded sizes and framed Git SHA1 authentication.
They establish this source pointer family:

```
../../.git/annex/objects/AA/bb/SHA256E-s<positive-size>--<64-lowercase-hex>.<extension>/SHA256E-s<same-size>--<same-digest>.<same-extension>
```

Both shard components must be two alphanumeric characters. The full content key
must repeat exactly, with the role's `.vhdr`, `.vmrk` or `.eeg` extension. Leading
zero sizes, alternate layouts/backends, whitespace and mismatched keys are
rejected. The supported grammar comes from three authenticated examples; the
remaining189 pointer objects have not been inspected in this construction step.
A different valid upstream format will fail closed until separately justified.
The code never follows the relative path or opens an annex target.

The key states an **expected** payload SHA256 and extent. It does not prove that
any raw file has been acquired or authenticated. The three observed expected
extents are1535 header bytes,5643 marker bytes and201207360 signal bytes. Header
and marker limits remain1MiB; the signal limit remains8GiB, matching the existing
provider. The64 ordinary event bodies are hashed byte-for-byte without decoding,
rewriting or approving their labels. `SOURCES.eeg` maps to manifest `signal`.

## Operator command

After the separately authorized full source-object acquisition:

```sh
python3 -I -S -B source_pin_compiler.py \
  --sources /absolute/registered-runtime/SOURCES.json \
  --blobs /absolute/supplied-git-blobs \
  --manifest-output /absolute/new/morse-pinned-cohort.json \
  --receipt-output /absolute/new/source-pin-projection.json
```

Both output parents must already exist and both output files must be new.
Compilation completes before publication starts. Writes are exclusive and
flushed; failures retain their partial files for diagnosis. Accept a publication
only after successful exit, with both files present and the receipt's
`manifest_sha256` matching the exact emitted manifest bytes. A failed second
write is not a successful two-file publication. No overwrite, acquisition,
installation, Git command, credential, model call, or network request exists in
the compiler.

The first output has the unchanged intake schema:64 ordered recordings, each
with header/markers/events/signal pins,256 entries total. The second output
records each source object's mode, Git SHA1, source extent/SHA256, projection
method and expected payload pin. It explicitly denies raw-payload custody,
scientific certification, provider/runtime admission, and full dataset-tag to
source-commit equivalence. Matching descriptor fields observed previously do
not establish that last equivalence.

Feed the complete expected manifest into the existing protected production
configuration and provider only after the corresponding raw payloads, operator
approval and custody are separately supplied. The existing provider still checks
actual bytes, channel scaling, recording pair names, marker/event alignment and
full support before protected export. Viewer image delivery, participant context
freshness, model readability and scientific scoring qualification are unchanged.

## Validation and integration seam

`source_pin_compiler.py` and its controls use the Python standard library only; file controls target the existing POSIX runtime.
Proposed task-local location is
`implementations/source-pin-compiler-v1/`, beside `registered-runtime/`.
Keep the registered runtime's fixed source inventory unchanged: install this
adjunct, supplied blobs and generated outputs outside that directory. The CLI
requires an explicit `--sources` path to the existing
`registered-runtime/SOURCES.json`; it has no default or parent-relative source
lookup. The controls import the compiler beside their own file and remain
unchanged. Run the maintained controls with the existing shared two-slot pool:

```sh
python3 -I -S -B test_source_pin_compiler.py
```

Twelve distinct controls passed: the initial11-method run and one focused FIFO
refusal control after independent review. The reader opens inputs nonblocking
before checking file type, so a substituted named pipe cannot stall intake. A generated64-recording/256-object fixture
exercises the complete directory/CLI path. Other controls check source anchoring,
full support, role mapping, all-object authentication before interpretation,
malformed/unsupported keys, opaque event hashing, and publication/file boundaries.
Private source-identity constants are patched only inside generated tests; this
is explicitly synthetic trust and is not a production source override. The
observed three pointer examples separately reproduce their pinned Git object
IDs. No authentic recordings, neural arrays, provider run, model run or scientific
result was produced. The old viewer/campaign tests were not replayed.
