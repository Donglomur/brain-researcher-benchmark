# N062 ownership and logical-read contract

The scientific condition and phase API are preserved. This contract describes acquired container identity, independent failure cleanup and logical source-read accounting.

## Acquired container identity

The runner still uses the original `docker run` command, inputs, isolation flags, image, deadlines and resource limits. It adds `--cidfile` in the invocation's fresh 0700 host output directory. This file is outside the candidate's mounted scratch directory and is never exposed through a candidate mount. The maximum 65-byte receipt write is reserved before launching Docker. Docker's documented CLI creates the receipt file and refuses an existing one; native qualification must establish that behavior for the selected deployment.

The name remains a convenience for creation, never cleanup authority. Inspection and removal use only the receipt's complete 64-character lowercase hexadecimal container ID. The existing bounded ordinary reader validates the file, rejects links/nonregular/multiple-link or changing files, debits its observed extent plus sentinel before reading, and validates the exact ID grammar. A partial ID, malformed/absent file, stdout, or a matching name cannot authorize deletion.

On process failure, the original failure is retained first. A single independent receipt recovery is attempted if no receipt read was previously attempted. It uses an independent 66-byte logical-read owner, with its snapshot retained as a diagnostic cost event. An acquired ID permits bounded removal; absence or malformed identity records unknown cleanup and never falls back to removal by name. A timed-out or disconnected create path may therefore leave an unidentified container: this is explicit failure and unresolved retirement, never successful cleanup. It requires later qualified operator adjudication; this source does not enumerate or delete possible matches. Removal and scratch-unmount attempts remain independent, and their errors do not replace the first failure.

Host-output freshness and trusted Docker/host operation are concrete prerequisites, not a claim that receipt syntax alone grants authority in an arbitrary directory. This receipt can only arise on the selected runner path. An untrusted actor or compromised Docker daemon is not certified by this source. The existing genuine signed admission, image/host/resource evidence, full retirement and runtime qualification remain unavailable.

Docker API reference: [docker run, capture container ID](https://docs.docker.com/reference/cli/docker/container/run/#capture-container-id---cidfile). Native execution remains unqualified.

## Protocol alias reads

Both alias byte comparisons in `prepare.generation` now call the existing `delivery_io.read` under the active programme owner. The 200,000-byte per-alias cap bounds ordinary source bytes. Exact equality is preserved, and the later existing source-pin reads are retained rather than silently substituted or discounted. With the unchanged 2,282-byte aliases, each call now reserves an additional 4,566 logical read bytes including the two sentinels. Across the conditional complete 545 generation calls, this is 2,488,470 additional reserved bytes. This is source arithmetic, not an executed programme cost.

The cohort/source/projection/key generation join, authentic-data holds, feature preparation, all scientific estimators and target-last grading remain unchanged. Logical stream extents are distinct from unmeasured physical I/O, native allocations and full campaign capacity.

