# OpenBMI full-cohort acquisition source

This source-tested Python 3.11 component acquires the fixed NEURAL-083 motor-imagery corpus: 54 participants, both sessions, 108 original MAT files, and **64,847,432,285 bytes**. It produces the source-hash manifest used by [the adaptive investigation preparation route](../adaptive-investigation-v1/README.md). It does not prepare neural arrays, establish their schema, fit a model, or qualify a scientific benchmark. No authentic recording was downloaded to validate this public package.

## Portable, inert example

From a physical checkout directory, run the following with Python 3.11. The supplied request deliberately refuses execution before output creation, resource-limit changes, or network access; a nonzero exit with `separate actual root execution selection required` is the expected result.

```sh
NEURAL083_ACQUISITION="$(pwd -P)/benchmarks/neuroscience/neural-083/acquisition-v1"
python3.11 -I -S -B "$NEURAL083_ACQUISITION/acquire.py" \
  --roster "$NEURAL083_ACQUISITION/publisher_roster.json" \
  --request "$NEURAL083_ACQUISITION/REQUEST.INERT.json" \
  --request-bytes 262 \
  --request-sha256 f062f0104a521cb7319a28ef10b46583b879091bcf0a1b7ae9ed0fb993f17a00
```

The CLI's word `root` means the operation's selecting coordinator; it does not require a privileged operating-system account. No `sudo` is needed. The package can also be copied as one directory; set `NEURAL083_ACQUISITION` to that directory's physical absolute path. Its authenticated helper is loaded beside `acquire.py`, independently of the working directory and Python import path. All source/request/output ancestors must be ordinary directories: symlinks, including temporary-directory aliases, are refused. Do not bypass that boundary by editing the source. The output parent must exist and the output directory itself must be fresh and absent.

Run the public packaging checks without network or numerical dependencies:

```sh
python3.11 -I -S -B "$NEURAL083_ACQUISITION/test_public_source.py"
```

These checks copy only this source package into fresh temporary directories and validate relocation, dependency pins, inert refusal and the complete publisher roster. The separate `test_acquire.py` contains the generated transport, corruption, interruption, partial-write, framing, redirect, path and timer controls. It uses invented bytes/connectors; no MAT file is fetched. Historical generated checks were versioned during development; this public packaging validation is not a claim that every historical suite was replayed against this projection.

## Publisher bindings and receipts

`publisher_roster.json` fixes every unsigned HTTPS object URL, byte extent and publisher MD5. The roster body and normalized 108-row digest are pinned in `acquire.py`. Its checksum provenance is the [GigaDB 100542 checksum sidecar](https://s3.ap-northeast-1.wasabisys.com/gigadb-datasets/live/pub/10.5524/100001_101000/100542/100542.md5): 33,427 bytes, SHA256 `20b1ef60db5877a8508bfb9fb04a206cf9173d884bf48850ce2627d55c957cb4`. The metadata agrees with the existing programme's complete source inventory, SHA256 `aef0f1c484527da571a2b77a0c93bf081ba4fd51aed6e3bf1babd4fae9f8f9ce`.

Those are publisher declarations, not observations of downloaded recordings. MD5 checks transfer agreement with that declaration; it is not a digital signature or a collision-resistant authenticity guarantee. Multipart ETags are not used. Simultaneous SHA256 identifies the successfully written acquired bytes; it is not an independently published expected SHA256. Expected SHA256 values remain unavailable until a real, fully successful acquisition supplies them.

Production accepts only the fixed HTTPS origin/path, HTTP 200, a unique exact Content-Length and identity encoding. It refuses redirects, alternate hosts, chunked framing, compression, retries and resume. The direct stdlib HTTPS connection uses default certificate/hostname verification and does not consume proxy configuration or cookies. Reads are at most 65,536 bytes. Short writes are completed explicitly; both digests charge only confirmed successful writes. A rejected EOF-probe byte is counted as received without entering written-byte hashes.

For each object, complete extent and publisher MD5 must match. File fsync, no-clobber hard-link publication, directory fsync, temporary-name removal, final inode/link checks and closure must succeed before its success receipt. The selected filesystem must support those operations. Failures retain partial files; a publication failure can leave both names. No overwrite, retry, deletion or automatic recovery is selected. Disk failure or abrupt termination can prevent a receipt or an unwritten received suffix from being preserved.

Only all 108 durable successes emit `verified-sources.json` and `COMPLETE.json`. The complete receipt pins the manifest and each object receipt. The generated internal engine emits `generated-sources.json` with a different schema and `GENERATED_CONTROL_ONLY`, never an admissible authentic-source manifest.

The resulting `neural083_verified_sources_v1` manifest can supply expected SHA256 values to the existing preparation contract. Preparation still authenticates each current original MAT body once and decodes those same captured bytes; finalization still makes its two derived-array passes. Acquisition removes a separate prehash sweep, not the mandatory current-body authentication. Authoritative per-file schema/class/channel bindings and runtime qualification remain unresolved; this tool does not guess them.

## A future operation needs its own owner and storage

Do not toggle the inert request as a substitute for resource admission. A future selected operation needs a separately frozen request, its exact byte/SHA256 pin, legitimate dataset access, an independently enforced execution owner, and a storage reservation accounting for other work. The request has these fields:

- `schema`: `neural083_acquisition_request_v1`; `execution_authorized`: true only for a separately selected operation.
- `output_root`: physical absolute path to a fresh output directory.
- `whole_seconds`, `request_seconds`, `socket_seconds`, `cpu_seconds`: positive integers capped at 43,200, 3,600, 30 and 3,600 respectively, with socket <= request <= whole.
- `minimum_free_bytes`: at least 64,851,626,589 (the full corpus plus the 4 MiB metadata partition), increased as needed for reservations and filesystem headroom.
- `owner_receipt`: a declaration including `hard_memory_bytes: 134217728` and `aggregate_cpu_seconds` equal to the requested CPU allowance. These fields do not enforce or attest those limits.

The fresh free-space check is not a reservation against concurrent writers. The source applies a process CPU soft limit without raising an inherited limit and carries its original monotonic deadline through I/O. A compatible active inherited timer is retained untouched; an ambiguous or longer inherited timer causes refusal without rearming. A new relative alarm has syscall/scheduling latency. Socket timeouts bound inactivity; request deadlines are cooperative between operations. None of this establishes an exact absolute kernel deadline or hard aggregate memory/process-tree containment.

The external owner must enforce memory, aggregate CPU, wall time and finite cleanup, and reserve storage before execution. The 128 MiB request declaration is a requested ceiling, not measured authentic-transfer sufficiency. Authentic TLS/provider behavior, full-transfer throughput, durable filesystem behavior and the execution owner remain unqualified. Acquisition receipts and raw consumed HTTP header evidence belong in operator storage, not the public repository.

`SOURCE.json` pins the public source payloads. See [NOTICE.md](NOTICE.md) and [LICENSE](LICENSE) for attribution and the limits of the code license. The acquisition package is not a benchmark success result, prepared dataset or readiness promotion.
