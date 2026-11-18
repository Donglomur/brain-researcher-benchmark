# SUNS2 original-panel fold input contract

The projector defines the data boundary for the original Figure 5c TUnCaT spatial segmentation task. It preserves all nine original movies and supplies exactly eight manual-mask files per held-video fold. It writes a participant manifest and an operator-only file-level bind specification. It does not copy payloads, mount files, start a candidate, enforce a namespace, or establish benchmark readiness.

The complete current-v3 original movie bank, manual-mask byte identities and saved author outputs are now authenticated in separate admitted and independently reviewed stages. All nine original movies passed a complete readability scan. This projector has not yet accepted an authentic material manifest or mounted a protected fold. Its generated tests use deliberately fake byte fixtures with generated trusted receipts; those tests do not establish the separate source authentication, HDF5/MAT validity, neuroscience performance or process isolation.

## Trusted authority and API

`freeze_procedure(lock_path, procedure_digest, condition, trusted_material_sha256, trusted_code_sha256=None)` creates an exclusive operator-side lock before any fold is projected. The complete procedure digest and assistance condition remain unchanged across folds. Existing locks cannot be overwritten, and each fold gets an exclusive claim. A failed claimed projection remains recorded and cannot be silently retried with a different destination.

`project_fold(material_manifest_path, trusted_material_sha256, bank_root, destination, fold_index, condition, procedure_digest, lock_path, *, code_manifest_path=None, trusted_code_sha256=None, code_root=None)` verifies the lock, externally pinned material manifest, original support and all source file bytes. It then writes only `fold.json` in a new destination. The private completion receipt next to the lock includes the exact read-only bind specification and logical hashing counts.

The trusted digest arguments must come from the coordinator's independently qualified authentication/review record. A candidate cannot supply them. A self-declared `authenticated` status or a newly computed digest of a candidate manifest does not establish source authority. The projector verifies a trusted attestation and its files; it does not independently authenticate the historical paper, inspect scientific array contents, or infer file roles from names.

The private lock, source authentication manifests, claims and bind receipts must stay outside participant-visible mounts. The participant manifest contains hashes only for the nine movies, eight permitted training masks and optional permitted code. It excludes the held-mask hash, complete private inventory, author predictions, evaluator summaries and protected root paths.

## Material schema

The exact top-level keys of `suns2-authenticated-materials/v1` are:

- `schema`, `task`, `status` (`authenticated_original_inputs`), and `authentication_receipt_sha256`.
- `source`: exact keys `object_id`, `version`, `archive_bytes`, `archive_sha256`, `archive_md5`. The current input object is Figshare **49636131**, version **3**, **248,562,067 bytes**, with advertised MD5 **e4aaf274478253cfea21580594ab2e36**. The whole-object SHA256 must be supplied from the admitted acquisition receipt. This identity does not assert version-2 whole-payload equality.
- `videos` and `manual_masks`: exactly nine entries each, in original source fold order. Every entry has `video_id`, `role`, `path`, `source_member`, `bytes`, `sha256`, and `shape`. Local paths are relative to the protected bank. Source members must be `<video_id>.h5` and `GT Masks/FinalMasks_<video_id>.mat` respectively.
- `common_support`: exactly `{"temporal_template":"quarantined_pending_provenance"}`. This implementation offers no self-asserted override. The global temporal template is neither exposed nor silently replaced; a future scientific selection requires a separately reviewed contract revision.

The source movie consumer uses `(time, row, col)`, so the required qualified movie shape is **[6000, 50, 50]**, rather than silently transposing a differently shaped array. Manual-mask axes are **(col, row, neuron)**, with shape **[50, 50, N]** and the already qualified counts 48, 40, 86, 42, 57, 81, 81, 47 and 79 in source order. Thus **movie[t,row,col] corresponds to Masks[col,row,neuron]**. The retained author `generate_masks_tuncat.py` transposes original `FinalMasks` by `[2,1,0]` for alignment with network-input axes. The projector declares this relation and preserves original file bytes; it performs no transpose. Equal 50×50 dimensions alone do not establish the coordinate join. Header and content facts must be established by admitted preparation, not invented by this projector.

The source fold order is `c25_59_228`, `c27_12_326`, `c28_83_210`, `c25_163_267`, `c27_114_176`, `c28_161_149`, `c25_123_348`, `c27_122_121`, `c28_163_244`. Nine videos do not establish nine independent animals.

## Assistance conditions

`paper_data` and `paper_data_official_code` receive the same nine movies and eight active-fold training masks. The paper is supplied through the coordinator's common task prompt or independently pinned paper artifact; this file projector does not itself deliver a PDF.

The code condition additionally requires an externally pinned `suns2-official-code-allowlist/v1` manifest with exact keys `schema`, `task`, `release`, `commit`, `source_role`, and `files`. Each file has `path`, `bytes`, and `sha256`. The supported identities remain separate:

- Paper-cited v1.1.0: `71d1037859b85fb2e104d74f9307f7ac3ecaf19c`.
- Post-publication v1.2.0: `128eb4738e026b89a341a6013e7bd7b6dc7c3216`.

The allowlist must already have been reviewed to exclude answer-bearing material. Its exact role string is `reviewed_official_code_without_answers_or_weights`. Textual source extensions and exactly the original extensionless license paths `LICENSE` and `SUNS2/LICENSE` are supported; all other extensionless paths and data/results/weights directories are rejected. These two license exceptions preserve the selected official package's notices without admitting arbitrary binary artifacts. Extension checks cannot prove that source text contains no embedded answers; the external code-review digest is essential. Released weights require a separately declared, authenticated fold-lineage condition and are not supported by this interface.

The original author source passes held-video masks into a validation path. Inspected fixed-epoch/final-save behavior does not demonstrate validation-driven selection. Removing that exposure is a protected execution adaptation, not automatically an identical replay of the original training recipe. Neither fresh training reproduction nor checkpoint lineage is qualified here.

## Filesystem and runtime boundary

Every manifest and source leaf is opened without following symlinks, with nonblocking type admission to reject FIFOs before any blocking read. Source paths reject traversal, noncanonical paths and collisions. Regular files must have one hard link; inode and content aliases across source roles/cases are refused. Sizes and streaming SHA256 values are verified against the externally pinned receipt, with file identity checked before and after reading. The destination must be new and disjoint from the protected bank. Existing fold claims and late failures are retained.

These checks are time-specific. A later qualified runner must revalidate an immutable bank, apply only the **17 selected data-file binds plus the separately qualified code-file binds in `paper_data_official_code`**, mount them read-only in a fresh candidate namespace, and keep the entire protected bank and operator receipts inaccessible. It must never mount a parent containing the held label. A manifest alone cannot protect files from another process with the same host permissions, prevent namespace/path races in an unqualified runtime, reset candidate memory, or prevent cross-fold feedback. No such runtime was executed in this stage.

The original dataset and author outputs are publicly exposed. Runtime isolation does not prove absence of prior access or pretraining contamination.

## Costs and verification

No movie or mask payload is copied by `project_fold`. Each call hashes all nine movies and all nine manual masks privately, including the held mask, before constructing the selected bind list. For the original inventory this is **270,028,406 logical bytes per fold**, or **2,430,255,654 bytes over all nine folds**, plus optional code and small manifests. These are logical hash-input bytes, not measured physical disk I/O. New writes are only bounded manifests, locks, claims and receipts; read volume must not be counted as nine new movie-bank copies.

The source interface caps each material file at 32 MiB, aggregate material at 280 MiB, manifests at 1 MiB, and optional textual code at 1,024 files/8 MiB total. These are explicit engineering bounds, not biological constraints or measurements of model cost.

The initial generated suite had 22 tests and passed once in the shared short pool in 0.14276 seconds, with observed peak child RSS 21,430,272 bytes. An additive asymmetric generated-byte control checks that the axis relation is declared while file/bind hashes remain unchanged; it does not decode real HDF5/MAT data or establish the actual index conversion (the parent coordinate helper has separate controls). The suite covers complete nine-fold support, held-mask hash exclusion, both assistance conditions, byte/digest/role failures, source and parent symlinks, hard links, FIFOs, immutable procedure/fold claims and retained late failure. These qualify a file-boundary component on generated inputs, not authentic source preparation or hostile-code containment.
