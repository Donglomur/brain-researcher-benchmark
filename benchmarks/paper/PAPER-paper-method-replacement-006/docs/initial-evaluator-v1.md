# Initial PopT/BrainBERT RMS evaluator

The package at `../implementations/initial-evaluator-v1/` implements an executable, paired volume-decoding evaluator and a native-output binding adapter. It is an independently useful construction component; `task.json`, the registration count and historical evidence are unchanged. Scientific qualification remains unknown and the full registered contract is incomplete.

## Source-derived endpoint and selected scope

The [Population Transformer paper](https://arxiv.org/html/2406.03044v4) uses binary volume decoding, concatenated BrainBERT Linear/Deep NN comparators, and subject-mean ROC-AUC with SEM; its main iEEG table uses 90 electrodes. Seven downstream subjects are present, and three share Cars 2. The source labels volume by extreme rank quartiles. Historical downstream splits are random 80/10/10 rows. This component implements RMS only; pitch, speech and sentence endpoints, pretraining and interpretability are outside this version.

Code revision `d237755bbdea123c60bface0cecbb48bab6f42de` is fixed. [SOURCES.json](../implementations/initial-evaluator-v1/SOURCES.json) identifies inspected paths, specific semantics and unverified content. No author code, data or weights are vendored. Source URLs are revision pins; they are not fabricated content SHA-256 receipts. The authoritative task pin is 31,269 bytes, SHA-256 `4b06cd0993642d160ce1f953434c777292f771c86d27896feafa5775c64ca4ef`.

The exact source test roster is `sub_1/trial001`, `sub_2/trial006`, `sub_3/trial000`, `sub_4/trial000`, `sub_6/trial004`, `sub_7/trial000`, `sub_10/trial000`. The fixed movie join uses each subject's held-out movie in paper Appendix D: The Martian, Aquaman, Cars 2, Shrek 3, Coraline, Cars 2, Cars 2, respectively. This join is an inference between two primary records; native timing/movie metadata must confirm it before authentic execution. Same-subject pretraining is present in the pinned trial roster. Pairwise trial disjointness does not establish unseen subjects or movies.

## Explicit prospective policy

`prospective-rms-matched-v1` is a new, declared comparison profile. It preserves the source's RMS endpoint and primary metric while making the following choices explicit:

- It requires all seven subjects and the complete operator-declared eligible word roster for each sole downstream session. Lower `floor(n/4)` words are negative; words from rank `floor(3n/4)` onward are positive. Remaining words stay in the frozen record with null labels and are excluded from scoring. For seven words this gives one low and two high words. A tie across either cutoff is rejected because a cross-version historical tie order has not been established. Quartiles use the full supplied session, following source label construction; they are not train-fitted thresholds or a new target definition.
- Saved train/validation/test membership is supplied and retained. Every split must contain both retained classes. Neural support intervals are half-open seconds; support overlap between different splits of a subject/session is rejected. The intended source RMS context is five seconds, but actual clipping/padding and support accuracy need native verification. Transcript-word duration or one-second negative-label intervals must not substitute for neural support. This strict profile may reject the historical random row split; no historical split recreation is claimed.
- The fixed nested electrode grid is 1, 10, 50, 90. These are prospective anchor counts, not a claim about the exact Figure 3 grid. Submitted channels are ranked by training-only linear decodability; the declared fit IDs must equal all retained training words. Each subset selects the highest-ranked membership but preserves the submitted original feature-channel order, matching the author loader's filtering convention. Membership, order and inputs are identical between arms and across each subject's scored examples. Eligibility/ranking evidence hashes are mandatory, but their contents and correspondence to the pinned `clean_laplacian.json` are **not independently established** here. Arbitrary submitted channel IDs do not become verified clean electrodes.
- The principal estimand is the equal-subject mean paired PopT-minus-baseline ROC-AUC difference at each count. No pooled-window score is used. The standard error is sample standard deviation divided by sqrt(7), reported descriptively because participants share stimulus content. Each subject also has a paired temporal-block percentile interval. Blocks are fixed 60-second recording-time bins; bins touched by a common neural support are merged. The same resampled blocks go to both arms. Undefined one-class draws are counted, not scored as zero. Intervals are conditional on valid two-class draws; fewer than two blocks yields no interval. Sixty seconds is a prospective choice; authentic autocorrelation and block-length sensitivity remain unresolved.

These choices address leakage and paired assessment; they do not recreate the historical model recipe. No numerical success tolerance or binary reward has been invented.

## Operator plan and frozen reference

Use Python 3.10+; no dependencies beyond the standard library. `evaluator.py freeze PLAN OUTPUT` builds the canonical reference and its SHA-256 digest. JSON duplicate keys and nonfinite values are rejected.

The plan is an object with:

| Field | Required value or meaning |
| --- | --- |
| `schema_version`, `profile`, `source_revision`, `endpoint` | `1`, `prospective-rms-matched-v1`, the fixed revision above, `rms` |
| `support_units` | `seconds` |
| `shared_resources` | Object containing exactly `brainbert_checkpoint_sha256`, `feature_table_sha256`, `preprocessing_sha256` |
| `population_manifest_sha256` | Digest of the independently retained eligibility/population evidence |
| `saved_split_file_sha256` | Digest of the actual saved split file, shared between arms |
| `pretraining_exposure_manifest_sha256` | Digest of the common disclosure ledger, including both arms' actual checkpoint/pretraining exposure; equality means a common ledger, not equal exposure |
| `words` | Every eligible word, with unique `id`, `subject`, `trial`, fixed `movie`, `start_s`, `end_s`, `split` and nonnegative finite `rms` |
| `channel_rankings` | Seven subject-keyed records with ordered distinct `channels` (at least 90), `selection_rule: training_only_linear_decodability`, `ranking_evidence_sha256`, `eligibility_evidence_sha256`, `feature_channel_order` (the same full channel set in feature-column order), `channel_order_evidence_sha256`, and `fit_word_ids` |

`rms` is the source-extracted scalar volume quantity, not a model prediction. This package does not recalculate acoustic features. SHA-256 fields use 64 lowercase hexadecimal characters. Hash syntax and matching are checked; external artifact authenticity is not inferred. The frozen reference stores full source values, derived labels, saved split membership, ensemble membership and policy. Rehashing a tampered label is insufficient: validation rebuilds the reference from its source values and fixed rules.

The plan, frozen reference, model-binding records and operator scorer must remain outside candidate packets. They contain target values or verifier information. `evaluator.py interface REFERENCE OUTPUT` exports only test coordinates, ensemble identities and artifact/reference digests; it excludes RMS, labels and channel-ranking fit IDs. Apply the task's same-data and approved-official-code access conditions when assembling actual packets. The public generated fixture is exposed engineering material. No sealed or blind assessment is established.

## Prediction interface and native binding

Each arm supplies a JSON object with `reference_sha256`, `arm` (`candidate` or `baseline`), `method`, the same `shared_resources`, `saved_split_file_sha256` and `pretraining_exposure_manifest_sha256`, `model_artifact_sha256`, `selection_split: validation`, `probability_semantics: canonical_high_rms`, and `native_high_rms_index`.

The candidate method is `pretrained_popt`; the baseline is `linear_concatenation` or `deep_nn_concatenation`. A mean pool or an unmatched feature extractor is not an allowed baseline. `model_artifact_sha256` binds an immutable manifest of all downstream run artifacts, not just the pretrained PopT file. Explicit `native_high_rms_index[subject]["electrode_count"]` is 0 or 1 for **every** subject/count run; mappings may vary between processes.

`predictions` contains exactly one row for every retained test word at each of the four counts: `word_id`, integer `electrode_count`, ordered `channels` identical to the reference, and finite `probability_high_rms` in [0,1]. No supplied labels are trusted. Missing, extra, duplicate, off-split and unmatched-ensemble rows fail instead of being inner-joined away. Row order is immaterial to scoring, while report provenance hashes preserve exact input order/content.

The author loader enumerates a set to map raw labels to class indices; class 1 need not mean high RMS. The author output stores `predicts` and `labels` without sufficient row identity. The native adapter prevents treating these arrays as already aligned:

```sh
python3 evaluator.py bind-native operator-reference.json operator-binding.json native-outputs.json candidate.json
```

`operator-binding.json` contains the arm metadata above except derived output/model fields, plus `runs`. Each run contains `subject`, `electrode_count`, `high_rms_index`, `ordered_word_ids`, `model_sha256`, `order_evidence_sha256`, actual ordered `channels`, and `channel_order_evidence_sha256`. Native channel membership/order must equal the frozen ensemble, and channel-order evidence must match the frozen reference; the adapter never infers actual channels from intended counts. Author selection files do not imply native feature order: the source loader filters membership while retaining original electrode order. The ordered IDs must match the complete frozen test set for that subject; the order evidence must trace the native manifest, saved test indices and emitted output order. `native-outputs.json` maps each `subject/count` key (for example `sub_1/90`) to the author's `predicts` and integer class-index `labels` arrays. All 28 runs are mandatory. The adapter compares every native label to independently derived RMS truth through the declared map, checks lengths/completeness, and inverts probabilities when high RMS maps to class 0. It rejects floating-point class inversion that would collapse distinct scores or change the semantic 0.5 decision. It emits prediction, binding, native-output and artifact-manifest digests. It does not prove the supplied order-evidence artifact is authentic; that native audit remains held.

The primary AUC grants half credit for tied positive-negative scores and is invariant under simultaneous class/probability inversion. `f1_high_rms` always uses canonical high-volume probability strictly greater than 0.5; it is a prospective semantic diagnostic. `f1_native_index1` separately preserves the source class-1 convention and NumPy's 0.5-to-zero rounding behavior. Native class-1 F1 is not used as a paired semantic effect when class orientation differs. The report also includes per-subject electrode-count changes from one electrode, subject-macro differences, all interval support counts, and both arms' method/model/input prediction hashes.

## Commands and generated controls

From the implementation directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
python3 generated_control.py /tmp/popt-generated-control
python3 evaluator.py score /tmp/popt-generated-control/generated-reference.json /tmp/popt-generated-control/generated-candidate.json /tmp/popt-generated-control/generated-baseline.json /tmp/popt-generated-control/scores.json --replicates 20
```

The demonstration generates 48 words per subject and uses a perfect-score versus tied-score arithmetic control. These are not models, BrainTreebank samples or competent baselines. Tests independently enumerate positive-negative pairs, check quartile floor asymmetry, tied scores, per-run class reversal/native row binding, cross-split overlap, exact population/ensemble coverage, immutable reference content, resource/split mismatches, target-free export and undefined bootstrap draws. Production default is 1,000 replicates; allowed range is 20–10,000. All validation here used bounded generated controls on CPU. Native/model/API scientific runs, authentic datasets and weight downloads: zero.

## Requirement coverage and retained gates

| Registered requirement | Current component and limit |
| --- | --- |
| Volume decoding, PopT+BrainBERT versus matched aggregation | Complete paired RMS scoring and native-array binding; extraction/training and competent empirical predictions remain absent |
| Identical features, channels, windows, saved folds | Exact declared identity/coverage checks and support-disjoint prospective reference; native identities and eligibility remain unverified |
| Electrode-count effects, per-subject uncertainty | Four fixed nested counts, paired subject estimates/SEM and conditional temporal-block intervals; no all-figure reproduction |
| Protected reference and code-access arms | Operator reference retained separately, target-free export; packet rights/exposure audit remains required |
| Independent grading, reproduction, improvement | Mathematical/adversarial controls only; authentic independent reference, tolerances, protected final panel and improvement qualification remain open |

Preserved holds include BrainBERT weight member/hash qualification and redistribution rights; PopT checkpoint/data rights; actual pretraining overlap and BaRISTA linkage; full input population/clean-channel eligibility; loader/timing/order and validation-selection audit; historical splits/ranking; independent figure references/tolerances; native compute envelope; competent baselines; and grouped improvement. Code MIT terms do not license checkpoints or datasets. No empirical performance, causal architectural benefit, compute equivalence or qualification follows from passing these tests.
