# Closed production input formats

All JSON is finite and duplicate-key-free. Ordinary file pins have exactly
`{path,bytes,sha256}` with canonical relative path, positive integer extent and
lowercase SHA256. Paths and evidence are private operator inputs. No authentic
selection or approving fixture is bundled. The CLI's config and authorization
pins are supplied independently of candidate metadata. Each captured source
member/config is bounded by 1 MiB; the selected metadata_member_bytes separately
bounds evidence/nuisance bodies during an authorized run.

Configuration keys: `{schema,metadata_member_bytes,intent}`; schema is
`morse-production-configuration-v1`. Intent keys are exactly:

```
data_root, intake_manifest, nonce_root, nonce, workspace_root,
storage_configuration, order_nuisance, capsule_sources, paired_parameters,
native_profile, allocation, reference_seed, bootstrap_seed, bootstrap_repetitions
```

`data_root` is the existing ordinary authentic intake root. `intake_manifest`,
`storage_configuration` and `order_nuisance` are file pins below the independently
selected evidence_root. `nonce` is a pin below a separate private nonce_root;
its body must contain at least 32 independently selected bytes. workspace_root
is an absent direct child of the selected campaign mount. Intake, nonce,
evidence, workspace, legacy source and Docker configuration custody roots are
distinct and non-nested; only the two candidate source modes may share a public
source root. Neither shared source root may overlap private roots.

`capsule_sources` has frozen_program and case_adaptive keys, each with exactly
`{root,files,entrypoint}`. The existing freeze_capsule contract applies to all
source members, manifest/total/file limits and flat Python entrypoint. Candidate
artifacts are copied to workspace/capsules/MODE only after full storage admission.

`paired_parameters` keys are exactly:

```
environment, stage_limits, broker_limits, model_spec, freeze_limits,
prediction_max_bytes, export_max_bytes, context_max_bytes, total_reserved_bytes,
max_concurrency, authoring_exposure, technical_retry_policy, seed,
host_metadata_max_bytes, workspace_max_files
```

The original compile_paired_plan/validate_spec/validate_model_spec contracts are
normative. All capacity/deadline operands are explicit positive numbers of the
original required type, not defaults. max_concurrency is exactly 1; retry policy
is abort-preserve-no-automatic-retry. environment omits runtime_root; the fixed
operator supplies its own new worker-runtime root and the exact bootstrap/protocol
source pins. All roster/science/policy/hold fields and reference selections are
derived without permitting caller replacement.

Stage limits are the original exact fields: wall_seconds, cleanup_seconds, cpus,
cpu_seconds, memory_bytes, pids, file_bytes, nofile, workspace_bytes, output_bytes,
tmp_bytes, stderr_bytes, stdout_bytes, frame_bytes, command_timeout_seconds and
gpu_devices (empty for this CPU route). The inherited cleanup/CPU consistency
predicates remain exact. Broker limits: max_calls, input_tokens, output_tokens,
max_input_bytes, max_messages, frame_bytes, call_seconds. Model spec: endpoint,
model_revision, credential_env, protocol, request_max_bytes, response_max_bytes,
stderr_max_bytes, timeout_seconds, token_bound. The token bound has
utf8_multiplier, fixed_overhead, per_message_overhead and certificate_sha256.
That last hash is the independently selected token evidence body's exact hash.
Freeze limits: max_files, max_member_bytes, max_total_bytes, max_manifest_bytes.

Allocation keys are exactly: intake_read_bytes, prepared_array_bytes,
premarker_export_bytes, private_member_bytes, reference_member_bytes,
report_member_bytes, total_artifact_bytes, aggregate_volume_capacity_bytes.
All are positive integers. The code derives the complete intake read minimum
from the 256 authentic file pins and both fixed windows; prepared_array_bytes
covers at least both complete 745,285,632-byte float32 cohorts. This is not a
total NumPy/native heap estimate. Native fitting copies/workspaces require the
independently qualified host RAM/CPU owner. Artifact capacity includes every
original retained candidate allocation, separate premarker export, both capsules,
minimal runtime, five full reference prediction files, eight success metadata
files plus one failure allowance, and the report. Aggregate volume capacity
covers the sum of all 257 actual kernel ceilings; no thin subset is accepted.

The intake manifest is `{schema,source_commit,recordings}` with schema
`morse-pinned-cohort-v1` and the exact original source commit. recordings is exactly
PEOPLE × TASKS in that order, 64 selections using the incumbent
`{source_commit,participant,task,files:{header,markers,events,signal}}` schema.
Original source path binding, raw markers, sample-minus-one clock, 156 events,
62 channels, class coverage and float32 preprocessing remain in provider/importer.

Order nuisance body: `{schema,intake_manifest_sha256,field,rows}` with schema
`morse-source-identity-order-nuisance-v1`, field within_block_order, and all 9,984
rows `{source_identity,within_block_order}`. Values must be finite numeric operands
whose semantics were independently reviewed; the operator does not infer or
renumber them. No authentic nuisance rows are bundled.

Storage configuration uses schema morse-preprovisioned-tmpfs-v1 and exact keys
`schema,admission_id,host_uid,max_mountinfo_bytes,max_mountinfo_entries,
max_directory_entries,max_receipt_bytes,campaign,stages`. Each root descriptor
is `{path,mount_id,device_major,device_minor,device,inode,uid,gid,mode,bytes,inodes}`.
Mode is 448 (0700); host UID is positive and matches real/effective/container UID.
stages is exactly PEOPLE × (frozen_program,case_adaptive) × (train,query), with
rows `{participant,mode,phase,output,workspace}`. All 257 devices and mount IDs
are distinct, private tmpfs with exact kernel capacities and no host-namespace
aliases or nested mounts. No plan hash is placed in this preselected file; IDs
are derived after the final plan is compiled, avoiding circular hash bindings.
max_receipt_bytes must accommodate canonical plan/config and the full observation
receipt (898 root observations plus selection/admission events). Source code
reserves its finite buffers and each mount-table capture before their effects.

Native profile keys: docker_binary, host_python (absolute-path file pins),
docker_socket, docker_config_root, deployment_id, host_owner_source_sha256,
host_dependency_paths, numpy_version. The Unix socket descriptor is
`{path,device,inode,uid,mode}`. Docker configuration root is explicitly empty.
Each host dependency directory descriptor has those same five identity fields;
there are 1–8 distinct, non-group/world-writable selected roots. The real NumPy
import/version/path must match after those trusted roots are appended under
isolated/no-site startup. Their complete builds/transitive native libraries and
the real original-lifetime host owner remain independently qualified external
inputs. There is no default Python/model/daemon identity or automatic owner.

The separately selected authorization record has exactly:

```
schema = morse-external-operation-selection-v1
issuer, selection_id, intent_sha256, source_sha256,
operations = [authentic_intake,paired_candidates,five_references,private_report]
evidence = {intake, deployment, token, references}
```

Evidence values are pins below evidence_root. intent_sha256 is canonical digest
of the entire intent; source_sha256 is the production source manifest's selected
byte hash. This is an independently selected authorization artifact format, not
an issuer/signature protocol. The code cannot establish issuer truth from its
hash; an accepting record must never be fabricated to bypass independent review.

Each evidence body has a review_record file pin, also captured in full. Exact
body formats:

* Intake: `{schema,source_commit,intake_manifest,people,tasks,review_record}`;
  schema morse-external-intake-evidence-v1, exact full roster/source/pin.
* Deployment: `{schema,intent_sha256,native_profile,image_digest,
  storage_configuration_sha256,review_record}`;
  schema morse-external-deployment-evidence-v1.
* Token: `{schema,endpoint,protocol,model_revision,bound,review_record}`;
  schema morse-external-model-bound-v1; bound is exactly the three numerical
  bound fields excluding certificate_sha256, preventing a self-hash cycle.
* References: `{schema,intent_sha256,order_nuisance,methods,review_record}`;
  schema morse-external-reference-selection-v1. methods is the exact five-arm
  map to prior_only/order_only/premarker/permutation/erp_shrinkage respectively.
  It does not certify the supplied shrinkage method as competent.

Reference provenance freezes selected source, seed, actual algorithm, exact
nuisance pin and the unchanged premarker window. Actual serialized window hashes
are derived from the admitted complete primary/premarker records before candidate
dispatch and rechecked after exports/reference decoding. This has no circular
dependence on authorization/configuration pins, and it grants no query fitting.

The explicit bootstrap seed and 1,000–100,000 repetitions retain the original
descriptive participant bootstrap. No p-value, new success threshold or causal
interpretation is introduced.

V2 custody/startup clarification: config-root must equal evidence-root exactly
after canonical absolute/full ordinary-ancestry validation, before configuration
capture. Every existing data/nonce/legacy/capsule/dependency root is validated
before overlap checks. The absent workspace path must be canonical and have an
ordinary existing parent. Numerical imports occur only after dependency admission.
The intake read minimum is a source-derived serial first-failure maximum including
role-capped growing-file refusals, not a measured read total or64 simultaneous
failed signal reads.
