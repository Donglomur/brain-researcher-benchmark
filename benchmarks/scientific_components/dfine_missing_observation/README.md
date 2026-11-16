# DFINE missing-observation numeric component

This portable source component belongs to existing `PAPER-CANDIDATE-20261114-DFINE`. It implements prediction admission, paper-defined block-mask checks and behavior-correlation tables. It is not an original-data run, a qualified benchmark, an inference executor or a new task registration.

## Scientific definition

The [primary paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC11735406/) defines observed ratio rho, exact missing counts within each100-step block, inference at every test timepoint, and fivefold evaluation. Its public grid-reaching experiment has seven sessions from one animal and four cursor position/velocity variables. Figure7e compares DFINE filtering/smoothing; Extended Data6e–f adds LDM and SAE zero/neighbor-average smoothing at observed ratios0.3/0.6, with full-observation comparisons. Training statistics come from TRAIN.

The [pinned official function](https://github.com/ShanechiLab/torchDFINE/blob/37d25e332753eaba49f42e91766d0db8e186aefe/time_series_utils.py#L91) computes Pearson correlation per dimension, casts to float32, converts NaN to zero, and averages. This component preserves the formula and zero contribution, reports constant dimensions, and uses scaled float64 arithmetic; SciPy/Torch bitwise parity is untested. It scores every held timepoint, including missing-neural positions. Curves equally weight35 session-folds. Replicate averaging is an explicit component convention, pending historical RNG reconciliation; folds are not independent animals.

## Concrete interface

`grade(profile, candidate_records, reference_records, target_loader)` validates the complete public profile and BOTH complete prediction sets before calling the private target loader once. No published table scalar can substitute for predictions. This numeric interface does not prove that submitted predictions were produced by executable inference, obeyed filtering boundaries, or avoided hardcoding.

The owner controls the immutable profile and its SHA-256 outside the candidate context. The profile names seven distinct sessions, five disjoint equal-sized test folds per session, original ordered sample identities, four fixed dimensions, the full ratio/replicate roster and exact binary masks. It requires observed20%,30%,60%,100% endpoints/comparisons, but does not invent the intervening original curve grid. Mask hashes and ordered-sample hashes bind every prediction matrix to that public support. Missing, extra or duplicate cells, boolean/nonfinite numbers and wrong shapes are rejected. Targets must have all35 matching session-fold supports and the same original sample order.

For every supplied ratio, both DFINE inference profiles are required. LDM and both SAE smoothing comparators are required at30%,60%,100%. Output contains complete per-dimension/cell/curve results and candidate-reference deltas. There is no arbitrary pooling across methods or ratios, pass threshold, confidence interval, historical percentage-degradation estimate or prospective integrated-loss scalar.

Run the inert numerical component only with owner-prepared inputs:

```text
python3 -I -S -B scorer.py --profile OWNER_PROFILE.json --profile-sha256 OWNER_HASH --candidate PREDICTIONS.json --reference FIXED_REFERENCE.json --private-targets PRIVATE_TARGETS.json --output FRESH_OWNER_SCORES.json
```

The64MiB per-file bound is a component admission limit, not a measured authentic-data resource requirement. All input JSON is parsed in memory. A future authentic preparation must measure complete support sizes and select suitable finite resource limits; this source phase launches no such preparation. Keep scores private until the selected feedback policy allows release.

## Exact remaining work

Original seven-session filenames, the full original ratio grid, masks/RNG realization count and final source caller still need an authenticated input binding. The component anchors each100-step block at the first declared held-fold sample. Ordered sample IDs alone do not establish the original recording/test-fold block alignment; that historical alignment remains unverified. The inspected primary text specifies complete100-step blocks but not an incomplete trailing block: this component refuses such a tail, never silently trims it. That refusal can prevent authentic use and needs source-supported resolution. The four-ratio invented fixture is not the original grid.

The paper's January2025 correction was identified but its content was not retrieved; historical correction scope remains unverified. Current pinned tutorial code is not proven to be the original Figure7/ExtendedData6 analysis. Top30-neuron selection, causal30ms smoothing/downsampling, complete trial/time support, TRAIN-only normalization/MLP fitting, independent fixed references and candidate execution remain to be bound. These are claim-specific scientific dependencies, not a requirement to reproduce unrelated paper experiments or an obsolete environment. No request-only cohort, model fitting, empirical target or native Torch/SciPy run was used here.

## Portable use and generated verification

Python 3.11 or later and its standard library are sufficient for this numeric
component. Copy the whole package; no private checkout or installed native model
is required. `SPEC.json` defines every input record and the unresolved original
support. The embedded `contract_sha256` is the fixed accepted definition marker,
not a file to download or proof that an input preparation is valid.

Run `python3 -I -S -B test_portability.py` for package integrity and real relocated
CLI controls. Run `python3 -I -S -B test_scorer.py -v` for the generated numerical
suite. These create invented complete-support inputs only. No scientific data,
historical mask realization, fitted model or empirical result is bundled.

This is an independently authored mathematical implementation under the bundled
MIT license. Official DFINE code is linked for attribution, never bundled or
imported. `PROVENANCE.json` records exact accepted implementation identities.
`SOURCE_MANIFEST.json` inventories every other package file, excluding itself.
Keep owner profiles, references, targets and detailed scores outside the candidate
context; the CLI itself is not an isolation or feedback-release service.
