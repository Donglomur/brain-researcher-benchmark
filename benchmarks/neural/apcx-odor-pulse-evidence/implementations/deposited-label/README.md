# APCx deposited-label prediction

This is one conditional neuroscience task with two evidence conditions. Predict the integer deposited as `Total_pulse` from every released neuron's spike-count bins in a recorded session. The target is **not independently verified physical odor delivery**. The observation window is [0.5,5) seconds in 90 half-open 50-ms bins; the first 500 ms is unavailable and is never filled with zeros.

The complete released scope is 95,072 trial-unit rows, 10,831 trials, 43 sessions, 383 session-unit pairs and three recorded mice. Each condition contains the same 2,199 protected queries, including 165 queries among the 900 trials with unresolved physical-command disposition. Nothing is filtered because a physical reconstruction failed. The 43-session release is retained despite the paper's 42-session count.

`matched` supplies 16 calibration and eight development trials per session: 688/344 across the cohort. `full_calibration` supplies all 6,482 calibration and 2,150 development trials. Each method receives only its current condition and session. Both program authoring and case investigation must use identical session evidence, tools and declared budgets; neither may access another session, the other condition, owner files, source identities or protected labels. This component prepares and scores data; it does not launch or sandbox an LLM/candidate.

The target-blind hash split and existing HMAC opaque-ID projection are unchanged. This measures within-session interpolation on historically selected recordings. It does not measure new-animal transfer, authenticated chronology, prospective all-QC selection or unassisted LLM neural understanding. Public-data contamination remains possible.

## Existing evidence and current limits

The original selected-host operation completed all 86 session-condition episodes. Independent review reconciled all three fixed references in both conditions, all 13,194 submitted predictions and 1,204 normal-equation systems. The accepted decision was **complete fixed-reference engineering evidence only**. The eight-container predecessor used invented data; it was not authentic evidence. An earlier memory-admission refusal was closed before the successful operation and remains a preserved failed guard.

The portable interface reuses the accepted conversion, grouping, reference mathematics, local alpha selection and scorer. Its new file/provenance wrappers need their own verification. Reuse of the original result does not certify a new host, new conversion, new candidate or portable image. No scientific-task count, broad qualification, submission readiness, LLM result or SOTA claim follows from this source release.

Seven physical/source limitations remain beside every score: missing external all-QC roster; unavailable original trial exclusions/chronology; missing physical delivery/overlap logs; unproven compiler-to-file lineage; incomplete original spike padding/cap provenance; the 42-versus-43-session discrepancy; and unresolved released-row disposition semantics. The separately declared deposited-label task preserves these limitations rather than claiming to resolve them.

## Inputs and rights

The primary study is [Perception and neural representation of intermittent odor stimuli in mice](https://www.nature.com/articles/s41467-026-72445-1), Nature Communications (2026), DOI10.1038/s41467-026-72445-1. The [data record, version1](https://doi.org/10.6084/m9.figshare.31792705.v1), declares CC BY4.0. Attribute the authors and dataset DOI and identify transformations. The canonical deposited file is `apcx_neural_data_plus_behavior.parquet`, Figshare file62893717, 281,948,826 bytes, MD5 `71898ac370476e634e592f17171f2ee2`, accepted SHA-256 `83193081d7486e95590f1599cc20943f702d05d2d1ccf4f124038a5f86598598`. Do not download the entire 17.8-GB multiassay record or duplicate file alias.

The authors' [analysis repository](https://github.com/leboero/Odor_Pulses_Task_Analysis/tree/5653ebc491961e6ca196b39c18b086ffedf932ac) declares MIT. No author notebook, scientific output, article or dataset body is bundled here. The code in this component is the benchmark's authored conversion/evaluation source. Third-party environment packages retain their own licenses.

There are two complete provision routes, both explicitly owner-side:

1. **Reuse accepted prepared packets:** supply all four files named and hashed in `config.json`: both `PARTICIPANT_*.json` and both `OWNER_*.json` files, totaling46,615,026 bytes. `provision` verifies exact accepted sizes/hashes, strictly decodes JSON and preserves the original packet bytes. It checks all cohort/condition joins before creating a final bundle manifest. Do not reformat accepted packets: their original hashes are part of the input contract. It neither regenerates splits nor fits references.
2. **Convert accepted whole prepared sources:** supply the exact `ROWS.jsonl` and `COMMAND_DIAGNOSTICS.jsonl`, totaling234,753,785 bytes. `convert` invokes the accepted complete converter with a new private32-byte HMAC key. The split stays identical; opaque IDs and packet hashes change with the key. It conserves every row/trial/diagnostic and all old flags. The converter uses approximately704.3MB of input reads before bundle checks, because complete prehash/parse/posthash passes are intentional.

Scientific inputs are not included in this source distribution. Reuse the evaluator's exact accepted prepared inputs when available. Otherwise, the accompanying [complete official-input route](ORIGINAL_INPUT.md) provides `native_convert.py`: it converts the canonical Figshare Parquet into both exact byte-pinned prepared inputs using the accepted whole-cohort transformations. It requires a separately admitted native runtime and complete-operation review; this source package has not run the portable native conversion on a new host. The original Parquet cannot be renamed into either prepared format. Do not expose owner packets, protected targets, original identities or the private HMAC key through candidate storage simply because the underlying dataset is public.

## Portable commands

Run stdlib commands on POSIX Linux/macOS with Python3.11 or later from this directory. No network, installation, Docker invocation or candidate execution occurs. Every output directory must be fresh; failures retain partial outputs and cannot produce a valid final manifest. Commands print the hash of their final manifest; pin that literal hash when proceeding.

```sh
python3 -I -S -B task.py provision --inputs /private/accepted-packets --output /private/apcx-bundle
# Or, for a separately selected complete reconversion:
python3 -I -S -B task.py convert --inputs /private/accepted-preparation --output /private/apcx-bundle

python3 -I -S -B task.py episodes --bundle /private/apcx-bundle --bundle-sha256 BUNDLE_SHA256 --output /private/apcx-episodes
python3 -I -S -B task.py assemble --bundle /private/apcx-bundle --bundle-sha256 BUNDLE_SHA256 --responses /private/candidate-responses --output /private/frozen-submissions
python3 -I -S -B task.py score --bundle /private/apcx-bundle --bundle-sha256 BUNDLE_SHA256 --submissions /private/frozen-submissions --frozen-sha256 FROZEN_SHA256 --output /private/scores
```

`episodes` writes all86 files under `matched/` and `full_calibration/`, named by opaque session ID. Mount **one file only** per separately isolated candidate process. Never mount the full episodes directory, bundle, parent directory, source dataset, owner material or another session. Reset memory, tool caches and context between sessions/conditions. A valid schema is not proof of process isolation; the external evaluator must enforce and attest these boundaries before capability claims.

Each response has the exact fields `schema`, `profile`, `condition`, `session_id`, `participant_packet_sha256`, `episode_sha256`, and `records`. Schema is `apcx-candidate-session-result-v1`; profile is `apcx-deposited-total-pulse-within-session-v1`. Each record has only `case_id` and finite numeric `count`. Copy identity fields from the supplied episode; `episode_sha256` is SHA-256 of canonical sorted, compact JSON followed by one newline. Response paths must be exactly `<condition>/<opaque-session-id>.json`. There must be all86 responses with every query exactly once; extras, duplicates, missing files, relabeled/replayed episodes and boolean/nonfinite counts are rejected.

`assemble` authenticates all responses and freezes both complete condition submissions before reading either owner target document. `score` authenticates every frozen prediction first, then loads owner material. A missing/invalid complete submission yields no complete task score. File hashes bind content, not external candidate-process safety.

## References and metrics

The accepted fixed panel is calibration mean, total-spike ridge and all90-bin temporal ridge. Scaling uses calibration-only population moments; constant features contribute zero. The seven-alpha grid is0.0001,0.001,0.01,0.1,1,10,100. Each session/representation/condition selects alpha from its own development MSE, choosing the largest alpha within the frozen tolerance. There is no development refit or cross-session pooling.

The optional `reference --episode FILE --output FILE` command exposes that existing one-session numerical kernel. It requires the originally accepted Python3.12.8 and NumPy2.2.6 versions, with `OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1` set before process launch. Use Python's isolated mode without `-S` so the operator-installed NumPy can be imported. This command fits models and must be separately selected; it is never invoked by provisioning or scoring. Matching versions is not an immutable image or numerical-parity certificate.

Store all86 reference responses in the same two condition folders, then use `select-references` with the same arguments as `assemble`. It retains complete per-condition development-selection documents and freezes all six submissions. `score` preserves all six method/condition reports and the prespecified count-minus-mean, temporal-minus-mean and temporal-minus-count differences. Reuse the existing accepted results instead of rerunning an unchanged campaign merely to produce new receipts.

The primary score is the arithmetic mean of three animal RMSEs, each over that animal's complete held-out trials. All43 session metrics, three animal metrics and pooled descriptive metrics remain available. Finite negative counts are clipped to zero, with no rounding or upper clip. Constant-target R² is explicitly undefined. The CLI emits no new uncertainty claim: original chronology is unavailable, three mice do not establish population inference, and the earlier optional conditional bootstrap was not part of the accepted reference operation.

## Resource and verification scope

Each wrapper has a600-second managed deadline,1GiB managed input/retention caps and a4GiB observed RSS stop. These are bounds, not measured authentic portable costs or hard containment. The complete converter retains its128MiB per-document cap and512MiB decoded-record accounting. Linux `ru_maxrss` is converted from KiB to bytes; macOS already reports bytes. Data/result files are owner-readable only, inputs reject symlinks/hardlinks, and existing outputs are never replaced.

`test_task.py` uses invented data only. It checks malformed input and hash refusal, filesystem safety, target-free episode schemas, cross-condition/replay binding, complete response sets and a positive three-animal example whose independently calculable macro RMSE is2. These controls do not run the original prepared inputs, a numerical fit or an authentic scientific task. An actual portable full-cohort conversion/parity check, a new-host runtime admission, full provision-route publication and candidate isolation still need separate evidence.

`test_provision_bytes.py` adds ten invented regressions for byte-preserving provisioning. Numeric object keys can change sorted order after JSON decoding; authenticated packets must therefore be copied without reserialization. The checks retain strict JSON/hash admission, complete-cohort validation before a final manifest, bounded writes and refusal to overwrite existing files. They do not certify an authentic replay.
