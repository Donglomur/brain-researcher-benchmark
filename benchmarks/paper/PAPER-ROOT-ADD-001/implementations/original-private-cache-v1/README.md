# Private authenticated reads and compact-input cache

This trusted-operator module reads prepared immutable objects and caches exactly selected response/maps bundles. It does not prepare authentic source arrays, expose a participant filesystem or execute candidate code. The paper's 14 sessions, eight people, 58,926 feature jobs and 6,776,076 software prediction requests remain unchanged. These counts do not imply that many AI API calls.

`FileStore` snapshots a finite typed manifest. Its first read authenticates an ordinary, single-link, read-only file against its full SHA-256, exact extent and primitive NPY dtype, shape, order and finite-value rules. That first body can directly supply the requested array; it is not discarded and immediately reread. Qid/time bytes remain cached. Later response loads charge actual body rereads plus an EOF allowance and check the authenticated stable file identity and header. They do not hash the entire body again.

This reuse assumes a trusted host and immutable prepared files. Device/inode/mode/link-count/extent/mtime/ctime checks detect ordinary changes; they do not defend against a privileged hostile host. Every descriptor closes within its call. Returned arrays are fresh views into immutable bytes, so a caller changing view shape cannot rebind the store's authority. Caller-owned returned values have independent lifetimes outside the store's retained-byte counters.

`BundleCache.get(job, held_qid)` loads only permitted maps and selected training-response shards. It never looks up or opens the held-response specification, selected feature file or unrelated feature files merely to construct a response/maps bundle. Its private key binds the session, held-qid bits, exact permitted map/spec identities and row assignments. The key excludes feature/layer identities. Jobs may therefore reuse identical permitted response/maps bytes while retaining separate feature observations and candidate state. Private object identities make this a sufficient reuse condition; it does not claim maximal deduplication.

The LRU retains immutable bytes under separate payload, entry and metadata limits. Exact identity bytes accompany the key digest to reject collisions. Hits check the selected files' stable identities. Misses account for the complete gathered response bodies, builder workspace, new authentication metadata and retained entry before reading targets. Every actual rebuild, including after eviction, increments its counters. There is no unbounded seen-key history or claim that each source bundle is built only once.

All cache state is private. Across requests it can contain responses hidden from a particular candidate invocation; it must never be mounted for a candidate or inherited through a plain fork of the private coordinator. Actual fresh execution, namespace/FD enforcement and lifecycle closure remain separate work. The module is for serialized trusted-operator use, not concurrent hostile mutation or an untrusted Python caller.

Read, authentication, reread, cache-hit, creation, eviction, retained-byte and peak logical admission counters are separate. Failed operations latch failure rather than silently retry or refund previous reads. Logical byte/workspace admissions are not kernel I/O or RSS measurements. Constructor snapshot admission is included in the reported peak. It requires 8,192 bytes per declared object before snapshotting: the previously proposed 39,462-object largest session therefore requires at least 323,272,704 bytes of working allowance for that constructor alone. The older 285,710,632-byte estimate described a different implementation and must not be reused as this cache's bound. Retained bundles, assembly and candidate/runtime costs require their own joint allowance.

One cache may attach to each store; the attachment token creates no store-to-cache reference cycle. Session disposal still requires the caller to release its references and outputs. No actual full-session cache, native throughput or campaign affordability has been qualified here.

Run the generated controls:

```sh
python3 -I -B benchmarks/paper/PAPER-ROOT-ADD-001/implementations/original-private-cache-v1/test_cache.py -v
```

They cover first-read/reread accounting, immutable map reuse, feature-independent selected-input hits, unopened hidden files, eviction/rebuild correctness, mutation refusal, budgets, ordinary-file custody, manifest snapshots, lifecycle and constructor accounting. The sibling scoring-join controls additionally exercise this real cache through compact IDs, packed prediction recovery and the unchanged original Pearson scorer. Only NumPy is required; no original dataset, model fit or native provider is run.
