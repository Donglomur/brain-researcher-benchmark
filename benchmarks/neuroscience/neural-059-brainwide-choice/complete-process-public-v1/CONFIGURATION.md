# Selection fields and external evidence

The JSON templates use null for a genuine missing selection. They are deliberately
invalid runtime selections. The preparation command derives exactly five fields
from this public source and the supplied config files, then invokes the captured
validators. Acceptance is a source/configuration check; actual capability checks
remain in the original owner and workers.

| Field | Actual supplied value and meaning |
| --- | --- |
| `study_id` | New 32-character lowercase hex attempt identity, fixed before exposure. |
| `source_sha256`, `deployment.code_root`, `members` | Leave null; exact source and public member metadata are derived at preparation. |
| `raw_inputs` | Descriptor of the complete structured 29-session input JSON. Never substitute the old pilot or a manifest describing only files. |
| `preparation_limits` | Positive integer `max_input_bytes`, `max_output_bytes`, `max_trials`, `max_units`, `max_spikes`, `max_work`. Preparation retains original refusal/hold semantics. |
| `output_root` | New literal absolute private output directory, separate from source and covered by selected custody/supervision. |
| `stage_caps` | Positive byte ceilings `root_metadata`, `calibration`, `prediction_grade`. Diagnostic output has its separate `diagnostic_output_bytes` ceiling. |
| `paired_cost_limits`, `global_cost_limits` | Scientific lifecycle ceilings with exact fields below; equal for matched cells. |
| `measured_global_F`, `global_F_evidence` | Actual previous global F-development measurements and nonempty supporting identity/evidence, charged once and allocated across F cells. Unknown values are not zero. The preparer neither measures nor authenticates the stated evidence. |
| `actors` | Exactly SH/SHN/SBH/SBHN, each F/I, each with `policy`, `role`, `model_limits`. Eight explicit source descriptors captured before real inputs. |
| `model.kind` | The implemented `local_transformers_text_v1` backend only. |
| `model.configuration`, `native_profile` | Leave null; descriptors derive from the exact supplied ordinary JSON config bodies. |
| `model.checkpoint_root` | Actual complete locally available checkpoint mounted read-only to owner and model workers. |
| `model.checkpoint_files` | Nonempty list of `{path, bytes, sha256}` with relative canonical paths and every checkpoint file exactly once. Include configuration/tokenizer files as well as weights. The runtime verifies the full namespace and streamed bytes. |
| `deployment` | Selected dedicated Linux Docker/cgroup identities and reference/grader roles, detailed below. |
| `budget` | Positive whole managed ceilings for `wall_seconds`, `cpu_seconds`, `read_bytes`, `write_bytes`, `live_bytes`, `files`, `model_calls`, `stream_bytes`. Source bootstrap is charged. |
| `closure_reserve_seconds` | Positive cleanup interval strictly below whole wall allowance. It does not extend that allowance. |

The scientific lifecycle cost keys are `wall_seconds`, `cpu_seconds`, `read_bytes`,
`write_bytes`, `tool_calls`, `fit_calls`, `provider_tokens`. Values are finite and
nonnegative; all except seconds are integers. Known genuine zero work can be zero;
missing work is not a known zero. Original model-service setup/retirement costs
are allocated over the 116 cells in each arm. Failed requests retain their token
reservation when actual usage is unknown. Unknown failed whole costs remain
explicit rather than being accepted as successful-only ledger totals.

Each role has the exact keys `image`, `python`, `memory_bytes`, `pids`,
`tmpfs_bytes`, `request_bytes`, `response_bytes`, `stream_bytes`, `wall_seconds`,
`cpu_seconds`, `journal_bytes`, `artifact_bytes`, `channel_bytes`, `channel_files`,
`work_files`. The image is an immutable complete OCI image ID and `python` is its
absolute interpreter path. Channel tmpfs bytes must be page aligned and at least
4096; channel and work inode ceilings are at least four. Other capacities are
positive selected values, not inferred observations. All eight actor roles are
equal. `model_limits` has positive integer `calls`, `input_tokens`, `output_tokens`
and is also identical across eight cells.

Deployment has exact keys `docker`, `dockerd` (ordinary executable descriptors),
`docker_host` (`unix:///...`), `docker_config` (empty credential-free directory),
`daemon_id`, `daemon_root`, `whole_cgroup`, `controller_leaf`, `daemon_leaf`,
`whole_memory_bytes`, `whole_pids`, `reference_role`, `grade_role`, `code_root`.
Paths/daemon identity must correspond to the actually supervised dedicated host;
the preparer does not open or qualify them. Whole memory and PIDs must exceed the
sum for one actor, 29 reference workers and two model services, with real
controller/daemon headroom. The grader's own memory limit must fit the whole cap.

The model config contains exactly `kind`, `request_bytes`,
`maximum_input_tokens`, `maximum_output_tokens`, integer `seed`, and the explicit
common `system_prompt`. The backend uses CPU float32, greedy generation and
fresh per-request RNG state with that same seed. There is no stochastic sampling
knob or tool/provider URL. Compatible model chat-template behavior is an actual
runtime qualification requirement, including the selected common system prefix
and user/assistant histories.

The native profile contains exactly `schema` (`n059_native_profile_v1`),
`image_id`, full `python_version`, `packages`, `hgb_signature`,
`optimizer_signature`, `state_limit_bytes`. `packages` has numpy, scipy and
scikit-learn, each `{version, root, files}`. `root` is the absolute directory in
the immutable reference image. `files` is a nonempty map from canonical relative
paths to `{bytes, sha256}` for the complete original non-bytecode package census;
exclude `__pycache__`/`.pyc` as the inherited profile specifies. NumPy 2.2.6 and
SciPy 1.15.3 are fixed by the original source. Scikit-learn version and both API
signatures must be actually observed and selected. Package image identities,
versions, signatures and hashes must not be made up to get through validation.

Supply model/checkpoint licenses, container dependency versions and host
interpreter/environment provenance alongside the future deployment record.
Neither a matching SHA256 nor a successful configuration validator grants rights,
demonstrates hidden-state isolation, or supplies a scientific success claim.
