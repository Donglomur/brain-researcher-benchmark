# Explicit current-source NuCLR transductive readout

This additive adapter selects the adopted `multi_split_resample_transductive_v1`
route for E/I, five-subclass and eleven-class ordinary transductive panels. It
reuses the pinned original selector and existing evaluator. It changes no
split membership, scientific endpoint, native array, preparation document or
benchmark ID. The complete nine-panel inventory and invalid E/I-inductive
refusal remain visible.

`route-adoption.json` pins the root decision, source script, reader and evaluator.
The source is official revision `0fa409b304147ace00507063d44f03155691af62`,
`eval_scripts/multi_split_eval.py` with `--class-balance=resample`, including its
single-dictionary train/validation/test path. This selects an executable current
source condition. It does not recover the historical Bugeon execution or fix
the released README's incompatible single-script flag.

## API and custody

`bind_preparation_metadata(owner_root, *, file_sha256, protected_run_root,
implementation_root=None)` uses the exact pinned `native-metadata-reader-v2`
reader and public `ACCEPTED_INPUTS.json`. The supplied exact file digests for
COMPLETE, native-manifest and joined-panels JSON must equal the three accepted
hashes. `protected_run_root` must strictly enclose the preparation directory and
identify its complete original run tree. Both paths must be absolute existing
directories without parent traversal or symlink ancestors. The adapter
validates their canonical completion bindings separately from their file hashes.
Only metadata and pinned source files are read. No array hashes, percentiles,
source extraction or model work is repeated. The pinned public acceptance record
binds the accepted verification receipt and independent review identities. This
does not repeat the upstream 257-asset verification or authenticate a mutable
array copy at the caller's path. Input-role declarations alone cannot establish
authenticity; representation qualification remains separate.

`bind_generated_control_metadata(*, manifest, joined, completion,
protected_run_root, implementation_root=None)` is the explicit generated-only
boundary. It validates complete copied fixture documents in memory with the
pinned reader, without writing them or claiming file or array custody. Its
binding cannot create an `authentic_candidate` packet. Generated receipts carry
no accepted-input or prior asset-verification identity. The protected run root
must still be an existing absolute directory without symlink ancestors.

`select_current_route(binding, *, label_level, panel, route_id=...)` invokes the
unchanged original selector before checking this route's transductive scope.
It returns a `RouteSelection` with a no-fit receipt. Unsupported routes refuse;
attempting the invalid E/I-inductive artifact still encounters its original
topology refusal. The binding retains all nine original joined objects.

`build_current_route_packet(selection, checkpoints, *, input_role,
context_variant, representation_training_sessions)` produces the existing
evaluator packet plus a packet-bound no-fit receipt. `input_role` is explicitly
`generated_engineering_control` or `authentic_candidate`; the latter requires
the accepted-input binding. It supplies no model or representation qualification.
The packet receipt discloses the full source session manifest, declared
representation-training sessions and current transductive preprocessing and
readout exposure. Representation exposure remains explicitly unverified.
Checkpoints must have complete labeled-ID
coverage, exactly the same literal row order, strictly increasing numeric
epochs and one fixed embedding width. No filename, class or ID sorting occurs
inside the adapter. Source float32 conversion remains in the evaluator.

The packet receipt includes a separate address list in the actual checkpoint
row order. It does not force that order to equal label-map insertion order:
seed-42 resampling depends on the supplied row order. The frozen v1 packet
helper and its stronger order requirement are left unchanged. Existing native
historical flags and remaining-holds text are copied without clearing them.

`evaluate_current_route(selection, packet, route_receipt)` is the explicit
numerical entry point. A separately admitted execution protocol is required.
It validates the packet/receipt bindings, calls the unchanged evaluator once,
and returns its result unchanged beside an execution receipt. Receipt creation
and selection never call this entry point implicitly. A failed fit propagates
its exception rather than producing a successful execution receipt.

`write_receipt_new(selection, path, receipt)` writes an exclusive new private
sidecar into an existing separately allocated directory. It binds the receipt
to the selection, rechecks the protected original run directory's identity,
and refuses any output inside that entire tree. Use a sibling route-receipt
area. Absolute paths are required; parent traversal and symlink ancestors are
refused. Directories are opened component by component with no-follow semantics,
and each opened ancestor is checked against the protected directory's device
and inode, including differently cased path aliases. Double-root POSIX paths
are refused. The final exclusive file is created relative to the resulting directory
descriptor. Each sidecar is capped
at 1 MiB. Exact file and canonical receipt digests are returned separately.
No overwrite, array read or model fit is performed by this writer. Ancestor
ownership, operation authority, resource ceilings and failure cleanup remain
the external owner's responsibility; these Python objects are not an isolation
or signature mechanism.

When installed, the default implementation root is this component's parent,
beside `native-metadata-reader-v2`, `native-inputs-v1`, `source-splits-v2` and
`initial-evaluator-v1`. Staged/generated callers may supply another root; each
loaded source still has to match its fixed digest. No import-path mutation is
used. Private preparation paths are never embedded into a route receipt.

## Selected arithmetic and limits

Training indices are oversampled with RandomOverSampler seed42 before fitting
StandardScaler. LogisticRegression uses newton-cg, C=1, tolerance1e-4,
max_iter1000 and no class weights. Highest validation macro-F1 selects the
checkpoint; an exact tie keeps the earliest numeric epoch. The selected final
readout refits on original train plus validation with fresh resampling, scaler
and classifier. Complete test predictions feed the existing pooled balanced
accuracy and macro-F1 implementation.

For K checkpoints, the benchmark executes K validation fits plus one selected
final fit. The original source eagerly schedules K validation and K final fits.
Receipts preserve this difference, strict full coverage and the benchmark's
ConvergenceWarning refusal. No scoring arithmetic is duplicated here. No
unselected test results are used for selection or exposed by this wrapper.

The adapter preserves the frozen metadata's old unresolved-route flag while
recording the newly selected current route separately. Historical parity,
authentic reference qualification and scientific readiness remain false. The
representation, compute/exposure budget, source comparators and final protected
evaluation require their own evidence.

## Construction checks

Fifteen local generated controls passed. They exercise full metadata binding,
checkpoint row order, original split refusal, sidecar protection and source
versus evaluator execution traces. They use real NumPy and StandardScaler with
explicit RandomOverSampler and classifier test doubles. They establish the
tested ordering and selection behavior; they do not establish numerical parity
for the real resampling library. No authentic embeddings or readout fits ran.

`test_hosted_ros_parity.py` defines three required real-library controls on tiny
generated operands. Missing imbalanced-learn or a mismatched runtime fails the
hosted check; no skip or weighting substitute is permitted. The selected current
CI condition uses CPython 3.11.18, NumPy 2.2.6, SciPy 1.15.3, scikit-learn 1.6.1,
imbalanced-learn 0.14.0, joblib 1.5.3 and threadpoolctl 3.6.0. The author repository
declares NumPy 1.23.5 and `imblearn==0.0`; this current numerical condition does
not recover the historical resolved environment. These real-library controls
have not been run locally. Their hosted result is separate evidence.

The unchanged author reference functions and license are retained in
`reference/`. Controls replace Ray scheduling with a synchronous test driver;
the required hosted numerical comparison uses the actual sampler, scaler and
classifier. Production scoring still delegates to the existing pinned evaluator.
