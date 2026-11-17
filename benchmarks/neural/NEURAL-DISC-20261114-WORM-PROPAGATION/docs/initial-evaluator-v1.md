# Conditional worm-response evaluator: initial source implementation

This package implements a complete numerical evaluation path for the existing
NEURAL-DISC-20261114-WORM-PROPAGATION task, from a verified trace packet through
training-only references, development selection, protected exports and held-worm
scores. It does **not** establish a complete authentic benchmark. Scientific
qualification remains **unknown** and submission readiness remains false. No
NWB/image payload, authentic model run or scientific result is included.

The input source contains its measured response after stimulation. The question
is therefore retrospective conditional reconstruction of a receiver response,
not prediction before stimulation and not recovery of direct synaptic edges.

## Source-grounded construction findings

The [primary paper](https://www.nature.com/articles/s41586-023-06683-4) describes
optogenetic perturbation and calcium recording. Its published processing uses a
30-second prestimulus fluorescence baseline, interpolation and response-selected
kernel fitting. Those choices cannot be imported into this task's 10-second
receiver context or its all-response population. This implementation does not
use author atlas kernels, replace original samples with smoothed traces or select
responsive neurons.

The immutable [DANDI release](https://dandiarchive.org/dandiset/001075/0.240930.1859)
contains 223 assets: 113 imaging and 110 segmentation files. The task-local
`release_inventory.json` records their complete public metadata roster, observed
listing hash and sizes. Segmentation assets total 1,700,529,616 bytes; no payload
was acquired. `sub-20`, `sub-23` and `sub-33` have imaging but no segmentation
partner. The total release size remains 4,074,234,123,623 bytes. These are asset
and metadata-subject counts, not independently authenticated animal counts.

The official conversion source was inspected at commit
`3544c9bb59f90d5630fa1871850d990db9cafc18`; author `pumpprobe` source was inspected at
`1dbc5e0a2b609d54bc9b1c90c73d4e3bf183d3c7`. Exact read hashes, git-blob checks and
source line references are in `provenance.json`. Consequential conversion details:

- Fluorescence volume timestamps are means of original frame timestamps. A
  uniform 0.5-second grid would discard the source clock.
- `Base{Channel}Signal` restores the original missingness mask and is distinct
  from `Interpolated{Channel}Signal`; never-interpolated data uses
  `{Channel}Signal`. The source declares units `n.a.`, not an established dF/F
  normalization. This package makes no implicit unit conversion.
- Subject IDs can default to acquisition dates and genotype is hardcoded `WT`.
  Neither field proves animal identity or full condition membership.
- Stimulation duration is hardcoded 0.5 seconds, with a mutant-duration TODO;
  power is hardcoded. Nonpositive target ROI IDs become missing while
  segmentation ROI indexing starts at zero. This package does not repair those
  values by assumption.

DANDI CC BY 4.0, conversion BSD-3-Clause and `pumpprobe` GPLv3 licenses were
inspected. Original OSF version/rights and the complete dependency/component
rights chain remain unresolved. No upstream implementation is copied here.

## Executable interface

Use the existing Python 3 runtime with NumPy; no installation is required by the
package. From this implementation directory:

```sh
python3 -m unittest discover -s tests -v
python3 worm_evaluator.py export /path/to/verified-custody.json /new/role-packets
python3 worm_evaluator.py score /path/to/verified-custody.json /path/to/predictions.json /path/to/score.json
```

The test fixture is an executable, small interface example containing **generated
engineering data only**. Its all-zero asset hashes and asserted identities are
test placeholders and must never be used as authentic evidence.

The custody JSON requires `task_id`, `schema_version: 1`,
`release_id: "DANDI:001075/0.240930.1859"`, `units`, `horizon_s: 30`,
`max_interpolation_gap_s`, pinned `inventory_sha256`, `identity_audit_sha256` and
`mask_policy_sha256`, `identity_authenticated: true`,
`mask_policy: "acquisition_missingness_only"`, `expected_case_ids`, and `cases`.
The attestations are mechanically checked assertions; they cannot authenticate
themselves. Authentic extraction may proceed only after independent evidence
establishes the immutable roster and joins.

Each case contains unique `case_id`, `worm_id`, `acquisition_id`, `trial_id`,
`source_id`, `receiver_id`, `condition`, one `role` (`train`, `development`,
`held`), `quality_flags`, `stimulus_parameters`,
`stimulus_onset_acquisition_s`, and `provenance` with `asset_id`, `asset_sha256`,
`source_index`, `receiver_index`, `stimulus_index`. The three traces `source`,
`receiver_pre`, `target` each have `times_s` and `values`. Times are finite,
strictly increasing seconds relative to the stimulus; values are finite numbers
or JSON null for acquisition missingness. Every measured pair/trial, including
failure/weak/nonresponse cases, remains in the fixed roster. Unknown source or
animal identities prevent admission; they must remain in the external source
eligibility/coverage ledger rather than silently disappearing from that roster.

The prospective stimulus schema permits exactly positive numeric `duration_s`
and `power_mw`; nested or additional metadata is rejected to prevent carrying
receiver-derived information into public packets. These values must be checked
against original acquisition records, not trusted converter constants. If other
scientifically necessary stimulus parameters are found, extend and review the
allowlist before authentic extraction; this version does not silently discard
them.

Source timestamps must lie in [-10,30]; receiver context lies in [-10,0), and
targets in [0,30]. The half-open receiver endpoint is a prospective convention
that prevents exposing the scored zero-time sample. Preserve every original
sample in these windows; validation cannot prove an upstream extractor did so.
Missing tails are reported as `target_tail_unobserved_s`; this version does not
truncate the horizon to obtain an easier score. A common shorter horizon would
require a separately accepted revision based on development metadata.

Predictions are `{"units": "same units", "cases": [...]}`, each containing
`case_id`, `times_s`, `values`. Every held case and original target timestamp
must be present exactly once. Predictions must be finite even where a protected
target is missing. Extra/duplicate cases, wrong grids or units, and missing
predictions fail. Submission execution logs, inference recipe/access condition,
training exposure and frozen/adaptive assistance records remain an outer
assessment integration gate; this scorer does not certify them.

`export` writes physical `train.json`, `development.json` and `held.json` files.
Only the training export contains response values. A strict allowlist omits
target masks, quality flags, arbitrary evaluator fields and target-derived
normalizers from participant packets. Context and actual requested time grids
are retained. Protected custody data is placed under `evaluator-only/` with
directory mode 0700/file mode 0600. Distribute only the appropriate role files;
filesystem modes are not an isolated execution sandbox. Evaluator output contains
protected metrics and must not be routed back into frozen held inference.

## Explicit prospective numerical recipe

These choices are implemented and tested, but require root scientific acceptance
before authentic assessment; they are not claims about historical paper policy.

1. Pair means use only training animals within condition/source/receiver. For
   each requested timestamp, linearly interpolate between adjacent observed
   original training samples, never across a null, outside support or beyond the
   explicitly supplied interpolation gap. Average trials within training worm,
   then average worms. Unseen/unsupported pairs retain null comparator results.
2. Persistence is the mean of all valid receiver prestimulus samples. Training
   pair variance is the population second central moment over training target
   samples, with each training worm equally weighted. No held response changes
   the mean or variance; zero/missing training variance produces null normalized
   results without epsilon or a target-derived replacement.
3. The linear convolution predicts receiver prestimulus mean plus a causal
   convolution of the source's prestimulus-centered calcium. Trapezoid weights
   on lag grid [0,1,2,4] seconds define integration. Ridge candidates are
   [0.01,0.1,1]. The objective gives each training worm equal total squared-error
   weight and adds alpha times squared kernel coefficients, with no intercept.
   Pair/condition models are fit by augmented least squares. Separate development
   worms select alpha by hierarchical MSE; a development case with observed
   targets but incomplete kernel support makes that candidate unsupported.
   Development data is never refit into training. These are useful train-only
   linear references, not reproductions of the author's exponential kernels.
4. MSE first averages valid original samples per case, then trials per
   condition/source/receiver pair, then pairs per authenticated worm. Final paired
   difference is model MSE minus pair-mean MSE; negative favors the submitted
   prediction. Equal-worm means avoid pair/trial pseudoreplication. Report raw and
   training-variance-normalized model, pair-mean and paired errors. A comparator
   missing any observed target sample is unsupported; no favorable intersection
   mask or fallback is substituted.
5. Pearson correlation is computed on observed target samples, with explicit
   zero-target/zero-prediction-variance outcomes. Signed response-area error is
   predicted minus observed trapezoidal area; absolute area error is its absolute
   value. Only adjacent original valid samples within the declared gap contribute.
   Integrated duration is reported; no area is manufactured across a missing
   sample, and partial area is not described as a complete 30-second area.
6. Whole-worm paired percentile bootstrap uses 2,000 draws, seed 0 and 2.5/97.5
   percentiles. Fewer than two supported animals gives no interval. Any unsupported
   held animal suppresses the complete-roster primary mean and interval, including
   the normalized interval. Per-case/per-worm rows remain visible. These engineering
   intervals do not establish population validity for a small authentic cohort.

The callable API allows explicit alternative lag/candidate/seed/draw arguments;
those settings are reported in scores. Such changes are prospective protocol
changes that must be frozen before authentic evaluation.

`source_reassignment` creates a control copy by reassigning **whole** source
traces within animal, condition, source identity, stimulus parameters and exact
source timestamp grid. All receivers for one stimulation receive the same
reassigned trace. Missingness and within-trace temporal structure are unchanged;
unmatched singleton groups remain reported. Its audit log supersedes the
original source-trace association in that control copy. Pair mean supplies a
stimulus/identity-only reference and persistence supplies a receiver-history-only
reference. Authentic identity permutation, synchronization shifts, artifact,
adjacent-stimulation and complete failure controls remain required; no completed
control campaign is claimed.

## Requirements and held gates

| Task requirement | Implemented source behavior | Remaining evidence |
|---|---|---|
| Complete release and measured-pair scope | Immutable asset metadata roster; exact packet/prediction roster checks; all flags retained | Three missing segmentation partners; OSF mutants/spontaneous scope; complete original trace/pair extraction |
| Authenticated held worms | One worm per role; acquisition aliases cannot cross worms | Independent biological identities, not date/subject assumptions |
| Original signals, timestamps, missingness | Exact time grids; null support; no silent gap filling; custody export | Authentic converter/source alignment and raw versus interpolated signal selection |
| Training-only references and normalization | Pair mean, persistence, regularized convolution; separate development selection | Authentic full-scope baseline qualification and recipe acceptance |
| MSE, correlation, area, paired uncertainty | Numeric case/pair/worm computations, normalized paired metrics, coverage and intervals | Authentic reference tolerances and population-inference adequacy |
| Protected same-packet access conditions | Role files and target-free held/development allowlists | Execution isolation, exposure audit, assistance logs and direct/numerical/specialist parity |
| Negative controls | Whole-source reassignment and two ablated references | Full authentic control suite and artifact explanations |

No new benchmark ID, canonical task edit, historical rewrite or scientific count
increase is created by this implementation. The package is suitable for source
review and generated engineering checks while the listed gates remain held.
