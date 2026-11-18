# Original targets for the current NEURAL-067 scorer

This is a grader-only adapter for the fixed original FALCON H1 preparation. It does not execute participants, fit a model, implement a metric, or establish benchmark readiness. No recordings, targets, operator paths, or per-run target digest tables are shipped here.

`grade_submission(submission, prepared_root, evidence_paths, scorer_path=...)` calls the byte-pinned current session scorer. That scorer validates and snapshots all 56 prediction blocks before its first target callback. Constructing the lazy callback opens no files. The callback then authenticates the fixed whole-file source, preparation, original design, private bindings and successful execution metadata; joins all 40 original assets and 27 calibration runs; and authenticates each of the 14 query target files before decoding the same captured bytes. All rows and seven columns are retained. Original float64 velocity and uint8 masks are required. Masks become Python booleans only after strict 0/1 and full masked-count validation.

`grade_journals(...)` reuses the separately reviewed, unchanged 56-journal prediction bridge. It snapshots source input descriptors before bridge callbacks and joins them to the original design after complete current-scorer admission. The bridge remains a separate dependency; it is not reimplemented here. Causal execution, access mode and privacy enforcement remain external obligations.

The existing session scorer stays byte-identical: negative scores stay negative and constant targets retain its explicit undefined policy. The legacy tuple loader/force-finite metric is not substituted. Four information arms are not four access modes.

The five `evidence_paths` keys are `asset_manifest`, `design`, `private_bindings`, `attempt_receipt`, and `operator_result`. `PREPARATION.json` is read from `prepared_root`. All these metadata documents and the target NPZ files stay operator-private. Fixed whole-file pins identify the accepted original snapshot and observed preparation; a caller cannot replace them with its own manifest. A future source snapshot requires explicit reviewed source rebinding.

`guarded_npz.py` reuses the original task-local bounded capture/NPZ reader. Its only source delta replaces the `common.need` import with the same local guard. The adapter's source-capture function is the same ordinary-file, no-symlink, nonblocking, stable-fstat capture body. Public submission capture uses the reused reader too. The reader checks primitive members, bounded expanded extents and pickle-free decoding. These are software checks, not an OS sandbox.

The CLI accepts either `--submission` for grading or `--qualify-targets` for operator I/O qualification. Qualification first admits a complete synthetic prediction panel, then loads all 14 targets and emits only run/row/mask counts. It never invokes a metric, computes a scientific score or writes targets. Output must be fresh; the bounded report is file-fsynced. Root must check natural exit, output and owned process closure; a surviving partial report or timer exit is not success. No global deadline or OS RAM limit is provided by the module.

Run the maintained generated controls through the shared test pool:

```text
python -I -B test_target_callback.py --workdir <fresh owned test directory> --scorer-path <pinned session-evaluator-v1/scorer.py>
```

The test directory must exist and have no prior `generated-fixtures-v1` or result file. Tests generate only synthetic NPZ bodies at the full query geometry, patch expected whole-file metadata pins only inside tests, and exercise the composed current scorer. Production has no synthetic switch. Bridge controls cover the new composition seam without replaying the bridge's accepted suite. NumPy is needed for this adapter/reader; source-pin checks do not establish full environment qualification. Operator native qualification is separately root-selected.
