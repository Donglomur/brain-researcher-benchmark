# NEURAL-099: regional response prediction under assumed observation

This package preserves the source-construction and import-proof cutoff for the original sequential, full-training condition of NEURAL-099. It predicts early auditory responses in processed extracellular recordings. It does not add benchmark IDs, establish physical recording continuity, or report an empirical model result.

**Private authentic preparation is now complete**, for the full selected cohort, checked by two counting implementations and an independent saved-output review. That review did not repeat count decoding. See the aggregate [preparation-status receipt](PREPARATION_STATUS.json). That later receipt updates preparation status. The additive [portable source package](portable-v1/README.md) now supplies local metadata regeneration, count preparation and paired current-trial collection interfaces. Its metadata-regeneration and counting entry points have now reproduced the original case and count commitments on the selected local runtime; see the [reconstruction-status receipt](portable-v1/RECONSTRUCTION_STATUS.json). Participant isolation and a qualified model runtime remain open. The historical source/import-proof cutoff below remains unchanged.

The original verified-physiology condition remains unresolved. This condition explicitly assumes that eligible deposited source clusters cover each selected response and permitted-history window without an unrepresented interruption that materially changes the endpoint.

## Source and target

The complete MGN component of DANDI **001421, version 0.250521.2343** contains 26 files and 5,238 click rows. Source metadata assigns 1,387 `good` or `mua` clusters to named regions in 49 nonempty file–region cells. The audit retains 666 unassigned clusters. Cluster IDs are scoped to their source file; these processed clusters are not individual neurons.

Each supported region and click supplies one prediction case: the deposited spike count in each consecutive 1-ms bin over **[0, 100) ms**, divided by the fixed regional cluster count and the nominal 0.001-second bin width. History-enabled inputs add the corresponding **[−100, 0) ms** regional rates. All intervals are half-open. Missing regions are unsupported, rather than zero responses.

At the initial source cutoff, the retained headers implied **9,867 regional trial cases and 986,700 target values**; no target values were computed during that construction. Subsequent private preparation completed that entire selected cohort under the explicit observation-support assumption, as recorded in the [preparation-status receipt](PREPARATION_STATUS.json).

The source paper, [Noncanonical Short-Latency Auditory Pathway Directly Activates Deep Cortical Layers](https://doi.org/10.1038/s41467-025-61020-9), motivates the fast time resolution. These 100-ms prediction windows and scoring rules are new benchmark choices; they do not reproduce the paper’s summed and normalized PSTH estimator.

## Original sequential, full-training evaluation design

The design below remains the original trained condition. Separately versioned zero-label, current-trial native and frozen-programme conditions do not change its training permissions or within-animal sequential state; their source is supplied separately in the [portable paired package](portable-v1/paired/README.md), while their actual execution remains unqualified.

The paper’s 26-mouse statement and the authenticated 26 MGN subject identifiers support source-declared animal grouping. Unknown aliases remain a limitation. Known cross-archive overlap is excluded by the MGN-only cohort. A subsequently established alias requires a versioned grouping review before evaluation.

Five fixed outer folds query each declared animal once. Animal identifiers are sorted by SHA-256 of the fixed namespace `NEURAL-099|condition-b|outer-v1|` followed by the identifier, then assigned round-robin. The next fold supplies selection validation and the other three supply initial training. One frozen final refit may use all four non-query folds; the reference and candidate receive the same final training data.

The submitted selection, refitting and state-update procedure is fixed before all outer folds. Predictions are locked chronologically before later histories appear. State may retain already permitted observations and prior own predictions within an animal; it must reset between animals and folds. Query responses are never feedback. No outer scores are released until every outer prediction is locked. This is sequential prediction, not a stateless or zero-shot task.

The primary metric averages squared error equally over animals, then available regions, then trials, then time bins. Secondary metrics use the same hierarchy for MAE and for MSE after averaging each five consecutive 1-ms rates into one 5-ms rate. Final results average animals directly, rather than averaging unequal fold scores.

The reference predicts a regional trajectory averaged over trials within each training animal and then equally across training animals. For a region absent from training, it uses a declared global fallback: average available regions within each training animal, then average animals equally. Fallback use is reported.

## Implemented boundaries

- `support.py` authenticates supplied metadata bytes against external pins and constructs ragged source support. It performs no file or network I/O.
- `condition.py` defines the selected protocol, fold declarations, pure event-count preparation, whitelisted observations and chronological prediction locking. It rejects known observation gaps and any history intersecting a scored response window.
- `scoring.py` validates complete predictions before inspecting gold, derives rates from private counts and computes the declared weighted metrics and reference. Its exact reference arithmetic is tested on generated examples; full-cohort runtime is unmeasured.
- `inspect_clicks.py` is the timing-inspection entrypoint preserved at the source/import-proof cutoff. It authenticates whole files before reading only trial IDs and click start/stop times, with bounded chunk and filter checks. The explicit execution flag is an accident guard, not read authorization. It had not run on authentic NWB files at that cutoff. Later private timing and count preparation are reported separately in the preparation-status receipt; the portable preparer is supplied separately, while private execution histories and prepared data are not published.
- `DECLARED_SUPPORT.json`, `COHORT_BINDING.json`, `PROTOCOL.json` and `CONTRACT.json` retain the source roster, selected design and limitations.
- `FOLD_SUPPORT.json` audits anatomical coverage without responses. Every queried region is represented in its final four-fold training partition under the frozen source-declared grouping; sparse regions remain a limitation.

The canonical observation projection is shared by future viewer and programme adapters. Graphical rendering and adapter containment are not implemented here. The separate portable package adds exact structured adapters and a trusted collector, without qualifying actual containment. Any difference between a full-training programme and a limited-demonstration viewer must be labelled as an information-budget difference. The present source seams do not measure native neural understanding or isolate a tool-use effect.

`ChronologicalQuery` is a trusted evaluator object, not a sandbox. Keep it outside participant processes. It currently accepts one animal and one source asset; multi-session animals require an authenticated chronology schedule. Process-level isolation, private-gold protection and state resets require separate runtime qualification.

## Historical validation and current remaining work

The original construction passed 49 distinct generated checks across the initial suite and subsequent targeted checks. They cover source support, half-open counts, denominators, ragged weighting, reference fallback, complete prediction admission, chronological locking and the future timing-reader boundary. A pinned metadata-only normalization recovered the complete roster. These operations opened no NWB files or neural arrays.

Run the local generated checks from this directory with:

```sh
python3 -I -S -B -m unittest discover -s . -p 'test_*.py' -v
```

Private authentic timing and count preparation have completed, including checks by two counting implementations, packet round trips and an independent saved-output review that did not repeat count decoding. The public preparation-status receipt reports that bounded result without exporting private signals or case maps. The portable public preparer and relocatable bindings have now reproduced the complete original cases and counts through authenticated local reconstruction on the selected runtime. Remaining gates include reconstruction on other machines or native stacks, qualified participant execution and isolation, verified physiological observation coverage for the original physiological target, and actual model/reference evaluation. The assumed-support condition does not close the physiological gate, and physical stimulus-onset parity remains unverified despite completed source-timing preparation. Whole-session spike sorting remains a retrospective preprocessing limitation. The public original dataset also prevents a claim of secret test data. Generated checks establish software properties; they do not establish empirical difficulty, SOTA, or submission readiness.

## Runtime initializer correction

The first admitted timing attempt stopped before opening any NWB file because the inspector assumed that h5py exposed `h5pl.set_loading_state`. The corrected entrypoint requires `HDF5_PLUGIN_PRELOAD=::` in a clean environment **before Python starts**, using the documented HDF5 initialization mechanism. It refuses preloaded h5py and unexpected runtime versions before source access.

One import-only probe succeeded with h5py 3.13.0, HDF5 1.14.6 and NumPy 2.2.6. That import-only probe proves the selected initializer can run in that environment; the probe alone does not qualify dataset reads, cache APIs or recording coverage. The later private preparation receipt is separate evidence and does not broaden this historical import-proof cutoff. See `RUNTIME_REPAIR.json` and `RUNTIME_PROBE_RESULT.json`. The original generated-validation snapshot is retained under `history/VALIDATION.pre-runtime-repair.json`; `VALIDATION.json` describes the additive repair.
