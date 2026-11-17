# SBIND owner-side continuous numerical preparation

This experimental source component connects the accepted complete whole-trial
views to train-only continuous normalization and serialized participant inputs.
It does not train a model or fit SVD, and it is not a reproduction of Tables 2–3.
The unchanged registered question still requires both complete widefield assays,
all released fUS sessions and the specified reference/ablation comparisons.

The existing public [whole-trial component](../sbind-whole-trial-preparation/README.md)
supplies `trial_preparation.py` and its generated fixture. They are reused from
that adjacent package, not copied into this one. Its mandatory
[owner-only view warning](../sbind-whole-trial-preparation/SCOPE_CLARIFICATION.md)
remains valid. Nine inherited indexing methods and seven normalization methods
have generated source evidence; none is an authentic scientific run. The public
relocation controls do not repeat either numerical/indexing suite.

## Numerical policy

The selected mathematical formula comes from the official widefield
`create_train_data.prepare_data` and `prepare_behavior_data` helpers at commit
`c00e006dd298cb8c51d1543641fb3be77cc585ae`:

* Fit one training mean for each of the full 1×128×128 neural pixels.
* Fit one population standard deviation over all **raw training pixel values**,
  not the pixel-demeaned residuals. Use that same scalar on all pixels/roles.
* Fit each continuous behavior channel's training mean and population standard
  deviation. A truly zero variance receives denominator 1, for either modality.
* Apply those fixed training statistics to train, validation and test.

This is the explicit prospective policy
`sbind-train-only-continuous-normalization-v1`. Inputs are finite binary64
values; booleans, numeric strings and incomplete fields/channels are refused.
Sums and squared sums use exact rational accumulation after conversion to
binary64. Means are rounded to binary64, and population SD uses a scaled square
root. This deliberately does not promise NumPy 1.24.1 bitwise results or infer
which upstream preprocessing path produced historical paper values. Ordinary
normalization uses binary64 subtraction/division; exact-rational fallback avoids
intermediate subtraction overflow when the final result is representable.
Nonzero SD underflow and genuinely unrepresentable results are refused.

The operation is for continuous SVD/motion behavior features. It does not
normalize categorical class targets or implement the separate classification,
F1, fUS or future-prediction protocols. The source's separate `DataSplitter`
adds an epsilon and uses a different split, while `proc_neural` has additional
global/rolling normalization and filtering branches. None of those alternatives
is silently composed with this policy. A prior preprocessing leak cannot be
undone by a later train-only normalization.

## Authentic input and SVD obligations

The existing full census and split schemas are unchanged: exactly 248 WFCI1 and
412 WFCI2 whole trials, the complete spatial field and declared behavior channels,
and all five externally frozen folds per assay. All ten folds are validated
before a source loader is called. Original lengths and chronological source
order are preserved; no 170-frame stride, remainder trimming or small cohort
substitution is introduced.

An additional independently frozen JSON declaration is required:

```text
schema: sbind-owner-fold-representations-v1
task_id: PAPER-CANDIDATE-20261114-SBIND
census_sha256, split_sha256: exact admitted identities
folds: exactly ten rows in WFCI1 folds 0..4, WFCI2 folds 0..4 order
  assay_id, fold, source_sha256, representation_sha256
  fit_trial_ids: exactly that fold's training trial IDs, in source order
  fitted_artifact_sha256, method_source_sha256: non-null literal SHA256 values
```

The method and fitted artifact must cover the complete owner-provided
representation, including both behavior SVD and motion-SVD transforms and any
learned neural preprocessing. They may identify a package containing all
fold-specific transforms; the loader selects the declared fold without changing
the original complete assay identities. The hashes authenticate declaration
bytes, and the fit-ID check checks a declaration. Neither proves how the bases
were actually fitted. The owner must authenticate the originals, basis/centering
and rank specification, full channel ordering, fold-specific transforms,
filter/purge policy, and their fit provenance. All real declarations and fitted
artifacts remain unavailable here. No placeholder hashes are authentic bindings.

The retained helper loads precomputed `svd_behavior` and
`svd_behavior_motion` tables. Its source does not supply their full basis/rank,
fit implementation or authentic train-only fit receipt. This component refuses
missing declarations and does not invent those missing operations.

## Callable owner API

```python
from numerical_preparation import prepare_selected_fold

result = prepare_selected_fold(
    census_bytes, split_bytes, representations_bytes,
    census_sha256=EXPECTED_CENSUS,
    split_sha256=EXPECTED_SPLITS,
    representations_sha256=EXPECTED_REPRESENTATIONS,
    assay_id="WFCI1", fold=0,
    source_loader=authenticated_fold_loader,
    sinks={"train":training_writer,
           "validation":validation_neural_writer,
           "test":test_neural_writer},
    owner_targets_sink=private_target_writer,
)
```

This is an inert API example: the authenticated inputs, readers and writers are
not provided. The loader receives `(admitted_assay, fold_number, declaration)`
and returns the unchanged `SourceRows` type. Each row has a complete nested
`(1,128,128)` neural field and a vector of all declared continuous behavior
channels. The owner must ensure source values remain stable across fitting and
emission and that the actual authenticated bodies match those identities.

One invocation emits **one full assay/fold**, after admission of the entire
two-assay/five-fold metadata grid. Completing the prospective grid requires ten
separate complete invocations and their evidence; this source phase performed
none with real inputs. Repeated test sets are not additional benchmarks.

Each binary sink receives newline-delimited JSON. Headers bind the census,
split, representation and normalization identities, full shape/channels, role and
policy. Frame records preserve source index, trial ID, within-trial offset and
reset. Training frames include normalized behavior. Validation/test participant
frames contain normalized neural values **without behavior values**. After all
three participant streams complete, a separate owner sink receives held
validation/test behavior records. A failed participant write prevents those
held behavior values from being inspected by this function. The returned owner
result contains statistics and exact written-byte hashes/counts.

All sinks and loaders are trusted owner code. Distinct Python sink objects are
required, but their underlying files may still alias unless the owner prevents
it. A stream write receipt is not an fsync, no-clobber publication, filesystem
permission or process-isolation guarantee. Partial streams must be retained or
discarded according to the external owner's failure policy; this function
returns no success after an incomplete write. Only completed serialized
participant bytes may cross an independently enforced process/mount boundary.
Do not hand an agent the original views, loader, generator, Python owner state,
target stream or owner result. Candidate validation selection must use a
separately defined owner-scored interface; held labels are not exposed here.

## Model-caller seam

The source-defined normalization is now executable. The native caller remains
unqualified. The current official trainer passes only `y` and `x_init` to its
model; its `mask`/`z_mask` control losses, not within-sequence recurrent resets.
The inspected model initializes state when `x_init` is true, the RNN is
non-stateful or no state exists. The current trainer sets `x_init` for the first
batch, not every trial boundary. Its fixed-length dataset floors the number of
sequences and can omit the trailing frames. These are current-source findings,
not proof about the historical caller or published results.

The serialized policy therefore requires a future complete single-trial model
sequence, reset true at each trial, with no tail loss. The header records that
requirement; it does not execute it. A native owner must bind a compatible
reset-aware training/inference caller and prove complete output-to-frame joins,
including unequal trials and the final remainder. It must also bind architecture,
dtype, initialization, optimization, epoch/early-stopping, causal information and
runtime choices. The official trainer currently also refers to
`misc_torch_utils` without defining/importing it in the inspected module; any
external caller injection or repaired source must be explicit. No generic
executor or unqualified upstream call was added to hide these unresolved seams.

## Validation and limits

Use the two-directory commands below for the portable generated checks.
The seven-method numerical suite is unchanged from the accepted source; public
delivery adds dependency/import checks without repeating its arithmetic run.

The one retained seven-method run checks raw-global versus residual SD, constant
channels, representable extreme arithmetic and refusal, complete ten-fold
admission before loading, full invented 248-trial serialization with 249 unequal
frames, exact temporal/reset metadata, train-only fitting, held-label exclusion
and target-last access, short/failed writes and malformed numeric input.
The invented full-sized fields are generated in memory and are not downloaded
or retained as a dataset. The original nine indexing controls remain inherited.

No authentic scientific performance, input/export rights, hard resource limits,
authoring isolation, native compatibility, original-paper reproduction or
benchmark readiness is qualified. The original source was inspected as primary
evidence under its USC license; no upstream implementation or original data is
copied into this independently authored module.

## Portable public package

Python 3.11 standard library is sufficient for these generated checks. This
package requires the adjacent published `sbind-whole-trial-preparation` package;
`SOURCE.json` pins its complete source manifest. Do not substitute a similarly
named module from another project. Both directories must come from the selected
owned checkout. The task CI authenticates both exact ordinary file namespaces
and every member before importing any task or test code.

From the repository root, the following trusted-checkout command runs only two
public delivery methods. It admits invented complete metadata and tests shared
module/type identity after relocation to a path with spaces and an unrelated
working directory. It executes neither the seven numerical methods nor the nine
inherited indexing methods.

```sh
PYTHONPATH="components/sbind-continuous-normalization:components/sbind-whole-trial-preparation" \
  python3 -B -m unittest -v test_public_delivery
```

To run the unchanged seven generated numerical methods explicitly:

```sh
PYTHONPATH="components/sbind-continuous-normalization:components/sbind-whole-trial-preparation" \
  python3 -B -m unittest -v test_numerical_preparation
```

These commands are for a trusted source checkout, not an adversarial module
loader or a selected authentic run. The separate CI job authenticates source
before discovery and runs exactly nine methods from this new package. The
existing whole-trial package retains its independent CI and files unchanged.
There is no data download, scientific execution CLI or implicit native backend.

The Python API example above needs the same two import directories. The owner
must supply all authenticated full inputs, fitted representation provenance,
separated trusted sinks and later native/runtime isolation. Read
[NATIVE_CALLER_CLARIFICATION.md](NATIVE_CALLER_CLARIFICATION.md) before connecting
upstream prediction: its target-shape dependency cannot be satisfied by exposing
held labels. No actual census, folds, original source body, behavior targets,
private evidence graph or runtime admission is distributed here.
