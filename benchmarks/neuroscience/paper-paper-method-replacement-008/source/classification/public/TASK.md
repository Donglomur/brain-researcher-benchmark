# BaRISTA paper reproduction and improvement project

Canonical task **PAPER-paper-method-replacement-008**, based on [BaRISTA, NeurIPS2025](https://arxiv.org/html/2512.12135v1) and [official commit83b27375eba60e9eba9da4e7dd8fb283baace376](https://github.com/ShanechiLab/BaRISTA/tree/83b27375eba60e9eba9da4e7dd8fb283baace376). This is one paper project, not22,960 benchmarks. It investigates spatial encoding and masking scale, and is distinct from PopT's population aggregation and Brain Treebank's word/sentence statistical reconstruction.

## Scope and complete required classification panel

The source corpus has ten clinical participants and26 recordings:17 pretraining, two downstream-validation and seven downstream-test recordings. Ordinary pretraining includes downstream people. The seven downstream recordings are:

|Person|Native recording|Source session|Channels / parcels / lobes|
|---|---|---|---:|
|1|sub_1_trial001|HOLDSUBJ_1_HS1_1|91 /25 /6|
|2|sub_2_trial006|HOLDSUBJ_2_HS2_6|100 /25 /8|
|3|sub_3_trial000|HOLDSUBJ_3_HS3_0|91 /20 /4|
|4|sub_4_trial000|HOLDSUBJ_4_HS4_0|151 /36 /9|
|6|sub_6_trial004|HOLDSUBJ_6_HS6_4|134 /30 /6|
|7|sub_7_trial000|HOLDSUBJ_7_HS7_0|205 /47 /9|
|10|sub_10_trial000|HOLDSUBJ_10_HS10_0|173 /42 /8|

All contacts after the declared source exclusion/join are required, not a selected90. Reusing unmodified PopT counts for people4/6 is wrong. Exact channel identities, hemisphere-aware Destrieux parcels/lobes and LPI coordinate IDs must be authenticated; published counts alone do not prove that join.

For **random_nonoverlap**, reproduce both `sentence_onset` and `speech_vs_nonspeech` on all seven sessions and five finetuning seeds. For **chronological**, reproduce `sentence_onset_time`, `speech_vs_nonspeech_time`, `volume` and `optical_flow` on all seven sessions, five saved chronological folds and five seeds. Five logical seed slots1…5 map to native training seeds0…4. Both pinned launchers establish those default integers; historical executed configurations and fold identities still need verification. Random fold slot0 denotes its single fixed source partition; chronological slots1…5 bind the five actual saved fold identities, not invented physical-time cutoffs.

Both protocols require all14 models: nine `barista_<encoding>_<masking>` combinations over `channels,parcels,lobes`; three `random_<encoding>` controls; `popt_brainbert`; and `brant`. Tables1/2 and16/17 overlap; overlapping model conditions are counted once. Masking scale is a pretraining condition, not a candidate-selected test mask. Five-seed and five-fold repeats must remain complete; do not choose the best seed or remove unavailable cells.

## Native segmentation and information limits

Every neural segment has6144 samples at2048Hz (three seconds), with full source channels and preserved finite float32/64 values after the audited native preprocessing/segment normalization. The source notch filters are causal lfilter operations and Laplacian referencing uses appropriate neighboring electrodes. Each segment is z-scored across its whole duration by StandardScaler. Centered segments and whole-segment normalization are offline inputs, not online causal decoding.

Main positives are centered on sentence-onset or speech events. Negatives require silence over the entire three seconds; PopT's center-second rule is not interchangeable. Main source windows are nonoverlapping before balanced random splitting. The splitter uses a separate fixed seed0 by default, rather than automatically changing partitions with training seed.

Chronological source folds use metadata row-count buckets and class-support selection, not uniform elapsed-time quintiles. They may place training intervals on both sides of buffered test intervals. This is blocked interpolation, not past-to-future forecasting. Within-partition segment overlap is permitted. The constructor requires native sample intervals to be disjoint across all three partitions and refuses an incompatible complete panel; it does not silently purge source rows. Exact source fold compatibility has not been demonstrated. Filtering history, trial annotation clocks and shared movie exposure need their own audit; a nonoverlap flag does not establish all forms of independence.

Volume and optical flow use inclusive .25/.75 numerical quantiles in the held code, with upper-threshold assignment taking priority if the thresholds coincide. This differs from PopT's rank-sliced quartiles. Native label1 means onset, speech, high volume or high optical flow respectively. Authentic events, native balancing, feature NaNs, trigger-to-neural sample joins and saved folds must be preserved upstream. A normalized array with the right shape is not proof of source compatibility.

## A/B conditions and staged inputs

`paper_and_data` and `paper_data_official_code` must receive the same complete empirical panel, noncode assets and needed pretrained checkpoints. B additionally receives the approved pinned official source. No operator scorer, private labels, trusted predictions, other-attempt history or private source audit is candidate-visible. The complete export is an operator package, never a candidate mount.

Each future context directory contains `VIEW.json`, normalized neural NPY arrays, aligned channel/spatial identities, training and validation labels, and blinded query IDs/arrays. Spatial array columns are L,P,I coordinate category IDs, hemisphere-aware parcel ID and lobe ID. Preserve row correspondence to supplied channels. Do not infer missing physical labels, create embeddings from arbitrary coordinates, or substitute a convenient cohort. Raw source indices, private query labels and the operator pool are absent from the view. A generation commitment binds the private input manifest; query IDs do not expose source row indices.

A context is exactly one arm/protocol/person/task/fold/seed/model. Methods and selection rules must be frozen before query grading. Contexts whose training labels can expose another context's query targets—including different folds, models, protocols and related Brain Treebank tasks—need separate candidate agents from inception, no shared conversation memory, labels, fitted state or query feedback. Resetting only a checkpoint after label exposure is insufficient. File staging alone does not enforce this boundary; without verified isolation, report exposed-development diagnostics only.

The current package holds source metadata and all32 selected official textual source/configuration/license/notebook files at the pinned commit. B staging verifies every required source file and refuses missing or altered members. Neural arrays and checkpoint assets remain absent. No complete empirical view or model has run.

## Reproduction metrics and prospective improvement

Return finite semantic-positive probabilities in[0,1] for every required query. ROC-AUC uses all declared queries and half credit for exact score ties. A single-class query has undefined AUC and makes its complete aggregate unavailable; it is never silently dropped. Candidate identity/model names cannot certify the trained architecture or checkpoint used—future trusted execution must establish that.

Keep all per-session/fold/seed/model AUCs. For manuscript-style classification summaries, pool35 session-seed AUCs per main task/model, or175 session-fold-seed AUCs per chronological task/model. Report unrounded mean and explicitly defined sample-SD/sqrt(n) SEM. The released convenience aggregator instead rounds cells and reports available-seed populationSTD; this benchmark does not claim historical SEM implementation parity. A separate prospective equal-person summary first averages that person's seeds/folds, then uses seven person means. Repeats and shared movies do not create independent patients. No significance, ANOVA, confidence interval or published-number agreement is automatically established.

The `improved` model is an additional prospective condition on every chronological context. It compares a frozen method against a separately obtained, competent **trusted BaRISTA parcels/channels** baseline on identical query IDs, checkpoints/exposure, source preprocessing and declared resource budget. Candidates do not supply or weaken that comparator. Primary is the complete absolute improved AUC equally weighted over seven people, four tasks, five folds and five seeds. Signed paired gain and trusted absolute AUC are separate. A higher score alone is not a novel biological claim, causal scale effect, unseen-person result or certified frontier advance. The authentic trusted baseline, resource/effect-size assessment and independent verification are missing.

## Submission interface

`SUBMISSION.json` has exactly `task_id,panel_id,predictions`. There are22,960 entries, ordered by arm (`paper_and_data`, `paper_data_official_code`), then770 contexts in protocol/person/task/fold/seed order, then the14 model IDs in the order described above. Chronological contexts additionally include `improved` last. There are no improvement entries on random contexts. Each entry has exactly `{id,arm,model,query_ids_sha256,values}`. `values` is `{path,bytes,sha256,shape,dtype}` for a primitive C-order float32/64 vector of exactly the context's query count. Use a single relative `.npy` basename. The public JSON schema and runtime complete-join validator are normative.

All22,960 artifacts are byte/hash/shape/range admitted before numerical private labels or baseline probabilities are read. Root JSON cap32MB, per-prediction array4MB, aggregate declared candidate arrays512MB. Reusing a file still counts each declared entry toward that cap. These are transport bounds, not measured full-panel RAM/runtime claims. All errors remain explicit; there is no invented pass threshold or successful-paper flag.

## Full paper still unfinished

The complete project additionally requires original masked-latent pretraining, multiple pretraining seeds, held-person-out pretraining, data-scaling subsets, masked-channel reconstruction, attention/interpretation, spectral reconstruction and architecture ablations. Channel reconstruction is not the classification AUC or token-pretraining loss: its exact held-out producer, per-channel masks, R² denominator and aggregation remain unresolved. Observed-token auxiliary training loss and visualization smoothing must not become reconstruction evaluation targets. These branches remain required and missing, not renamed or counted as completed work.

The five finetuning seeds for a fixed protocol/person/task/fold must share identical source row identities, neural and label array identities, channel/spatial joins and partitions. The constructor checks their support signature before opening arrays; changing a filename alias alone does not change the signature. Only actual seed/context identifiers and training-specific checkpoint-exposure metadata may differ.

The native source collator skips all-zero tensors, and its train/validation/test check compares segment paths rather than full sample intervals. A source compatibility audit must identify any resulting support difference before inputs are frozen; this benchmark never silently drops a required query. Native training returns rounded AUC logs but no authenticated per-query prediction artifact, so an actual probability-export join remains required.

The native validation selector can remain at the first epoch after an undefined initial AUC. Preserve and disclose that source behavior; a claim of best finite-validation checkpoint requires actual finite-validation evidence. No such source run is supplied here.
