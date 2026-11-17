# Operator-supplied records

All descriptors are exact JSON objects `{path,bytes,sha256}`: a canonical absolute ordinary-file path, a nonnegative exact integer byte length (never Boolean), and a lowercase 64-hex SHA256 of those exact bytes. Duplicate JSON keys and nonfinite numbers are refused. The source validators impose field-specific extent and type bounds. Supply real records from the selected operator namespace; do not copy a test fixture or substitute an assertion of success for independently established facts.

## Initial profile

Exact keys are `schema,task_id,root_roles,input_records,environment_records,execution_selection`. Schema is `neural081_portable_profile_v1`, task is `NEURAL-081`. `root_roles` has exactly `source,operator,raw,secret,protected,output`. Source is the chosen fresh instance root string. Operator/raw/secret/protected are arrays of 1–32 canonical absolute external root strings; output is one canonical absolute external root string. All are pairwise disjoint. Each of the last three profile fields is either its real pinned descriptor or exactly `{"disposition":"not_supplied"}`. The profile and BUILD_RESULT never change.

`select-run` may resolve only missing input/execution slots through its explicit operands, storing source/run-bound `P/selection/OPERANDS.json`. `bind-environment` may resolve only a missing environment slot, storing `P/environment/BINDING.json`. Later stages use these exact fixed records and reauthenticate all identities. Initially pinned values cannot be replaced; missing/contradictory later records refuse.

## Input metadata

Schema `neural081_portable_input_record_v1`; exact keys `schema,task_id,preparation,N,census_evidence,physical_input_evidence`. N must be an actual admitted complete trial census in the source bounds, not a convenient subset or estimate. Census/physical evidence are descriptors. Preparation has exactly `inventory,release_root,raw_files,key,protocol_source,annotation_authority,worker_io,protected_roots`. Inventory/key/protocol/annotation-authority are descriptors; the key descriptor has extent 32 and lies under a secret root, but the constructor never opens its body. Raw descriptors retain the source-owned ordered ten person FIF names plus README, all eleven under the selected raw release root. Ten worker-I/O shares and the exact protected root list are required. Authentic raw arrays, private labels, keys, masks and target bodies are not distributed or read by construction.

## Execution selection

Schema `neural081_portable_execution_selection_v1`; exact keys are `schema,task_id,condition,origin,whole_limits,phase_limits,outer_limits,issuer_limits,request_caps,artifact_caps,central_limits,external_limits,total_limits,memory,worker_io,replication_seeds,channel,outputs,bootstrap_read_cap`. Origin is an exact finite float on the selected original monotonic clock. Complete phase/support/workload formulas and share inequalities are enforced by `_stage_selection` in [stages/metadata_stages.py](stages/metadata_stages.py), using the unchanged original authority predicates. Do not reset clocks between metadata stages or scientific phases.

Each resource dictionary uses the original ten counters; the source is authoritative for integer/seconds distinctions and floors. `worker_io` has preparation, grade, host_metadata_capacity_bytes; preparation matches all ten input shares. `memory` has address_space_bytes, readback_live_bytes, metadata_cap_bytes, other_reserve_bytes. `replication_seeds` has r0,r1,r2, each an admitted integer or null. `channel` has maximum_response_bytes,poll_seconds; `outputs` has output. Full host, provider/native, query and external observer budgets remain explicit. No recommended operating budget is inferred from a tiny engineering control.

## Environment records

Schema `neural081_portable_environment_records_v1`; exact keys `schema,task_id,host,worker_environments,native,provider,issuer,external_observer`. Host has central_python,parent_python,host_environment,address_space_bytes,inherited_address_space_bytes,qualification. The stored host environment has only PATH and PYTHONDONTWRITEBYTECODE (`1`); no credential value is stored. Worker roles are preparation/reference/issuer/grader, each with qualification and installed_versions; reference also chooses numeric_role r1 or r2. The unchanged source selects numerical package identities NumPy 2.2.6, SciPy 1.15.3 and scikit-learn 1.6.1. Their presence, numerical behavior and physical resource fit require real qualification, not a version string alone. The issuer uses the selected Linux x86_64/aarch64 Landlock mechanism with minimum ABI at least 3 and explicit limits.

Native metadata includes the actual qualified engine socket device/inode/owner, immutable image digest, interpreter/user, complete controls and engine/clock/namespace/physical-I/O qualification descriptors. Provider metadata retains the exact source endpoint/model, independently selected canonical literal IP, credential environment NAME only, token/HTTP/transcript limits, selected seed and tokenizer contract. Full exact key sets and limits are `_stage_native`, `_stage_provider`, `_stage_environment_records` in the shipped stage source; metadata is not a request to install, connect, fetch or run anything. The external observer record is also independently supplied.

## Authorities, qualification and approvals

The constructor checks actual source-owned request/run/schema joins against independently supplied seven-role authority templates, registries and receipts. It never issues them. Channel root is the source-derived P run root, so the original authority predicate can authenticate P/RUN.json; authority metadata itself remains below P/authority. The launch request is materialized before its authority, and the final envelope joins both without a hash cycle.

Route binding receives three real independent descriptors, receipt/qualification/source_binding. It copies exact bytes into Q and runs the original generic qualifier over the actual complete 72-source map. Review qualification and `R/APPROVAL_REGISTRY.json` are separately administered protected inputs. A passed-looking fixture record is not a usable substitute. This distribution contains no passing operational receipts, model outputs, credentials or synthetic approvals.

The [schema/function index](SCHEMA_INDEX.json) points to the exact shipped implementation for every stage and record validator, including nested schemas. Source-derived indices aid inspection; the constructor itself remains the validator.
