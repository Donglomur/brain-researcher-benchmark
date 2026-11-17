# NEURAL-059 full-cohort input contract

This source implements the complete **29-session, 13-animal, 7-laboratory** choice programme. It retains four information conditions (`SH`, `SHN`, `SBH`, `SBHN`), two actor arms (`F`, `I`), both fixed reference families and the prior, and all 40 diagnostic panels. The declared reference obligations are 1,972 primary plus 59,160 diagnostic fit slots. These are obligations, not completed fits or results. The earlier exposed 93-query, one-session pilot is a separate programme.

The package does not include recordings, labels, normalized raw sessions, model weights, Docker images, fitted states or scientific results. It consumes explicit frozen local operands. This document and `structured-input.schema.json` describe their shapes; they do not create or validate authentic inputs, confer execution authority, or remove the original scientific gates.

## Required local operands

Every ordinary file descriptor passed to `core.capture` has exactly `path`, `bytes`, and `sha256`. Paths are absolute, literal and free of symbolic-link ancestry; the captured file must be regular, single-linked, stable and complete. The descriptor pins the actual file bytes, independently of semantic JSON hashes. No placeholder descriptor is a valid frozen operand.

| Selection field | Required body or value | What is still external |
| --- | --- | --- |
| `source_sha256` | Exact selected `SOURCE_MANIFEST.json` SHA-256; all package source must match | Final selected public source capsule and its digest |
| `members` | Descriptor of the original ordered 29-member JSON array | Exact ordinary roster supplied with the public projection; never reconstruct it from the pilot |
| `raw_inputs` | Descriptor of an object mapping every original session ID to one structured raw session | Authorized source acquisition, source/version custody and source-faithful HDF5-to-structure extraction |
| `preparation_limits` | Exactly six positive integer bounds listed below | Bounds derived from the selected full cohort and reserved resources |
| `actors[condition][arm].policy` | Eight descriptors, one per four-condition/two-arm cell | Actual pre-exposure F source and I policy source implementing the worker ABI |
| `actors[condition][arm].role` | The explicit physical role contract | A selected immutable image, interpreter and complete finite physical limits |
| `actors[condition][arm].model_limits` | Exactly positive `calls`, `input_tokens`, `output_tokens` | Prospective matched limits; no automatic free or unlimited allowance |
| `model.configuration` | Descriptor of the fixed local model configuration | Explicit prompt, seed, input/output token limits and request byte bound |
| `model.checkpoint_root`, `model.checkpoint_files` | Read-only complete unlinked local checkpoint namespace and all relative file byte/SHA descriptors | Actual weights, tokenizer, configuration, applicable terms and complete immutable manifest |
| `native_profile` | Descriptor of the selected native profile | Exact native image, Python version, package manifests, API signatures and state byte ceiling |
| `paired_cost_limits`, `global_cost_limits`, `measured_global_F`, `global_F_evidence` | Prospective ceilings plus actual global F development accounting and its provenance | A defensible accounting record; zero is not inferred from missing measurements |
| `deployment`, `budget`, `stage_caps`, `diagnostic_output_bytes`, `closure_reserve_seconds` | Exact startup, ownership and finite resource contracts | A suitably provisioned Linux host, isolated daemon/cgroups, supervisor and reserved resources |
| `output_root` | Fresh private output root outside the immutable code tree | Sufficient reserved output capacity and custody |

The whole selection has the exact fields enforced by `selection.validate`. `study_id` is a fresh 32-character lowercase hexadecimal attempt identity. `budget` has `wall_seconds`, `cpu_seconds`, `read_bytes`, `write_bytes`, `live_bytes`, `files`, `model_calls`, and `stream_bytes`. Stage partitions are `root_metadata`, `calibration`, and `prediction_grade`; diagnostics have a separate output cap. A positive closure reserve is smaller than the whole wall budget. No runnable resource defaults are supplied here.

The lifecycle cost fields are exactly `wall_seconds`, `cpu_seconds`, `read_bytes`, `write_bytes`, `tool_calls`, `fit_calls`, and `provider_tokens`; all are finite nonnegative numbers, with integer work/byte/token counts. F development is charged once globally and allocated across the original 29-by-4 F cells. The same role and model limits are required across all conditions and both arms. These counters do not independently measure native file churn, candidate-internal fit counts or all physical I/O.

## Full ordered roster

The current scientific contract requires the exact ordered member array. Its canonical sorted, compact, ASCII JSON plus one terminal newline is **8,148 bytes**, SHA-256 `2d7b37af47a41fceedef09c4591984b942ee40ab2d3ea5530827e8f7dd32db58`. A differently formatted file can have a different ordinary descriptor while the parsed canonical array matches; using the supplied canonical file avoids that ambiguity.

Preparation separately projects each member to exactly `bytes`, `eid`, `etag`, `inherited_sha256`, `key`, `lab`, and `subject`, preserving original member order. Compact sorted JSON for that projection **without** a terminal newline must hash to `1ca385428a08c993dc68ba21992601f70b4fad7917bcbbc74533b710536b4ffc`. The original session/subject/lab tuples must also match. These are metadata identity gates, not authentication of source recording bytes. Never turn an ETag, declared source revision, or unknown inherited SHA into an invented content hash.

## Structured raw input

`raw_inputs` is a JSON object with the exact 29 session keys, not a list of prepared counts or a 93-case packet. Each session has exactly:

```
session_id, source_identity, source_profile, unit_ids, original_trials,
spike_times, spike_units, spike_domain, task_intervals, stored_splits
```

`source_identity` has exactly `repository`, `revision`, `pipeline_sha256`, `source_sha256`. The currently accepted profile is `reviewed_6fbd_structured_v1`, repository `brainbench-org/ibl-bwb`, reviewed revision `6fbd666fe8170a2165f5198c1f490911424a654d`, and reviewed pipeline SHA-256 `931002bcf87e2ff88a8eb2e270d963b2479971a0a7dabc3659c5098a2bec0c29`. A matching declaration does not prove actual generating-source equivalence. The separately reported generating revision `2bec8d496660856c050f1afed05a4397fc7f15bc` remains unresolved. A disagreement remains a structural hold; do not relabel incompatible source data to make a check pass. `source_sha256` is either the actual known 64-character lowercase SHA-256 or null, retaining uncertainty.

`unit_ids` is the complete distinct nonempty original all-unit axis. `spike_times` is a finite nondecreasing array; `spike_units` is the same length and every value references that full axis. `spike_domain` contains ordered nonoverlapping `[start,end]` intervals. All clocks must retain the original source correspondence.

Every original trial is retained with exactly:

```
raw_index, stored_ordinal, intervals_0, intervals_1, stimOn_times,
firstMovement_times, feedback_times, choice, feedbackType,
probabilityLeft, contrastLeft, contrastRight
```

Raw indices form the complete zero-based original-row bijection. Stored ordinals are either all null or a complete zero-based bijection; missing ordinals do not justify guessed sort ties. Trial intervals must be finite and ordered. Other scalar fields may be null where the source is missing; behavior codes are integer or null. No-response and otherwise excluded rows remain in the original chronology. Actual encoding checks, exclusions and structural holds belong to the unchanged preparation code, not a converter's silent repair.

`task_intervals` contains exactly `stimulus_side`, `stimulus_contrast`, `choice`, `movement_window`, `licking_window`, `reward`, `block_prior`, and `envelope`. Each row contains `trial_index`, `start`, `end`, and, except for `envelope`, `value`. Movement/licking values are null; other task values are integers. These rows must exactly match the source-derived task definitions. `stored_splits` has exactly `train`, `val`, `test`, each containing one ordered interval; they must agree with the original cumulative-duration recipe and gaps. They are not arbitrary train/test selections.

Preparation limits are exactly `max_input_bytes`, `max_output_bytes`, `max_trials`, `max_units`, `max_spikes`, and `max_work`, all positive integers. Input/output limits bound the full serialized programme as well as per-session preparation. The unchanged work bound uses each session's trial count T, spike count P, full unit count U and domain count D:

```
100*T + 10*P + 4*T*U + 4*T*D + 8*T*T.bit_length() + 4*P*D
```

The aggregate of all 29 sessions must also fit the selected work limit. There is no source-supported guessed full-cohort count, byte allowance, runtime or eligible held-case count.

The companion JSON Schema is a **shape aid for the accepted profile branch**. Actual Python type checks reject booleans where integer/number values are required. The runtime additionally checks cross-field lengths, ordering, joins, exact hashes, numerical domains, source recipe equality, source exposure and selected bounds. JSON Schema alone cannot certify these relations. No array-filled example is supplied.

## Extraction and numerical prerequisites

The installed process package starts from the structured JSON above. It contains no acquisition client or complete original HDF5-to-structure converter. A future converter must retain the full original trial table, all units and spikes, source clocks, domain, task intervals, split witnesses and exact provenance. Source acquisition and extraction remain explicit external prerequisites; supplying a syntactically valid JSON object does not meet the scientific custody gates.

The owner-side preparation imports **NumPy** for the original float64 `sum` and `cumsum` reduction. Its recorded reduction profile explicitly has `package_authenticated=False` and `authentic_source_parity=False`. The reference-container native profile does not qualify that separate owner environment. The public startup must make this dependency visible and retain that hold.

The reference profile requires NumPy `2.2.6`, SciPy `1.15.3`, an explicit scikit-learn version, complete package file manifests, a complete Python version, exact HGB/optimizer signatures and a positive state byte limit. The worker checks the selected native image, actual Linux/nonroot/security/cgroup boundaries and package identities. Admission remains `source_only_unqualified`; it is not numerical parity evidence.

The supported model leaf uses local PyTorch/Transformers, CPU float32, one thread, a fixed seed and greedy generation. It uses local checkpoint files only, disables remote model code and does not reuse request caches. No checkpoint, image, model identity, PyTorch/Transformers distribution or license is selected by this documentation. The root model configuration has exactly `kind`, `request_bytes`, `maximum_input_tokens`, `maximum_output_tokens`, `seed`, `system_prompt`, with `kind=local_transformers_text_v1`. All dependencies and terms belong to the explicitly selected immutable environment.

## Actor and model interfaces

The actor policy is actual Python source exposing `fit(calibration, tools)`. Calibration contains the session ID, condition and the allowed train/validation projections. It returns exactly three nonempty byte strings: `source_body`, `config_body`, `state_body`. For F, the returned source must be byte-identical to the pre-exposure policy. I may return its captured fitted predictor source under the same allowed inputs and ceilings. Every predictor source exposes `predict(view, config_body, state_body, tools)` and returns one finite left-choice probability in `[0,1]`. Inference occurs in a fresh process with captured artifacts; the current view has no `y`.

`tools.model` accepts exactly `messages` and `max_new_tokens`. Messages are bounded user/assistant role-content records; the system prompt comes from the frozen common configuration. The owner reserves calls and tokens before dispatch, retains unknown/failed reservations, and supplies the actual model response as `text` plus observed input/output token usage. No API key or remote provider is part of this interface.

The four information projections are S (nine stimulus indicators), H (seven predecessor-history indicators), optionally B (three privileged block indicators), and optionally N (all-unit log1p counts). Queries are sequential with the original whole-panel commit barrier before later history. Do not expose raw source/targets, answer-bearing metadata, model weights or a daemon endpoint to actor processes. Labels remain owner/protected-grader operands; producer closure precedes target-bearing grading.

## Interpretation and rights

Movement-onset alignment is retrospective; privileged block context is explicit. The full one-second, half-open window containment rule is a prospective source amendment, not a demonstrated reproduction of every original sampler behavior. Public source/data remain development material. This programme does not establish prospective forecasting, causal biological conclusions, unseen-animal transfer, target non-exposure, SOTA, or a meaningful success threshold. The original 24 gates remain.

See `PROVENANCE.json` and `RIGHTS.md` for the retained upstream code license and historical data-license evidence. A source release does not bundle or relicense data, model weights or environment images.
