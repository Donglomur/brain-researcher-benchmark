# PAPER-FIND-ADD-009 initial evaluator v1

This is a completed feature-level scorer and declared-cohort auditor for offline neural-to-voice comparisons. It computes the paper's acoustic endpoint family and listener-aggregation structure. It does not implement offline neural training, pretrained inference, waveform extraction, MCD, acquisition, real-time operation or authentic historical grading. Scientific and submission qualification remain unknown. The canonical task and historical evidence are unchanged.

## Evidence and prospective decisions

The [primary manuscript, Methods: Evaluation of synthesized speech](https://pmc.ncbi.nlm.nih.gov/articles/PMC12369848/) describes independently removing inter-word silence, DTW-aligning target and synthesized 40-band Mel dB spectra, and averaging within-band Pearson correlations. The audio setup is 16 kHz with 50 ms Hann windows. It says 10 ms overlap; this package requires the caller to declare either the literal 40 ms hop or an explicitly prospective 10 ms hop. It never silently interprets overlap as hop. A target waveform represents synthetic intended speech, not recorded ground-truth healthy T15 speech.

The manuscript does not freeze the inspected frontend's Mel filter construction, padding/centering, dB reference, silence detector, DTW cost/ties/constraints, or undefined-band policy. Therefore v1 accepts already extracted matrices and masks and defines the remaining computation prospectively. The operator must freeze and retain frontend implementation and calibration evidence under the profile identifiers. Correlations are not bitwise historical reproductions, causal or latency metrics, or intelligibility measures.

The [pinned official training session file](https://github.com/Neuroprosthetics-Lab/brain-to-voice-2025/blob/cff4875decd35ff0f98a944035377a25b43ba79c/configs/training_data_args.yaml) lists 36 sessions through day193 and holds day195 out. Day193 and day195 share model session-layer 20; this is not the biological session identity. The [training configuration](https://github.com/Neuroprosthetics-Lab/brain-to-voice-2025/blob/cff4875decd35ff0f98a944035377a25b43ba79c/configs/config.yaml) declares 8,184 trials, 50 validation samples from 5770:8184 and an unfrozen `None` seed. V1 requires explicit trial memberships; it cannot reconstruct historical validation selection. The original fixed-day165 transfer experiment is distinct from this release's day195 holdout.

## Acoustic interface

`evaluator.py acoustic` takes three separate UTF-8 JSON files. Duplicate JSON keys and nonfinite JSON constants are rejected. The code module also exposes `validate_manifest`, `score_trial` and `evaluate_acoustic`.

The plan is an object with:

- `schema_version: 1`, `task_id: "PAPER-FIND-ADD-009"`, `data_release: "441124"` and `official_code_revision: "cff4875decd35ff0f98a944035377a25b43ba79c"`.
- `mode`: `offline_retrained` or `pretrained_inference`. Both require a training/selection provenance ledger; pretrained weights with unknown training exposure cannot pass the holdout audit.
- `split_policy`: `author_day195` requires every one of the 36 listed source sessions in training/validation and only day195 in test. This validates the session roster, not authentic trial counts. `prospective_session_holdout` allows another explicitly declared roster and still prohibits any test session in fitting or selection. The latter is a new assessment policy, not the original control experiment's ten-fold CV.
- `sentence_policy`: `disjoint` prohibits test prompt IDs in fitting/selection; `overlap_declared` records deliberate prompt exposure and does not establish vocabulary generalization.
- `trials`: complete declared rows with `trial_id`, `original_trial_id`, `participant_id: "T15"`, `session_id`, `sentence_id` and `partition` (`train`, `validation`, `test`). Physical trial identity must be preserved across augmentation/window copies. An original trial cannot cross partitions and a physical test trial cannot appear twice. Session and sentence IDs must come from the retained provenance ledger, not be invented per output.
- `conditions`: rows with `condition_id`, `signal` (`neural`, `microphone`, `stethoscope`, `imu`, `combined_biosignals`), one fixed `decoder_id`, `vocoder_id`, `training_provenance_id`, exact `training_trial_ids`, exact `selection_trial_ids`, and `external_speech_resources`. Every method must use the same declared training/selection memberships, vocoder and resource list. Each resource has `resource_id`, `version`, `role`. Decoder identity denotes fixed weights, normalization and preprocessing; operator attestation must bind it to their artifact hashes. Configuration declarations alone cannot prove this.
- `neural_condition_id`: the neural comparator's condition ID.
- `acoustic_profile`: `representation: "mel_power_db"`, `bands: 40`, `sample_rate_hz: 16000`, `window_ms: 50`, `window: "hann"`, `hop_ms: 10` or `40`, explicit `mel_filterbank_id`, `db_reference_id`, `silence_policy_id`, and `dtw_policy: "squared-euclidean-full-path-diagonal-up-left-v1"`. The profile is common to all compared conditions; extraction and masks require independent provenance audit.

The operator reference file is a list of rows, exactly one for every test trial:

```json
{"trial_id": "trial-identity", "mel_db": [[0.0, 1.0]], "speech_mask": [true]}
```

The displayed row illustrates field names only: real matrices must be time-by-40, every frame must contain 40 finite numbers, and at least two frames must remain after masking. No time axis is inferred from array lengths. `speech_mask` has one strict boolean per frame; masks may differ in length and retained positions between reference and prediction. Prediction rows have the same fields plus `condition_id`. They must exhaust the Cartesian product of every declared test trial and every condition exactly. Extra, missing and duplicate rows fail rather than being silently intersected.

A true mask means speech, false means excluded silence. Reference masks must be produced from reference audio alone and prediction masks from that prediction alone under a previously frozen procedure. This code does not select masks, detect silence or permit target-assisted extraction for a submitted decoder. Supplying only selected easy trials or favorable masks can invalidate an assessment even when the JSON passes.

## Acoustic computation

For each trial/condition, silence frames are removed independently. Full endpoint-constrained DTW uses squared Euclidean distance across the 40 bands; allowed steps are diagonal, up and left, with ties in that order. There is no fitted offset, path band or path-length normalization. The path aligns both complete speech-only sequences. A separate Pearson correlation is computed over aligned time samples for each of the 40 bands, then their arithmetic mean is the trial result. It is not a flattened matrix correlation or a mean Fisher transform. Constant bands, fewer than two speech frames, nonfinite values, numerical overflow and cell-budget overrun are errors; bands/trials are never dropped.

Cost is O(40NM); backpointers use NM bytes and dynamic costs two rows. `--max-dtw-cells` defaults to 2,000,000 per pair, can be explicitly raised by the operator, and rejects oversized pairs without downsampling or changing the metric. This is a declared engineering resource limit, not a scientific cutoff. The default may be insufficient for long trials.

Output contains trial scores and all 40 band correlations, retained-frame/path counts, sentence-weighted mean/sample SD/median, per-session summaries and an equal-session mean. Sample SD is null for one observation. All compared conditions share the same trials, enabling a per-trial neural-minus-control correlation difference summary. These are descriptive summaries, not participant-population confidence intervals or a reproduced Wilcoxon test. No threshold, binary reward or automatic admission decision is defined.

## Human transcription interface

`evaluator.py transcriptions` operates on a separate frozen listening cohort. Its plan requires task/schema identity, `tokenization_policy_id`, `phonemization_policy_id`, `pairing_policy_id`, `trial_ids`, `condition_ids`, and `pairs`. Each pair has a unique `pair_id`, two distinct **ordered** `trial_ids`, and exactly seven distinct `listener_ids`. Pairs must exhaust the cohort without reusing trials. Every condition must contain both trials for all seven listeners. The pair map and listener inclusion are frozen before scoring.

`cohort_label` is `prospective`, `paper_main_90`, `paper_video_38`, `paper_residual_20` or `paper_biosignal_30`. Named paper cohorts require the corresponding count but still do not establish historical identity. The 90 main evaluation trials, 38 video examples, 20 residual-speech trials and 30 paired biosignal-control trials must be scored in separate plans; this prevents silently pooling example clips into the main assessment. The 15-listener, six-choice matching assessment is distinct and not implemented.

Reference rows contain `trial_id`, nonempty `words` and nonempty `phonemes` token lists. Listener rows contain `trial_id`, `condition_id`, `listener_id`, `words` and `phonemes`; empty responses are allowed. No automatic case folding, punctuation removal, phonemizer or speech-recognition model is invoked. Tokens are exact strings under external frozen policies.

For each pair and listener, concatenate the two references and the two responses in plan order. Compute unit-cost Levenshtein edits divided by the reference token count separately for words and phonemes. Take the median of the seven rates per pair. Summarize those pair medians per condition; do not replace this by a pooled listener average or by averaging per-sentence rates. Rates are fractions and can exceed one with insertions. Returned per-listener edit counts and denominators make aggregation inspectable. These are declared human-response records; the scorer does not verify listener recruitment, independence, blinding or authentic panel provenance.

## Coverage and retained holds

| Contract requirement | Implemented here | Remaining requirement |
|---|---|---|
| Offline training and held-out synthesis | Explicit mode and session/trial exposure audit | Native training, checkpoint/inference/vocoder execution, authentic waveform outputs |
| Quality and control comparisons | Concrete 40-band DTW correlation, exact paired cohort and descriptive deltas | Original preprocessing/DTW equivalence, MCD, complete authentic controls, independent target reference |
| Session generalization | Full declared per-session tables and source roster validation | Authentic trial inventory, fixed-weight receipts and original day165 experiment |
| Voice intelligibility | Frozen paired-sentence seven-listener WER/PER arithmetic | Authentic cohorts/panels, token/phoneme/pairing provenance, 15-listener matching task |
| Information boundary | Separate reference input and receipt hashes | Actual protected infrastructure, packet/exposure policy and reference access enforcement |

The original closed-loop main population had 956 vocalized trials (plus 58 mimed in matching); biosignal decoding involved all 240 trials with ten-fold CV and a matched 30-trial listening comparison. V1 does not replace these populations with its generated controls, its session-heldout mode or an arbitrary declared subset. The full later Dryad release, exact native schemas, historical trial mapping and archive digests have not been acquired or validated. Source-recorded generic `digest` fields remain generic; they are not asserted to be verified content SHA-256.

No author source is vendored: top-level official-code redistribution rights remain unresolved. Data, manuscript, stimuli/TTS, pretrained models and LPCNet terms remain independent gates. Public results/checkpoints and overlap with other T15 work are acknowledged; there is no blind evaluation, new-person generalization, causal code-benefit or compute-equivalence claim. No authentic reference performance, difficulty or whole-paper qualification is established by these tests.

The generated controls exercise independent hand-computable correlations, exhaustive small DTW path costs, silence placement, listener aggregation, omitted trials, leaked groups, repeated physical trials, matched resource exposure, source-roster omissions, undefined bands, malformed inputs and exact input-byte provenance. They run on Python's standard library with no dependency installation, data archives, model/API calls or scientific campaign.
