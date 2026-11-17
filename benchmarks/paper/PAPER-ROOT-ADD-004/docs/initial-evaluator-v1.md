# Initial respiration–retrieval evaluator

This package computes participant-level retrieval decoding, respiration at cue-locked confidence maxima, and exhalation-aligned confidence–alpha/beta coupling from normalized EEG/respiration epochs. It is a **complete prospective analysis recipe**, not an author-code reproduction, frozen benchmark reward, or scientifically qualified result. The immutable task remains `PAPER-ROOT-ADD-004`.

## Source identity and decisions

The [task contract](../task.json) has SHA-256 `747c7a1b8d5a31d116bc510bfe68d987ef5afb4c3a139b297070390c9c2640d9`. Its historical LMU code archive is `22f245506d4c8a87887e1bd6cfbb47c133223fa5c2989963c27449bc0fcdcd1c`; no archive or empirical data was downloaded for this implementation.

Primary sources are the [published article](https://pmc.ncbi.nlm.nih.gov/articles/PMC12828881/), [LMU release](https://data.ub.uni-muenchen.de/596/), and newly identified [official GitHub snapshot](https://github.com/EstebanBT/Bullon-Tarraso-2025/tree/b3ecba26b8820a3837f50e67fe4ccde7899dbc32). GitHub commit `b3ecba26b8820a3837f50e67fe4ccde7899dbc32` was resolved independently with `git ls-remote`. Its equivalence to the historical LMU archive is **not established**. The LMU release predates the final article.

| Requirement | Implementation and provenance |
|---|---|
| Participant population | The 18 IDs in pinned `figure_3b.m:7`; `evaluate` requires exactly this roster, with all object/scene × pre/post cells. |
| Memory endpoint | Pooled remembered/hit ratio from `figure_3b.m:55–56`; four cell ratios and their equal-weight mean are diagnostics. Recognition misses remain in old, nonremembered neural trials (`figure_3b.m:43–52`). |
| Event alignment | Last detected trough strictly inside `0 < t < 3`, from `+util/splitTrials_breathFeat.m:125–164`. An explicit marker must join each exhalation epoch to that event. |
| Decoding | Object versus scene localizer training; retrieval category comes from learning session. AUC uses half credit for tied scores. Training/test time generalization and remembered-minus-not comparison follow article Methods and `figure_3a.m`. |
| Confidence | **Manuscript policy:** absolute value after averaging signed decisions over localizer 0.15–1.5 s. **Known disagreement:** legacy generator flips scene signs, averages indices `72:end-80` (approximately 0.155–1.1 s), and does not take the modulus. No equivalence is claimed. |
| Respiration coupling | Cue-locked maximum search is 0–1.5 s (`figure_3b.m:35–39`), ties select the earliest sample; resultant length is correlated with pooled memory. |
| Power coupling | Five-cycle Hann power at 8–20 Hz; source Figure 3c policy normalizes each outcome group by pooled trials × exhalation baseline −1–0 s, per channel/frequency. This differs from the article's cue-baseline description. Spearman is across trials at each channel/time, then a five-bin mean. |

`provenance.json` records source-view hashes, inspection limits, and source-specific locations. These are clean implementations of mathematical operations; no author source text/code is vendored. LMU's CC BY-NC-SA 4.0 terms remain applicable to its materials. The newly found GitHub snapshot has unresolved reuse terms; the archive license is not silently assigned to it.

## Frozen prospective choices

This recipe uses 50 ms evaluation grids; it does not recreate the source's full 200 Hz decoding grid. Each training time independently learns localizer-only channel z-scores, PCA retaining at least 95% variance, and equal-prior LDA with a fixed ridge equal to 0.1 times mean pooled variance. Retrieval values and outcomes cannot affect these fitted transforms. This differs from source preprocessing details and is an explicitly prospective protection against test-data fitting.

Inputs must already have declared preprocessing. This package does not claim to implement native filtering, CAR, channel interpolation, artifact rejection, BreathMetrics event detection, or double-interpolated respiratory phase. A 200 ms mean uses offsets −20 through +19 samples with truncated endpoints. Hann kernels have the nearest odd sample length to five cycles (exact ties choose the longer kernel), a symmetric taper, and power divided by taper energy; no additional demeaning occurs. These rounding and normalization choices need FieldTrip parity assessment. Undefined correlations/AUC and zero-hit diagnostic cell accuracies are `null` in JSON, and propagate without dropping participants. Only zero pooled recognition hits prevent the memory endpoint. There are no p-values, learned thresholds, or success labels.

## Input and execution

Use Python 3 with existing NumPy/SciPy; validation used Python 3.12.8, NumPy 2.4.6, SciPy 1.17.1. No installation is required by the package.

```sh
python evaluator.py normalized_epochs.json analysis.json
python -m unittest discover -s tests -v
```

The JSON root contains `schema: "respiration-epochs-v1"`, `expected_participant_ids`, `provenance`, and `participants`. `provenance` must declare `data_kind` (`authentic_preprocessed_epochs` or `generated_engineering_control`), `sample_rate_hz: 200`, and nonempty descriptions of `epoch_preprocessing`, `respiration_phase_convention`, `trial_label_source`, and `cohort_source`. Descriptions are provenance declarations, not evidence of authenticity.

Each participant contains:

| Field | Shape or meaning |
|---|---|
| `participant_id`, `channels` | Exact source ID; ordered unique EEG channel names shared across all participants. |
| `localizer_times` | Uniform 200 Hz seconds relative to image onset, covering −0.2–3. |
| `retrieval_times` | Uniform 200 Hz seconds relative to cue, covering −0.2–3 (longer allowed). |
| `exhalation_times` | Uniform 200 Hz seconds relative to the selected trough, covering −5–5. |
| `localizer` | Trial records: unique `trial_id`, `session` and `category` (`object`/`scene`), `eeg` as channel × localizer-time arrays. Both sessions required. |
| `retrieval` | Trial records: unique `trial_id`, `session`, `test` (`pre`/`post`), booleans `is_old`, `recognized`, `remembered`, cue `eeg`, and `respiration_phase_radians` on the cue axis. |
| Retrieval event fields | Sorted unique `exhalation_trough_seconds` in cue time. For eligible old trials: `exhalation_eeg` as channel × exhalation-time and `exhalation_epoch_trough_seconds` exactly matching the last strictly interior candidate. |

All trial IDs must be unique across both tasks within each participant; normalizers should use qualified native keys containing session, block and original trial identity. Arrays live in the same record as labels and phase, preventing positional joins across separately ordered files. Records are sorted by ID before analysis. Foils and trials without an eligible trough remain in the admission audit and behavioral census. Remembered items must be true recognition hits. Missing cells, invalid booleans, nonfinite values, off-grid events, partial epochs, channel changes, duplicate IDs, and cohort omissions fail explicitly.

The output includes all participant summaries, per-trial event admission, peak phase/tie counts, time-generalization AUC matrices, unsmoothed/smoothed coupling, equal-participant group summaries, input hash, dependency versions, elapsed time, and preserved holds. `analyze_participant` supports engineering controls; it does not assert a complete cohort. The CLI requires all source IDs, but that alone cannot establish a complete authentic trial/channel population.

## Validation and remaining gates

The tests include independent pairwise AUC and one-feature LDA oracles, a scalar Fourier calculation, signed-before-modulus confidence, rank/circular controls, retrieval-contamination checks, trial reorder invariance, exact event boundaries and last-event selection, pooled denominator checks, duplicate/join/roster/channel failures, a full generated participant pipeline, and all 18 source IDs with generated arrays. Generated controls establish engineering behavior only.

Still unresolved: native MAT field extraction and complete trial/channel manifests; original exclusions and minimum-count rules; source/archive/article reconciliation; preprocessing/dependency parity; authentic result agreement and tolerances; independent protected references; timing and eye/muscle controls; participant-held-out improvement assessment; rights/exposure; native resources. Auxiliary classifier/TFR files remain optional reference aids and cannot replace recomputation. Public source results are not pass thresholds, and observational associations do not establish a causal breathing effect.
