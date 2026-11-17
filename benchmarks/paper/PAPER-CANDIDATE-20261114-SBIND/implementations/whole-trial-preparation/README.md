# SBIND prospective whole-trial preparation

This task-local source component repairs the trial indexing boundary for existing `PAPER-CANDIDATE-20261114-SBIND`. It is not a completed paper benchmark or a historical reproduction. The registered two widefield assays and full fUS question remain unchanged. All authentic-input, numerical preprocessing, reference, model, runtime, paired-execution and submission qualifications remain false.

## Concrete behavior

`compile_protocol` authenticates two bounded JSON byte strings against independently frozen operator SHA256 values, rejects duplicate JSON keys, and admits the complete 248-trial WFCI1 and 412-trial WFCI2 census before constructing anything executable. Each census has a unique trial identity, positive original length and contiguous original source extent. No missing/invalid trial is silently dropped. Different positive trial lengths are supported.

The external protocol must give five explicit train/validation/test whole-trial partitions per assay. Every role is nonempty; every original trial occurs exactly once per fold and in exactly one test fold across the five. This is an explicitly selected prospective policy, not a recovered historical split. This code never chooses a random seed, trial assignment, fold proportion, purge, filtering boundary, animal or session split. A whole-trial fold is not proof of independent sessions/animals or sufficient filtering purge.

The output uses original census order, regardless of role-list order. Source indices are unchanged. Each trial starts a new recurrent segment; the reset mask is 0 at that trial's first retained frame and 1 elsewhere. Unequal lengths use their real boundaries, with no fixed 170-frame stride and no concatenation across trial history. This fixes the indexing/reset discrepancy observed in the current official fixed-length helper. It does not claim the historical tables used that branch.

`prepare_fold` validates both assays and all folds before one trusted loader call for the selected full assay. It returns lazy `TrialView` sequences for the three roles. Every `Frame` includes original source index, trial identity, within-trial offset, reset flag, and the exact neural/behavior payload references from the loaded row. `reset_mask()` needs no payload reads. No image values are copied, transformed, normalized or scored by this component. Payload references remain mutable; this is not process isolation, immutable storage, model execution or a protected scoring boundary.

## Input contract

The census has exactly `schema`, `task_id`, `assays`. Schema is `sbind-complete-widefield-census-v1`; task is the existing SBIND ID. Assays are ordered `WFCI1`, `WFCI2`. Each has exactly `assay_id`, `source_sha256`, `representation_sha256`, `neural_shape`, `behavior_channels`, `trials`. The field shape is `[1,128,128]`; channels are the complete externally established nonempty unique list. The component does not infer that list or assert the declaration proves completeness. Source and representation identities must be literal lower-case SHA256 strings. Trial entries have exactly `trial_id`, `source_start`, `length`; source extents begin at zero and concatenate the complete declared trials without gaps. This is the prepared full-trial representation, not an assertion that raw acquisition clocks have no gaps.

The split has exactly `schema`, `task_id`, `census_sha256`, `assays`. Schema is `sbind-prospective-whole-trial-folds-v1`. Each assay has `assay_id`, `folds`; folds are ordered 0 through 4, with exactly `fold`, `train`, `validation`, `test`. Role lists contain only complete census trial IDs. Source/census hashes must be independently frozen from authenticated originals by the owner; computing a hash from an untrusted candidate assertion would not establish scientific provenance.

Metadata operands are capped at 2 MiB each. This is a parser input cap, not a hard total memory bound. Full scientific image storage and runtime requirements are not measured or provisioned here.

## Callable use

With operator-provided authenticated metadata and loader:

```python
from trial_preparation import prepare_fold, SourceRows

views = prepare_fold(
    owner_census_bytes, owner_split_bytes,
    census_sha256=owner_expected_census_sha256,
    split_sha256=owner_expected_split_sha256,
    assay_id="WFCI1", fold=0,
    source_loader=owner_authenticated_loader,
)
for frame in views["train"]:
    # Reset the model state when frame.reset is true.
    consume(frame.neural, frame.behavior, frame.reset)
```

The loader receives the admitted immutable `Assay`. It must authenticate the actual complete prepared source and representation artifact, establish full field/channel numeric shape and type, and return `SourceRows(source_sha256, representation_sha256, (1,128,128), assay.channels, rows)`. `rows` is a random-access `Sequence`, length `assay.total_frames`; each row is `(neural_field, behavior_vector)`. The component verifies receipt equality and complete row extent, but cannot prove that an arbitrary trusted callback authenticated those bodies. There is no default loader, implicit local dataset path, pickle importer or authentic execution CLI.

Array owners may expose their existing full arrays through this row interface without a copy, then use views to fit train-only transforms and run their selected model. A faithful connection to the official NumPy/PyTorch training caller, behavioral SVD/motion construction and normalization remains to be supplied and reviewed. No numerical preprocessing helper has been silently replaced. The current official preparation source remains byte-for-byte unchanged.

Both access conditions must receive the same frozen census, split, fields, behavior visibility and reset protocol. Official implementation access remains B-only under the original task. These instructions do not establish equal budgets, no-cross-arm history, authoring isolation or runtime mounts.

## Unresolved scientific work

The source repair is useful without inventing missing inputs: bind both authentic complete trial/field/behavior censuses and their original identities, the actual causal or noncausal preparation policy, complete folds/filters/purge and train-only transform provenance. Then connect the selected model caller to these exact views and qualify it on authentic complete inputs. fUS clock format, sessions, classification windows and numerical preprocessing remain unresolved. No timestamp parser fix is included. The whole Tables2–3 comparator/ablation grid and prospective neural noninferiority/Pareto margins also remain unchosen. There is no scalar benchmark reward, reference competence claim or new task count.

## Generated checks and rights

`python3 -B test_trial_preparation.py` runs nine generated methods. The full declared 660 trial identities and all ten assay-fold combinations are exercised with lightweight sentinel rows, including unequal lengths, exact order/reset semantics, malformed/missing/duplicate support, hash/receipt errors and loader ordering. These are interface controls, not full spatial arrays or numerical/scientific/model runs. The public delivery checks additionally exercise relocation and the complete source namespace.

This new code is project-authored. No official SBIND implementation is copied or relicensed. The inspected official source has USC educational/research/nonprofit terms; data rights and noncommercial restrictions remain separate. Public source provenance and qualification limits are recorded in `PROVENANCE.json`. Read `SCOPE_CLARIFICATION.md` before using any owner view; test behavior is held target information, not participant input.

## Portable source package

Python 3.11 standard library is sufficient for this component. It has no NumPy, PyTorch, official SBIND-code or dataset dependency for generated interface checks. Authentic preparation still requires the explicitly trusted owner loader described above; there is no built-in dataset acquisition or scientific execution command.

From this directory, `python3 -B -m unittest -v test_public_delivery` runs only the two delivery checks. `python3 -B -m unittest discover -v` runs all eleven generated methods, including the nine unchanged preparation controls. The component's CI job authenticates the exact flat namespace and every member before importing tests. Its limits apply to generated source checks, not real imaging preparation or model execution.

Only project-authored source and generated fixture code are shipped. `SOURCE.json` binds every other package file. No actual census, split, field, behavior target, official source body, private execution admission or historical evidence archive is included. Obtain and independently authenticate lawful complete inputs before considering any real execution.
