# BaRISTA operator recipe and limitations

This is construction-only work. No authentic neural arrays, model checkpoints, training, inference or scientific grading were used. The complete paper project remains partial. A scorer for the complete main/chronological classification grid is not a claim that the full paper, original pretraining, reconstruction or frontier improvement has been reproduced.

## Exact holdings and source gaps

source/PAPER_INTAKE.json describes the external arXiv2512.12135v1 paper; source/tree.json binds upstream commit83b27375eba60e9eba9da4e7dd8fb283baace376. All32 selected source/configuration/license/notebook roles are retained; packaging and external role admission are defined in ../../SOURCE_ACCESS.md. The notebook is an inert code/markdown projection with original identity and no outputs. Checkpoint/image/article bodies are external. No source acquisition or native execution is performed by staging.

source/BRAINTREEBANK_ROSTER.json reuses authentic recording/movie metadata only. source/PROTOCOL.json is a hard-pinned construction contract with the complete10-person/26-recording roster,17/2/7 source split, Table9 spatial counts and the exact seven held recordings. It does not contain neural values or actual target arrays. Source metadata provenance is not data acquisition. Whole-data/raw-clock/source row selection and model exposure still need authentication. Baseline PopT was re-pretrained by the BaRISTA authors; another public PopT checkpoint is not automatically that comparator. Brant's6144→1500 resampling and checkpoint provenance likewise require the original implementation/configuration.

The current source example is not a full paper command: only one pretraining session is active, and default sentence_onset_time is inconsistent with force_nonoverlap=True. Direct native commands must override coherent task/data/model configuration after all required native source/dependencies are supplied. Do not invoke the provided scripts during current construction-only work.

## Complete normalized source panel

`prepare.py` consumes an audited already-segmented panel, not arbitrary features or a subset of persons. It copies primitive values, binds input generations and blinds query ordering. It does not filter data, infer labels, train encoders, fit predictors or choose scientific outcomes. A true raw-data adapter/clock/label/channel audit remains missing; its required hashes are necessary declarations, not executed proof.

The root RESOLVED.json has schema `barista_resolved_panel_v1`, exact source_protocol_sha256 and770 ordered `{id,metadata:{path,bytes,sha256}}` entries. Each metadata file is a single relative JSON basename in the root directory. Every referenced array is also a single basename in that directory, with exact `{path,bytes,sha256,shape,dtype}`. Each context JSON contains:

- schema `barista_resolved_context_v1`, exact `id,protocol,person,task,fold,seed` from design.contexts(), the source_protocol_sha256 and exact native `recording` from the fixed seven-case map;
- `native_seed` equal to logical seed slot−1, an actual `native_fold` integer, and consistent five-distinct fold mapping across all chronological contexts; both exact launchers establish default native seeds0…4; actual historical executed fold/configuration identities remain unverified;
- complete unique `channels` in source order, exact Table9 contact count, `spatial_ids` int64[C,5] (three source LPI coordinate category IDs0…200, parcel ID, lobe ID), and exact Table9 unique parcel/lobe counts;
- `rows`: complete source-selected records `{id,start_sample,end_sample,neural}`, with exact6144-sample half-open native intervals and finite C×6144 float32/64 segment values;
- `partitions`: nonempty train/validation/query lists of row indices, disjoint and covering every selected source row once;
- `labels` int64[N] semantic0/1 and `provenance` containing exact SHA256 values for raw_recording, native_segment_producer, normalization, label_and_clock_audit, channel_and_atlas_join, split_indices and checkpoint_exposure.

The constructor checks random nonoverlap globally and chronological disjoint native support across every pair of different partitions. It refuses missing context support or intersecting intervals; it never silently prunes, imputes, changes native chronology or picks favorable folds. The native notebook does not itself apply a sample-level embargo at every boundary, so actual source compatibility is not established. A prospective purged successor, if necessary, must be explicitly distinguished from source reproduction before outcomes. Filtering history and model exposure remain separate issues.

Both class labels must eventually have source-authenticated support. The constructor does not invent natural class prevalence, repair a one-class query or equate prescribed counts with authentic cohort identity. Single-class AUC is explicitly undefined in grading.

Future data-only preparation, after genuine inputs and separate resource admission:

```
python private/prepare.py --resolved /ABSOLUTE/RESOLVED.json --secret /ABSOLUTE/PRIVATE_32BYTE_KEY --out /ABSOLUTE/FRESH_POOL --max-output-bytes EXPLICIT_ADMITTED_BYTES
```

No invocation has run on genuine data. All770 metadata contexts validate before any neural arrays are read. Array files are deduplicated by authenticated source identity. The public generation HMAC commits to the entire private resolved manifest; private target identities are not exposed. Query IDs/order are HMAC blinded. Context JSON pins bind every copied primitive array. The constructor preserves float32/64 values and does not silently lower precision. Per-source-array bound12MB, per-context metadata32MB, root metadata32MB, max200000 rows/context are unqualified transport limits. Incompatible authentic support requires a versioned larger bound, not truncation. Future total output bytes must be explicitly admitted; final metadata count toward the cap. Full-panel memory, disk and runtime remain unmeasured.

## Isolated candidate views

```
python private/stage.py --pool /ABSOLUTE/POOL/POOL.json --context random_nonoverlap-sub1-sentence_onset-f0-s1 --model barista_parcels_channels --arm paper_and_data --paper /ABSOLUTE/EXACT_PAPER.html --out /ABSOLUTE/FRESH_CONTEXT --max-output-bytes EXPLICIT_ADMITTED_BYTES
```

This is one context example, not permission to omit the other769. Only the staged directory can be mounted. Staging copies complete train/validation/query input support; training/validation have labels, queries have blinded IDs. No original source indices, sample clocks, query labels, scorer, gold binder, other model context or operator source audit is included. Stage.py copies only the six named public contract/helper files plus paper, and for B the complete declared source tree excluding weights/image/irrelevant .gitignore; source files and required notices are authenticated through the pinned offline source descriptor. Arm B requires --official-source-root and both arms require --paper; see ../../SOURCE_ACCESS.md. Missing B files cause refusal before output creation. No checkpoints are currently supplied to either condition.

Separate candidate agents from inception are required for folds/protocols/models whose training labels can expose another query. Do not combine all contexts into a single agent workspace. Candidate method code/configuration must be frozen before labels or metrics from a query are returned; all adaptation, normalization and selection policies must be declared. A directory stager is not proof of process/network isolation or empty conversation history. A future operator combines outputs after isolated runs; no new controller is provided here.

## Native reference route, still unqualified

The exact held random-split launcher invokes:

```
python barista/train.py --dataset_config barista/config/braintreebank.yaml --train_config barista/config/train.yaml --model_config barista/config/model.yaml --override seed=0 device=cuda:0 checkpoint_path=EXACT_PRETRAINED_CHECKPOINT force_nonoverlap=True experiment=sentence_onset tokenizer.spatial_grouping=destrieux "finetune_sessions=['HOLDSUBJ_1_HS1_1']"
```

The full launcher repeats seeds0…4. This example is not executed or a complete supplied reference. The pinned train.py, model implementations and configuration files are now held, while checkpoints and authentic segmented data remain absent. The three released checkpoint descriptors in tree.json cover channels/channels, parcels/channels and lobes/channels only. The six other pretrained scale pairs, full random-initialization configurations, author-repretrained PopT/Brant comparator programs and historical numerical outputs are absent. No fallback to a weaker hand-made comparator or an arbitrary public weight is permitted. The native training implementation is held but cannot execute without its genuine assets/environment. Its run_epoch computes semantic-positive softmax probabilities and ROC-AUC, selects the best validation checkpoint, and prints rounded last/best test summaries. It does not export the complete query identities/probabilities required here; that source-binding/export adapter remains missing. No placeholder is reported as a runnable full reference.

Best-validation checkpoint selection must be bound to authentic logs/config and query probability extraction. Convenience log-parsed rounded AUCs cannot substitute for the full per-query outputs required by this scorer. Metadata assertions cannot certify that a candidate prediction was generated by the declared model. All native/reference commands train or infer scientific models and are outside current construction-only execution scope.

## Data-only targets and trusted baseline binding

A future independently authenticated trusted chronological reference has schema `barista_trusted_reference_v1`, exact panel_id, model `barista_parcels_channels`, complete700 ordered `{id,query_ids_sha256,values}` predictions and SHA256 provenance for program, training_config, checkpoint, exposure_audit and execution_receipt (each key suffixed `_sha256`). The baseline must be competent and frozen without query-dependent selection, with matched noncode resources/exposure and the defined seed/fold contexts. The binder verifies declared artifact shapes/identities; it does not establish execution truth or competence from strings.

```
python private/bind_gold.py --pool /ABSOLUTE/POOL/POOL.json --public /ABSOLUTE/POOL/PUBLIC.json --baseline /ABSOLUTE/TRUSTED_BASELINES.json --out /ABSOLUTE/FRESH_GOLD --max-output-bytes EXPLICIT_ADMITTED_BYTES
python private/score.py --public /ABSOLUTE/POOL/PUBLIC.json --gold /ABSOLUTE/FRESH_GOLD/GOLD_BINDING.json --submission /ABSOLUTE/SUBMISSION.json --out /ABSOLUTE/FRESH_SCORE.json
```

Neither command has run on authentic values. The binder admits every baseline before target projection and copies bound targets/probabilities only. The scorer captures all22,960 candidate arrays before numerical private inputs; a malformed final item cannot cause early scoring of previous items. Public generation and full target/query identities must agree. Native model identity, original SEM implementation, original hyperparameter provenance and scientific improvement remain separate unresolved requirements.

The benchmark records all source-model absolute performances and prospective improved/trusted/paired values. There is no binary reward, publication-grade inference, automatic reproduction flag or new accepted-task count. Full-paper reconstruction/ablation/pretraining branches and all scientific execution still remain open.

The five finetuning seeds for a fixed protocol/person/task/fold must share identical source row identities, neural and label array identities, channel/spatial joins and partitions. The constructor checks their support signature before opening arrays; changing a filename alias alone does not change the signature. Only actual seed/context identifiers and training-specific checkpoint-exposure metadata may differ.

## Native source and dependency closure

The native requirements file pins Torch2.4.0, NumPy1.24.4, Pandas2.0.3, scikit-learn1.3.2, SciPy1.10.1 and xformers0.0.27.post2, among its listed packages. The operator scorer uses a separate NumPy dependency; native compatibility must be established independently. A future native environment can follow the author README editable-install recipe from a dedicated copy, but no environment installation or compatibility proof occurred here. Preserve all source notices: LICENSE.md grants educational/research/non-profit use under its stated conditions and separately addresses commercial permission. Public redistribution is not inferred from local construction.

The chronological launcher explicitly sets force_nonoverlap=False, the selected chronological task and fold, and seeds0…4. Native train.py uses validation AUC for checkpoint selection. The native collator skips all-zero tensors; path-disjointness is weaker than an interval-support embargo. Required query support is never silently removed by this benchmark; any native compatibility discrepancy remains a source-audit hold. Native override parsing contains eval and source metadata includes serialized fold/segment artifacts. The future native route needs trusted fixed configuration and an isolated authentic-data binding; current source-text staging does not execute those parsers.

Native run_epoch converts AUC failures to NaN. finetune_model always saves the first epoch when best_state is None; if that validation AUC is NaN, later finite values do not compare greater than NaN, so the saved state stays at epoch1. The source is preserved unchanged. A faithful reference must disclose this behavior and establish finite validation support/logs before calling its state the best finite-validation checkpoint; silently fixing it is a separate method change. The all-zero collator can also fail on an entirely empty batch; test drop_last=False alone does not establish full support.
