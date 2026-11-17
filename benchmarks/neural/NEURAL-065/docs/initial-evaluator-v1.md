# NEURAL-065 initial evaluator, V1

This package evaluates complete sentence predictions against private, pinned V1 typed-button labels. It applies known participant aliases, audits supplied split/alignment inventories, exports an allowlisted query manifest, computes person-macro character error rate (CER), and compares a neural-only arm with a complete language-only control using paired person uncertainty. Optional fixed-LM output stays separate. It is a concrete standard-library evaluator with generated engineering tests; scientific qualification and submission readiness remain unknown.

The canonical task remains unchanged: SHA-256 `1888547c763c67793b92ae4d1602c51917aa9d898755291e421ed545a54f7c47`, 11607 bytes. V2 data, native model training, raw recording ingestion, protected testing and full-paper final-number reproduction are outside this package. No native reference was executed.

## Primary evidence and the target distinction

All author-code references use revision `5f9889621d0df391c5aab37c996683d308e6e926` of Meta's [Brain2Qwerty source](https://github.com/facebookresearch/brain2qwerty/tree/5f9889621d0df391c5aab37c996683d308e6e926). The data revision remains `88f9096c6ce3a3fb17cc7b8e3131ff7f96da5684`; the actual data bytes were not fetched.

- [V1 feature configuration](https://github.com/facebookresearch/brain2qwerty/blob/5f9889621d0df391c5aab37c996683d308e6e926/brain2qwerty_v1/config/xp_config.py) uses Keystroke `button` labels. [Callbacks](https://github.com/facebookresearch/brain2qwerty/blob/5f9889621d0df391c5aab37c996683d308e6e926/brain2qwerty_v1/callbacks.py) distinguish typed target classes from intended sentence text. This package requires `target_definition="pinned_v1_typed_button_classes"` and refuses interchangeable intended-sentence labels.
- [V1 utilities](https://github.com/facebookresearch/brain2qwerty/blob/5f9889621d0df391c5aab37c996683d308e6e926/brain2qwerty_v1/utils.py) define 29 class IDs, participant merges and exclusions. Space is class 8, `@` is special class 13, and `9` is number class 28. The remaining classes are lowercase letters in author index order. The evaluator independently implements that mapping; it does not bundle author code.
- [V1 metrics](https://github.com/facebookresearch/brain2qwerty/blob/5f9889621d0df391c5aab37c996683d308e6e926/brain2qwerty_v1/metrics.py) decode class indices and normalize edit distance per update. The [training module](https://github.com/facebookresearch/brain2qwerty/blob/5f9889621d0df391c5aab37c996683d308e6e926/brain2qwerty_v1/pl_module.py) calls that metric on a batch. Native numerical parity therefore remains unverified; this implementation uses explicit sentence boundaries.
- The [primary article](https://www.nature.com/articles/s41593-026-02303-2) defines sentence-level CER and participant means. Its Methods distinguish intended keys from pressed keys and describe similarity-based sentence splits. Our typed-button endpoint and stronger held-person/session split policy must not be represented as reproduction of the paper's intended-key or final LM results.
- The [SpanishBCBL loader](https://github.com/facebookresearch/brain2qwerty/blob/5f9889621d0df391c5aab37c996683d308e6e926/studies/spanishbcbl.py) aligns triggers and behavioral logs, records unmatched events and applies source-specific exclusions. Template cleaning also includes particular typo corrections; it is not applied to scored predictions.

Upstream code is [CC BY-NC 4.0](https://github.com/facebookresearch/brain2qwerty/blob/5f9889621d0df391c5aab37c996683d308e6e926/LICENSE), copyright Meta Platforms, Inc. and affiliates. Upstream assets and models retain their own terms; this package grants no additional data/model rights. Only source-derived facts and independently written evaluator code are included. `source-provenance.json` records revisions and explicitly identified reconstructed source-view hashes; those are not asserted as independently fetched raw response hashes.

## Score and prospective policy

For sentence `s`, `CER_s = Levenshtein(target_s, prediction_s) / len(target_s)`. Within each resolved person, take the arithmetic mean over complete query sentences. The primary endpoint is the unweighted mean of those person means. Do not pool character counts or treat sentence rows as independent people. Insertions may give CER above 1. Empty predictions are legitimate deletion/constant controls; absent predictions are errors. Empty reference sentences are rejected by an explicit prospective selection policy, rather than adopting the native metric's denominator-one fallback.

Comparison is neural-only CER minus language-only CER; negative values favor neural input. Bootstrap samples resolved people with replacement, retaining each person's paired arm difference. The reported 95% percentile interval uses linearly interpolated quantiles and frozen seed/replicate count. One person receives descriptive differences and no population interval. This bootstrap choice is prospective, not a claim about the article's paired tests. No score or interval grants scientific admission.

The following are deliberately prospective task operationalizations:

- One modality per packet, because the five cross-device participant identities have not been resolved here. MEG and EEG outcomes must remain separate.
- The entire selected population is assigned to train, calibration or query. Training people cannot occur in target phases after alias resolution. Calibration people must also have query sentences. Every target person has exactly the frozen number of calibration sentences **and** typed keystrokes; zero calibration is allowed. This can constrain feasible sessions and must be decided before outcomes, never achieved by pruning rows after scoring.
- Complete source sessions and canonical biological visits remain in one phase. Alignment inventories retain raw subject/session identities; `biological_session_id` names the physical visit after operator reconciliation of aliases. That mapping is externally evidenced, not inferred from local session number equality.
- A template family ID may contain multiple near-duplicate texts. Its entire family remains in one phase. Exact conservative normalized text collisions also cannot be assigned to different family IDs. The collision key lowercases, decomposes accents and replaces punctuation with spaces; it is used only for private collision detection. It cannot establish complete similarity clustering: the frozen operator template-family derivation must be independently audited.
- Clock offsets and maximum residual tolerances are frozen operator choices in seconds. The evaluator verifies one-to-one, monotone event pairs, residuals, complete paired/excluded event accounting and each selected target keystroke's match. It does not reconstruct DTW, approve the tolerance or verify raw triggers.

MEG merges are `S18→S1`, `S14→S4`, `S10→S5`, `S21→S5`, qualified by `Pinet2024Meg/`. The loader's excluded `S13`, utility-excluded `S23` and five dated no-keyboard control IDs are rejected. EEG numeric IDs are zero-padded within `Pinet2024Eeg/`; excluded malformed `001` is rejected. This does not invent a full cohort count: all other file, block, practice-trial, sentence and alignment exclusions still require the frozen source-intake selection ledger.

## Input contract

All JSON objects use exactly the documented keys: unexpected fields fail closed. Duplicate JSON object keys and nonfinite constants are rejected. The complete generated input example is the `fixture()` in `tests/test_evaluator.py`; it contains no authentic observations.

The private packet has `schema_version=1`, `task_id="NEURAL-065"`, the exact `source_commit` and `data_commit`, `modality` (`MEG` or `EEG`), the fixed `target_definition`, `protocol`, `alignments`, and `sentences`.

| Object | Required fields and meaning |
| --- | --- |
| `protocol` | `protocol_sha256`, `selection_sha256` identify externally frozen protocol and full selection ledger; nonnegative `calibration_sentences_per_person`, `calibration_keystrokes_per_person`; integer `bootstrap_seed`, `bootstrap_replicates` (1–100000); `max_sentence_characters` (1–10000); `fixed_lm_id` (string or null). Bounds are engineering resource caps, not recommended scientific budgets. |
| Each `alignments` row | `recording_subject`, `session_id`, reconciled `biological_session_id`, `evidence_sha256`, finite `log_to_neural_offset_s`, nonnegative `max_residual_s`, complete `log_events` and `neural_events` inventories, `pairs`, `excluded_log_events`, `excluded_neural_events`. |
| Each event | `id`, finite `time_s`; inventories must be in strictly increasing time order. The present profile requires a common clock rate plus offset. Clock drift requiring affine/nonlinear transforms remains an explicit intake hold. |
| Each pair | `log_id`, `neural_id`. Pair endpoints must be known, unique, ordered and within tolerance after offset. |
| Each excluded event | `id`, nonempty `reason`; every unpaired event must be listed exactly once. A selected target cannot reference an excluded event. |
| Each sentence | Opaque 32-hex `query_id`, `recording_subject`, `session_id`, private `template_id`, private `template_text`, `phase`, nonempty `target_classes` (integer IDs 0–28), corresponding ordered `log_event_ids`, and unique per-sentence input `neural_asset_sha256` (never a shared full-session hash). Duplicate assets are rejected across the entire selected population. |

The packet SHA-256 is over canonical JSON (`sort_keys=True`, `ensure_ascii=False`, separators `(',', ':')`, UTF-8), generated by `digest()`. It binds submissions to every private row and frozen choice. Protocol, selection, alignment and neural hashes are references, not proof of authenticity; their external preimages and acquisition history must be verified separately. A supplied manifest cannot prove its own full-population completeness.

Each submission contains exactly `schema_version`, `task_id`, `packet_sha256`, `arm`, `lm_id`, and `predictions`. Arms are `neural_only`, `language_only`, or optional `fixed_lm`. Every prediction has only `query_id` and `text`. Predictions must cover every query exactly once, use the literal V1 decoded alphabet, and fit the frozen size cap. No case folding, punctuation stripping, whitespace collapsing or CTC blank/repeat removal is performed. Per-keystroke class outputs may use `decode_classes()` explicitly; unsupported class IDs fail instead of disappearing.

The neural arm requires null `lm_id`; comparator and optional fixed-LM arms must match the protocol's LM identity. Null LM in the language-only arm permits a frozen unconditional/no-neural control. These metadata checks do not prove actual model access. Checkpoint lineage, input access, inference traces, resources and training-corpus exposure remain operator-audited controls.

## Use and validation

Run from repository root with an existing Python 3 runtime. No installation is required.

```sh
python3 -B -m unittest discover -s benchmarks/neural/NEURAL-065/implementations/initial-evaluator-v1/tests -v
python3 -B benchmarks/neural/NEURAL-065/implementations/initial-evaluator-v1/evaluator.py queries private_packet.json > query_manifest.json
python3 -B benchmarks/neural/NEURAL-065/implementations/initial-evaluator-v1/evaluator.py evaluate private_packet.json neural.json language_only.json > private_report.json
```

Optional `--fixed-lm fixed_lm.json` adds a secondary arm without replacing the primary neural-only result. The query exporter returns only task/schema/packet identity and opaque query ID plus neural-asset content hash. Neural asset delivery is separate and must strip answer-bearing filenames, headers and embedded metadata. Do not send private packets, comparator outputs or score reports to candidates before the protected evaluation closes. Reports include per-sentence edit counts and private person identities, so they remain evaluator-private.

Generated checks cover the two-level weighting oracle (person macro `.25`, distinct from global sentence mean `1/3` or pooled error `1/12`), exact class mapping, insertion/deletion/transposition behavior, known alias leakage, biological visit and template isolation, missing/duplicate/extra IDs, native scope, invalid labels, unmatched events, unexplained losses, mismatched clocks, privacy allowlist, constant controls and CLI behavior. Independent review additionally checks Levenshtein against a separately implemented matrix oracle. These are engineering controls, not evidence of competent neural decoding.

## Requirement mapping and remaining holds

| Contract requirement | Package result |
| --- | --- |
| Person-macro neural-only CER, optional fixed-LM output | Implemented with explicit sentence boundaries and V1 typed-button provenance. |
| Alias resolution before split, session/template groups | Known MEG map applied; supplied original-session and canonical-visit partitions validated; exact text collisions checked. Authentic mappings/full family clustering remain held. |
| Equal calibration and no query transcripts/keycodes | Sentence/keystroke budgets checked; exporter allowlists IDs and neural hashes. Actual predictor environment/asset privacy requires independent audit. |
| Complete outputs and negative/null controls | Strict exact-ID coverage; malformed data rejected; valid constant/empty prediction controls retained and flagged. |
| Language-only reference and biological paired uncertainty | Mandatory complete comparator input, matching declared LM identity, person-paired bootstrap. Comparator competence/exposure and neural reference execution remain held. |
| DTW alignment and loss accounting | Supplied pairing and loss accounting executable; actual raw-trigger reconstruction remains held. |
| Frozen protocol, full selected payloads and rights | Version/hash requirements and explicit hold reports; no payload acquisition or rights expansion. |
| Native reference, independent replication, protected admission | Unexecuted, unresolved, qualification unknown. |

No partial or filtered score is returned on invalid input. No generic pass/fail threshold is invented. Root registry/catalog changes and publication are owned by the coordinator, separately from this package.
