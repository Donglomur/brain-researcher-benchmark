# DREDge human LFP construction package

This package adds an executable raw-segment loader, independent rigid registration control, shared voltage interpolation, and a prospective paired consistency/fidelity evaluator for `PAPER-paper-method-add-003`. It does **not** establish human motion accuracy, reproduce the paper figures, run native DREDge, or qualify a complete benchmark. Scientific readiness remains unknown. The canonical task and historical evidence are unchanged.

## Implemented computation

`implementations/initial-evaluator-v1/evaluator.py` reads a content-pinned raw `Pt01/02/03.imec0.lf.bin`, paired SpikeGLX metadata, and an operator-verified raw-channel MATLAB map. It validates complete int16 frames, LF-only channel layout, one-based channel IDs, connected contacts, selected spatial column, sampling rate, half-open sample interval, and supplied content SHA256 values. Signal units remain ADC counts; no voltage-gain claim is made. Saved `DREDgeAligned` maps cannot be assumed raw-compatible: their raw-index identity, depth units, x column and ordering require independent verification before authentic use.

The independent rigid comparator estimates lag by centered normalized overlap correlation on reserved fit channels, builds a connected pairwise displacement graph, and fits a sparse Huber-weighted least-squares solution. It uses a zero-mean displacement gauge and rejects disconnected/constant unsupported observations. It is a transparent additional comparator, **not** a reimplementation of DREDge's online chunk solver, temporal prior or source-default algorithm. All shift, correlation, temporal-neighborhood and robust-loss settings are explicit protocol choices.

Native `default_dredge` and `alternate` displacement results must come from the same pinned recording/segment, reserved fit channels, exact time axis and depth grid. The CLI verifies array and declared provenance consistency, but does not prove that these estimates were produced by the claimed executable. Native execution receipts and exact parameter equivalence are still an admission gate. Names identify proposed comparison arms, not verified default execution.

Every arm—no correction, fixed offset, independent rigid reference, default DREDge, and alternate—uses the same linear interpolation and identical evaluation-channel/time support. Displacement follows the pinned source's coordinate convention: `z_corrected = z_observed - d(t,z_observed)`. The implementation inverts this map by interpolating raw voltage from corrected source coordinates onto target depths; for rigid motion this reduces to sampling raw voltage at `z_target + d(t)`. Folded maps are rejected. No time or spatial extrapolation is scored.

Fit and evaluation channels are disjoint. Inference may use fit-channel voltage from the evaluation segment with settings frozen elsewhere; this is an unsupervised inference protocol, not evidence of protected model generalization. Every method is evaluated on all segment times and the contiguous depth intersection valid for **all** methods. Coverage is reported. Large shifts that leave insufficient common support produce an error, not a favorable small-subset score. A future frozen maximum-displacement margin should prevent candidate-dependent support changes between separate evaluations.

## Prospective metrics and scientific limits

The canonical task records no exact score/estimand or tolerance. This package therefore proposes a panel and emits no pass/fail reward:

- Mean adjacent-time spatial-profile Pearson correlation, with defined and total pair counts; undefined constant profiles stay null.
- Paired consistency gain against no correction, on identical support; this is null unless every adjacent pair is defined in both arms. Conditional diagnostic means retain separate defined-pair counts.
- Signal-energy, temporal first-difference-energy, and spatial first-difference-energy ratios relative to raw voltage.
- Same-coordinate raw/corrected waveform correlation and explicit retained sample/channel counts.

These are diagnostics. A time-averaged signal can achieve perfect consistency while deleting temporal variation; the fidelity panel exposes that failure. Real motion correction can also change derivative energy, so no invented universal fidelity threshold is imposed. Constant or vanishing denominators remain null. Temporal first differences require regular sampling; native displacement times must match the raw sample axis exactly in the CLI. Any resampling is an upstream, explicitly validated operation.

The cohort summary requires Pt01, Pt02 and Pt03, rejects duplicate segment identities, averages segment effects within each patient and then weights patients equally. It reports patient effects; three patients do not support a claimed precise population improvement estimate. A partial cohort cannot become the complete task by changing a label. Separate reservation intervals, inclusion criteria and figure-specific native metrics still require a scientific freeze.

## Interfaces

Python dependencies: NumPy and SciPy. Verified existing interpreter: `/opt/homebrew/opt/python@3.11/bin/python3.11`; no dependency installation was performed. Tests generate bounded signals and small temporary raw/MAT/NPZ files, never public recordings.

```sh
/opt/homebrew/opt/python@3.11/bin/python3.11 -m unittest discover -s benchmarks/paper/PAPER-paper-method-add-003/implementations/initial-evaluator-v1/tests -v
/opt/homebrew/opt/python@3.11/bin/python3.11 benchmarks/paper/PAPER-paper-method-add-003/implementations/initial-evaluator-v1/evaluator.py protocol.json results.json
```

The protocol is JSON with `task_id`, `source_commit`, `metric_status: "prospective_unqualified"`, `fixed_offset_um`, `rigid_settings` (`max_shift_bins`, `min_correlation`, `max_time_separation`, `huber_delta_um`, `iterations`), and `segments`. Each segment has:

- `patient`, unique `segment_id`, `role` (`development` or `evaluation`), and integer `start_sample`/`stop_sample`.
- Paths relative to the protocol: `binary`, `meta`, `channel_map`; corresponding `recording_sha256`, `meta_sha256`, `map_sha256`; `column_x` and zero-based `fit_channels`/`evaluation_channels` in the selected, depth-sorted column.
- `estimates.default_dredge` and `.alternate`, each with `path`, `sha256`, `recording_sha256`, `start_sample`, `stop_sample`, `source_commit`, nonempty declared `settings` (completeness is an external native-execution gate), and the same `fit_channels`.
- Each estimate NPZ contains `times_s`, `depths_um`, and finite `displacement_um` of shape time or time-by-all-selected-depths, defined at observed/raw depths. Pickled arrays are prohibited.

All reserved intervals are checked for overlaps by recording identity before any raw input is opened. Development segments are reserved but not used to tune settings automatically. Input provenance, settings, units and split design need external operator validation; accepting a declaration is not scientific authentication. `tests/test_evaluator.py` constructs a complete generated protocol and shows the executable format without supplying synthetic files as purported empirical inputs.

The optional `preprocess` API supplies a prospective explicit low-pass/integer-decimation helper, segment by segment, with no historical-default claim. The CLI deliberately scores the raw sample grid and does not invoke this helper. It does not implement the paper's unresolved preprocessing, antialias edge-guard or native kriging workflow. The LFP notebook contains approximately 12.2 MB of embedded material and was not downloaded; exact notebook preprocessing remains unverified.

## Source audit and preserved gates

Pinned source: `evarol/dredge` commit `ed236113a0b6c29b376065440174da6341a1d875`. `source-provenance.json` records primary URLs and local inspected-content hashes. `register_online_lfp` defaults include rigid registration, 10 s chunks, maximum displacement 500 µm, minimum correlation 0.8, Gaussian window step 800 µm/scale 850 µm and `soft=False`; input preprocessing belongs to the caller. Native signal interpolation defaults to kriging with removal of border channels, which differs from this prospective shared linear panel. These inspected defaults do not establish a validated human run.

The independent audit recovered Dryad version 224794 page 2: the canonical saved inventory only includes page 1 (20 of 25 files), omitting Pt03 raw LFP and metadata. Newly recovered source-reported metadata appears in `source-provenance.json`; no canonical inventory was rewritten and no payload hash was verified. Dryad now explicitly labels its digest algorithm SHA256, but source-reported hashes remain distinct from locally acquired bytes. Attempts to retrieve only small LFP metadata/README files returned HTTP 401; current access qualification remains open.

The source MIT license is preserved in `UPSTREAM-LICENSE.txt`. Code, data and other dependency rights remain separate. No raw recording, archive, model, protected reference or native campaign was downloaded/run. Tests establish engineering properties only. Still open: authentic geometry and preprocessing; full-population selection; native default/alternate execution; exact paper figure metrics and tolerances; external displacement truth; protected evaluation and exposure; data/dependency rights; realistic runtime/memory; independent biological fidelity and scientific qualification.
