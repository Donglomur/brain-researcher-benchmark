# Construct the complete FIND032 operands

[CONFIGURATION_TEMPLATES.json](CONFIGURATION_TEMPLATES.json) contains four **documentation templates**, not a runnable request. Copy each named section into its own JSON file after filling every null with its selected actual value. Never pass the surrounding documentation envelope to the operator. Nulls deliberately fail admission: no authentic file hash, filename, resource capacity, tolerance or monotonic deadline is invented here. There is no required private helper state or saved success receipt to obtain.

The four files are `input_manifest`, `controller_config`, `runtime_source_manifest`, and `operator_request`. The templates include every required key, all132 exact declared participant/condition slots and all43 runtime-source rows. The actual field consumers are linked below; their source remains unchanged.

## 1. Files, roots and exact pins

Select an ordinary control directory outside the component, authentic-input, exposure-source, programme, workspace, observation and protected-reference roots. Keep the control configuration/request/source-map there, except the input manifest belongs under `input_root`. Roots must be absolute normalized unlinked paths. Input/source/programme roots must exist; workspace and observation_root must not exist and their parents must exist. Four controller roots must be mutually disjoint (neither contains another); observation_root and reference_root must also be disjoint from those roots. Qualified numerical library roots must be disjoint from all of them and the component's `source/` root.

A relative `name` or `path` has no empty, `.` or `..` component, backslash or NUL. It names a file beneath the root specified in this table. Do not turn it into an absolute filename.

| Descriptor | Exact keys | Source of actual value |
|---|---|---|
| Input-manifest row | `participant, condition, path, bytes, sha256` | Fixed template participant/condition; actual authenticated recording-relative path, complete byte length and SHA256 under input_root. |
| Controller input_manifest | `name, bytes, sha256` | Exact serialized input-manifest file beneath input_root. |
| Controller source_members row | `role, path, bytes, sha256` | One authorized actual exposure file beneath source_root for each of the seven fixed roles. |
| Controller programs.A/B | `name, bytes, sha256` | Exact ordinary UTF8 programme beneath program_root. |
| Launch python_pin/docker_pin/config_pin | `bytes, sha256, mode` | Whole selected executable/config bytes and actual `stat.S_IMODE` of the ordinary file, in integer decimal form in JSON. Paths are separate absolute launch fields. |
| Assessment reference_result_pin | `name, bytes, sha256` | Exact protected `RESULT_MANIFEST.json`; name is fixed, not a historical verification path. |
| CLI request/source-map pin | `bytes, sha256` in CLI arguments | Exact final serialized operator request and runtime-source map. |

SHA256 is the64-character lowercase digest of **the exact whole byte string**, including serialization/newline choices. `bytes` is its length, not a filesystem allocation estimate. Derive pins after writing the final selected file; do not copy sample hashes. Ordinary single-link no-follow capture and stable identities are rechecked by the runtime. Config_pin mode is0400,0444 or0644 (decimal256,292,420); actual executable pins use their real permitted mode and must also pass executable access. The outer pin schema permits0400,0444,0500,0555,0644,0755, but read-only executable modes would still fail execution. Do not chmod existing inputs merely to imitate a sample.

The data manifest, each source exposure, each programme and controller config must fit their1MiB admission ceilings. Select complete authorized representations; never truncate a paper, programme or required input metadata to meet a limit. Recording data have actual selected whole-file extents rather than the1MiB source ceiling. Material requiring a different source ceiling needs an explicit source/protocol change, not a partial substitute.

## 2. Input manifest and participant programmes

Fill `input_manifest` and serialize it beneath input_root. Its exact schema is `FIND032_INPUT_V1`; release is `10.5281/zenodo.3268713`. Keep all132 rows from the template:33 declared identifiers × random/midminus/midplus/ordered, without duplicates or participant deletion. Every path must be unique. `rights_record` and `eligibility_record` are nonempty identifiers for actual upstream evidence; these strings do not issue rights or empirical eligibility. The declared roster is not itself empirical admission. See [admission.parse_input_manifest](source/find032/admission.py) and [roster](source/find032/roster.py).

The selected image invokes each programme as:

```text
python -I -B /candidate.py --view /view --contract /contract.json --output /output
```

Implement that CLI in each submitted programme and write the complete output protocol to `/output`. The programme is supplied by the benchmark participant; it is not an unimplemented trusted controller. The same selected image must provide `python` and the required dependencies. The view includes132 renamed recordings, projected INPUT_MANIFEST.json/ACCESS_VIEW.json and source_<role>.txt bodies. A sees paper; B additionally sees six official-code roles. The parent creates contract, holder, native owner, registry, journal, controller/recovery children and their receipts. Users must **not** create substitute owner/receipt objects. See [access.prepare_view](source/find032/access.py), [ArmSession](source/find032_runtime/lifecycle.py) and [candidate output contract](contracts/CANDIDATE_OUTPUT_CONTRACT.md).

## 3. Controller config

Fill `controller_config` using schema `FIND032_PAIRED_PARTICIPANT_V1`, profile `corrected_methods_v1`. Select endpoint `complete`, `empirical_and_most_likely` or `theoretical` prospectively; it does not reduce available output capture. `fixed_seed` is an integer0≤seed<2^32 and must match the protected reference. Keep exactly seven source roles and programmes A/B. Serialize the config in the control directory only after source/programme/input pins are final. See [validate_config and Stage](source/find032_runtime/staging.py).

`limits.normal`, `.cleanup` and `.evidence` each have exactly `{read_bytes,write_bytes,files}`, all positive integers. These are separately selected logical envelopes, not native CPU/RSS ceilings. The remaining three scalar limits are:

- `receipt_bytes`: positive integer≤1MiB for the complete terminal receipt.
- `attach_evidence_bytes`: integer>131072 and at least `docker.stdio_bytes + 1 + 131072`.
- `receipt_seconds`: positive finite number reserved inside the original normal interval; work_end=normal_end−receipt_seconds. It never extends the original endpoint.

The `.evidence` ledger must reserve write_bytes≥2×attach_evidence_bytes and files≥8; actual filesystem rounding is checked before launch. The template has exactly the six limits keys required by source: normal, cleanup, evidence, receipt_bytes, attach_evidence_bytes, receipt_seconds.

`docker` has exactly the13 template keys. `binary` and `socket` are the same absolute paths as launch.docker/launch.socket. `image` is an existing selected `sha256:<64hex>` image identity. All ten numeric fields are positive integers: memory_bytes,nano_cpus,pids_limit,scratch_bytes,volume_bytes,stdio_bytes,fd_limit,member_bytes,metadata_bytes,file_count. Require metadata_bytes≤member_bytes≤volume_bytes and file_count≥1087. The image cannot have implicit volumes/health programmes that change the selected command; source readmission checks its exact runtime configuration.

Budget the **complete** job. Stage requires normal read/write limits at least2×the total recording bytes for both views, before additional source/output work. The source-derived copy-buffer lower bound is2×the largest recording. Candidate and holder are separate native resources: account for2×memory,2×CPU,2×pids,4×scratch plus output volume and host views. These are lower bounds, not a complete measured capacity plan.

## 4. Host selection: no unexplained owner objects

`operator_request.launch.host_selection` is a plain JSON object. [NativeOwner.__init__/prepare](source/find032_runtime/native_owner.py) constructs the actual owner and cgroups from it. Its exact10 keys are:

| Key | Meaning/required shape |
|---|---|
| schema | Literal `find032_original_host_owner_v1`. |
| capacity | Complete normal host ledger below. |
| recovery_capacity | Separately reserved complete recovery ledger below. |
| cgroup_parent | Existing selected writable cgroup-v2 parent, absolute unlinked path. This is a real host filesystem requirement, not a JSON receipt. |
| group_prefix | New1–80-character string using lowercase letters, digits and hyphens. `<prefix>-controller` and `<prefix>-recovery` must be absent. |
| memory_bytes, pids, cpu_quota, cpu_period | Positive integers for each actual controller/recovery cgroup; cpu_quota and cpu_period use the Linux cpu.max microsecond units. |
| cleanup_seconds | Positive **integer**, passed to each cgroup's bounded retirement. It does not renew outer normal/cleanup/final endpoints. |

Both ledgers have exactly12 keys: read_bytes,write_bytes,creation_attempts,child_attempts,provider_calls,input_tokens,output_tokens,currency_units,live_fds,rss_bytes,wall_seconds,cpu_seconds. Every value is finite/nonnegative. All except currency_units/wall_seconds/cpu_seconds are integers. Each child_attempts must be≥1. Provider/token/currency dimensions remain explicit even though this fixed programme executor makes no provider call; select zero for an offline run. The other limits must support the actual complete operation, including authenticated source/executable/config capture, journal/evidence serialization, normal child work, separate recovery, descriptor ownership and kernel observations. Zero or small invented values are not a full resource plan.

The ledgers use application-owned logical effects and managed peaks; they do not by themselves measure total OS physical I/O/RSS. Cgroup memory/pids/cpu settings are separate native limits. Both host ledgers' wall/CPU observations are cumulative from the same original origin, including prior work; recovery wall_seconds is not merely an extra cleanup duration. See [Capacity](source/find032_runtime/n071_linux/capacity.py) and [Cgroup](source/find032_runtime/n071_linux/cgroup.py). Selecting cgroup_parent/resources requires real qualified host facts, but no private code or secret issuer is needed.

## 5. Operator request, source map and clocks

Finish `runtime_source_manifest` by setting root to the absolute component `source/` path. Preserve its43 exact selected rows/modes. Serialize outside the source tree and compute its CLI pin. The README includes a source-metadata-only preparation example.

Fill `operator_request` with exact schema `FIND032_COMPLETE_OPERATOR_V1`. Set launch.python/docker to actual qualified ordinary executable paths and compute their complete pins. Set launch.controller_config/config_pin to the final serialized config. Set observation_root to a fresh absent path with existing parent, and socket equal to controller docker.socket. No path points to the private authoring tree or an old verification run.

Only once a full run is selected, choose one monotonic timeline on that same host immediately before serializing/launching the request:

```text
origin <= current monotonic time < normal_end < cleanup_end < final_end < CLI original_endpoint
```

These are actual `time.monotonic()` coordinates, not Unix timestamps or durations. The enclosing trusted launcher supplies the original assessment endpoint via CLI and accounts for setup/serialization. No helper silently extends it. Choose normal, receipt, cleanup, final-evidence and assessment intervals with the complete workload in view. Expired operands must not be treated as completed work or silently renewed inside a failed invocation.

`assessment.reference_root` names the supplied protected full reference, disjoint from every participant/source/runtime root. Fill reference_result_pin for its RESULT_MANIFEST.json and finite nonnegative `absolute_tolerance`/`group_absolute_tolerance`. The reference must have the same fixed seed, complete coverage/products and exact axes. A prior result is not automatically a competent reference; actual scientific qualification remains external. The actual [assess_closed](source/find032/participant_executor.py) opens it only after both candidate decodes.

`budgets.launch` and `.assessment` each have exactly positive-integer read_bytes/write_bytes/files. `numerical_search_roots` is a unique list of1–8 existing qualified scientific-library directories, disjoint from all protected roots. `report_bytes` is a positive integer≤4MiB, pre-reserved in the assessment write budget. The enclosing launcher separately selects the entry bootstrap's4MiB source and1MiB request ceilings and map bytes; these are not returned scientific cost measurements. See [operator.run](source/find032_runtime/operator.py) and [entry.main](source/find032_runtime/operator_entry.py).

Serialize the request last, pin its exact bytes and invoke the fixed entry with README's CLI. Keep the fresh empty root-owned0550 cache outside all participant/reference roots. The public source provides the complete software composition and all operand shapes, not authentic files, a deployment image, competent reference, empirical tolerances or measured full-study resource sizing. No template or construction example was executed in preparing this release.
