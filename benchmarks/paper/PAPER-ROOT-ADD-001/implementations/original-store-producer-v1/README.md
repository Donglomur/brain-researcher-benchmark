# Original private store producer

This component prepares and reads the complete original source schedule without running a candidate. Its generated controls establish the producer, lineage, selected-view, and private recovery paths. No original store has been produced by this component, and no native provider or scientific result is qualified here.

The original scope requires all 14 sessions, 58,926 feature jobs, 6,776,076 held-qid software callbacks, and a subsequent 224-array result contract. These callback counts are source prediction requests, not completed AI calls. The producer requires 12,516 distinct feature objects, 1,764 private response classes, 202,407 response shards, 218,451 candidate-facing object specifications, and 220,243 total arrays. Generated prefix controls have a separate scope and cannot satisfy original completion.

## Exact source lineage

The producer imports authenticated unchanged `original-inputs-v1` transformations and iterates their canonical field → layer → lag order, within the original session order. The original supplied PCA representations, lexical NaN filtering, sentence-word swap, qid semantics, 40 lag positions and 33 layers remain unchanged. Each produced job is checked against the accepted support census. Feature sharing requires both the accepted feature key and byte-identical full X; one candidate view still contains exactly one feature job.

Population and unit response bases are prepared once per session by the original smoothing function and checked against the accepted Stage B byte hashes. Every job's private target is independently reconstructed from the base and its original source-row lineage, including negative-lag zero padding and seed-20 response permutation. The reconstructed target must match the original job's exact float64 C-order bytes before a class can be stored or reused. Each response shard contains exactly one qid group's rows; the existing cache exposes only other groups for a held request.

The original 579 `self_FR` population weights are bound to the full-member/header receipts from Stage B. The 567 continuous response channels do not replace those weights. The historical biological identity join between these counts remains unresolved.

## Private output layout

`STORE.json` binds preserved `CENSUS.json`, `GEOMETRY.json`, `PREPARATION.json`, source code and each session manifest. Each session has `OBJECTS.jsonl`, `FEATURES.jsonl`, `CLASSES.jsonl`, `JOBS.jsonl`, `SESSION.json`, candidate object files under `objects/`, and operator-only bases and source-row maps under `private/`. Object paths use opaque UUIDs. Array files are exclusive, ordinary, single-link, readonly, canonical 128-byte-header NPY 1.0, C-order float64 or int64. Directories are private. No full store manifest, class/source-response digest, held shard, unrelated feature, or target lineage becomes a candidate descriptor.

The maximum record bytes are 512 for object specifications, 640 for feature entries, 512 for jobs, and `2048 + 128 * Q` for a response class with Q held groups. Session manifests are bounded by 65,536 bytes and the root manifest by 131,072 bytes. The all-source logical estimate is 3,746,449,832 array bytes plus at most 182,769,693 metadata bytes: **3,929,219,525 bytes and 220,317 files**. Physical filesystem allocation, directory entries, inodes, failed attempts, and later execution products require separate reserves. These are planned full-source bounds, not measured produced-store sizes.

## Preparation API and admission

`prepare_original(output_root, archive_paths, census_path=..., preparation_path=..., admission_bytes=..., expected_admission_sha256=..., read_limit=..., working_limit=..., output_limit=..., metadata_limit=...)` is the actual-data seam. The admission must canonically bind the exact producer hash, pinned metadata, NumPy version, archive paths, output path, and finite allocations before archive open. The external orchestrator owns approval, storage reservation, process ownership, wall deadline, and runtime enforcement. A matching JSON digest is an operator binding, not an authorization or sandbox attestation.

Archive authentication must match the accepted Stage B SHA/MD5 receipts before numeric member reads. Original weight headers are reauthenticated. The existing archive reader charges source reads; metadata copies and produced writes have separate counters. The producer's joint logical workspace admission includes the archive reader's `4 * session_member_bytes + 64 MiB`, preprocessing/lineage/output buffers, and bounded index state. The largest original numeric session is 147,028,728 bytes. A future original-data protocol must admit the combined producer working set; no Stage B 1 GiB allocation or native permission is inherited.

`prepare_generated` accepts explicitly generated inputs and a prefix of 1–4,209 jobs per session. It is only a control seam. Failures retain exclusive partial output; no successful `STORE.json` is published. Output gross charge is admitted before each write, and failure does not make attempted bytes reusable.

## Reader and coordinator seam

`StoreReader(root, expected_store_sha256=..., read_limit=..., working_limit=...)` authenticates metadata and streams one session at a time. It exposes `metadata`, `scope`, `store_sha256`, `weights`, `iter_sessions()`, `private_metrics()`, and `close()`. Each session exposes `root`, `session`, fresh typed `specs`, `iter_jobs(include_targets=False, contexts=None)`, and `close()`.

Each job supplies a primitive six-field original context, the existing typed feature job, immutable qid/time maps, output width, private support and target hashes, selected feature identity, ordinary private feature path and specification. Default iteration opens only qid/time array files. `include_targets=True` additionally reconstructs and verifies private targets for trusted scoring after candidate closure. Returned arrays have immutable byte backing. File bytes plus an EOF probe are admitted before I/O; readonly/single-link/ordinary identity, exact extent/SHA and stable metadata are checked. Cached data reuse assumes a nonhostile trusted host; metadata changes fail closed.

`contexts` is `None` for the complete schedule, or a bounded list/tuple of up to 4,209 exact six-key primitive context dictionaries for that session. Duplicates or coordinates absent from the materialized canonical schedule fail before any selected array read. Results remain in canonical order; an empty selection returns none. This selector does not define a new scientific scope or promote partial results to full reproduction.

The private reader and candidate `FileStore` have separate, actual read and retained-memory counters. Duplicate map reads are explicit. A coordinator must account for their simultaneous state, selected feature staging, bundles, authority/prediction storage and runtime overhead. The maximum existing per-session `FileStore` constructor preflight alone is **323,272,704 bytes**; the older 285.7 MB feasibility estimate is not a bound for this implementation. Session resources must be released before advancing; the global 218,451-object store is not loaded into one cache.

## Generated evidence and remaining boundaries

Seven generated methods passed initially, including all 4,209 source transformations in memory and three small physical prefix stores. The selected-iterator delta passed separately. Controls verify byte-exact source callbacks and private target recovery, feature/class sharing, mutation refusal, no default target/feature reads, pre-I/O limits and refusal of malformed original admissions. No original array payload, candidate model, native process provider, or new author training was executed.

Original-data production, native isolation, end-to-end candidate execution, reproducibility under historical preprocessing versions, participant independence/uncertainty, and the original population-unit identity join remain separate gates. Continuous paired improvements must use the same held task and preserved source metrics; source p-values do not establish an improvement or a new SOTA.
