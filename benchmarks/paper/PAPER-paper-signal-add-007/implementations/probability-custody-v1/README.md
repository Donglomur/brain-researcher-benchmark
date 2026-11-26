# Original ICNet probability custody

This additive component preserves the categorical distributions that the existing
original-input runner otherwise reduces to sampled and expected counts. It does
not load a model or qualify paper reproduction or improvement. The original
seven animals, four sounds, two trials, unit columns and source-equation scorer
are unchanged. The current paper contracts and historical v1 artifacts retain
their original status.

`capture()` wraps an operator-supplied predictor and calls the existing pinned
`predictions.run`. Every original trial stream is requested once; there is no
retry or second prediction pass. Before yielding a block to the unchanged
converter, the wrapper takes an owned C-order copy and archives its original
float32/float64 values and emitted column order. It does not archive normalized
probabilities in place of the original values. The existing converter still owns
column restoration, its declared tiny row-sum normalization, expected counts and
PCG64 sampling. Full original support is required: 56 streams, 22,784 bins,
512 columns and five count classes. Blocks may have different allowed dtypes.

`verify()` reads the saved blocks and invokes the exact pinned v1 converter with
its per-animal/sound/trial seed derivation. It checks both derived count arrays
against that independent replay, along with coverage, order, original columns,
raw-file identities, the exact receipt bytes consumed, model declarations,
public-panel identity and NumPy version. It never calls the predictor. An old
count-only v1 artifact cannot pass this new custody route. Different categorical
distributions can have the same expectation and sampled outcome, so the derived
arrays alone cannot supply the required raw output record.

`verify_and_grade()` first verifies custody, binds the same public/prediction
identities through assembly, then calls the unchanged v1 grader and equations
3–5 scorer. No new metric, split, scalar superiority criterion or scientific
admission is introduced. Source identities and model hashes are operator
assertions unless independently authenticated; matching hashes are not proof of
original checkpoint competence, native alignment or protected execution.

## Operator API

Place this package beside the existing `original-inputs-v1` and
`source-equations-v1` packages. `custody.py` authenticates their exact source bytes
before loading them; SOURCE.json records those dependencies. NumPy must already
be available. Loading external predictor code and dependencies remains the trusted
operator's responsibility, with host privileges and a separately reviewed source
closure. The API is not an untrusted-code sandbox or a model acquisition route.

```python
import custody

# Authenticate these inputs and the predictor separately. No defaults infer
# historical source context, checkpoint identity or an acceptable native budget.
result = custody.capture(
    public_manifest, new_output_directory, reviewed_predictor,
    predictor_sha256=reviewed_predictor_source_sha256,
    model_binding={"model_sha256": authenticated_checkpoint_sha256,
                   "model_source_sha256": reviewed_model_source_closure_sha256},
    seed=explicit_seed,
    storage_budget_bytes=selected_finite_output_budget,
)
checked = custody.verify(public_manifest, new_output_directory / "capture.json")
report = custody.verify_and_grade(
    public_manifest, private_reference,
    new_output_directory / "capture.json", operator_workspace,
    variance_ddof=independently_selected_convention,
)
```

The output directory must be new, with an existing parent. All authentic raw and
derived outputs belong outside Git. This package does not authorize their capture.
`storage_plan()` computes a finite worst-case allowance for float64 raw values,
both derived arrays, one-bin blocks, bounded receipt rows and file/metadata
headroom. Both the declared allowance and available filesystem bytes must cover
that full plan before the first predictor invocation. Structural limits bound
all writes: at most one block per bin, exact arrays, bounded rows and fixed source
roster. This is admission against a measured free-space snapshot, not an exclusive
filesystem reservation; another process or a filesystem error can still prevent
completion. The caller may already have initialized its model before admission.

The raw probability payload alone is 13,065,256,960 bytes for all-float32 or
26,130,513,920 bytes for all-float64. Existing derived arrays add 5,879,365,632 bytes;
headers, receipts and failure custody require additional space. These are static
size calculations, not measured native compute or qualification results. Separate
candidate, baseline and information-condition executions incur their own costs.

## Complete and incomplete evidence

`STARTED.json` marks incomplete work. After admission, `RUN.json` binds the public
panel, predictor/model identities, dependencies, NumPy and sampling seed. Each
stream persists its identity before requesting blocks and its column mapping
before the first block is converted. JSONL receipts bind each saved probability
block. Failed attempts retain these records, partial probabilities and derived
arrays; `FAILURE.json` records the exception when the filesystem permits that
write. They are not cleaned up or retried automatically.

`capture.json` means all raw streams were captured; it does not certify replay.
Only successful conversion replay produces `COMPLETED.json`. Consumers must run
`verify()` on the actual artifacts instead of trusting an existing completion
file. A failed verification keeps capture evidence without a completion marker.
A hard process kill can leave only the durable partial records; missing completion
always means incomplete. This is ordinary trusted-operator custody, not protection
against hostile concurrent processes or fabricated model/source assertions.

## Generated controls and remaining science

Run `python -I -B test_custody.py NEW_GENERATED_DIRECTORY` with existing NumPy.
The test patches only in-memory time/audio geometry to two bins and 64 samples;
it keeps all seven animals, four sounds, two trials and 512 original columns.
It covers both probability dtypes, a nonidentity column permutation, original
pre-normalization bytes, exact conversion, unchanged grading, missing/reordered
streams and blocks, tampering, stale derived outputs with refreshed hashes,
preflight refusals, interrupted failures and handoff/receipt changes. Authentic
neural inputs, TensorFlow, a checkpoint and native model inference are not used.

These controls establish an executable source component only. Original context,
measurement-time mapping, mask/crop qualification, competent ICNet/LNP replay,
source companion findings, tolerance/uncertainty rules, permitted development data,
matched paper-access conditions and independent scientific evaluation remain
unresolved. No result or benchmark-readiness count is promoted.
