# NEURAL-078 operator contract

This is a concrete operator-side connection from the accepted full-eight-person investigation producer to the original numerical scorer. It evaluates every one of the 195 fields. It neither reruns a candidate nor recalculates the empirical reference. The unchanged producer and its original observer remain in `producer/`; the unchanged `score.py` and `analysis_core.py` remain in `scorer/`.

The complete declared population is sub-001, sub-002, sub-003, sub-004, sub-005, sub-006, sub-007 and sub-010: eight public packets and 15 public members. No participant, support field, digest, null, negative contrast or reversed contrast can be omitted. The candidate report is at most 65,536 bytes. The original score compares 195 fields, including 58 numerical fields and 137 support, identity-digest and disposition fields. Numerical tolerance remains `1e-9 + 1e-7 * abs(reference)`. All other comparisons retain original strict types and equality. Effect sign is not a pass criterion; lower-quality conforming reports receive their original fractional score.

## Concrete operator interface

Use Python 3.11 or later for this host adapter, with `-I -S -B`. The exact source-manifest byte length and SHA-256 come from the independently reviewed handoff. The source-only inspection command is:

```sh
python3.11 -I -S -B /absolute/path/to/score_artifact.py inspect \
  --source-bytes REVIEWED_SOURCE_MANIFEST_BYTES \
  --source-sha256 REVIEWED_SOURCE_MANIFEST_SHA256
```

The separately selected grading command is:

```sh
python3.11 -I -S -B /absolute/path/to/score_artifact.py run \
  --source-bytes REVIEWED_SOURCE_MANIFEST_BYTES \
  --source-sha256 REVIEWED_SOURCE_MANIFEST_SHA256 \
  --request /absolute/operator/grade-selection.json \
  --request-bytes TRUSTED_REQUEST_BYTES \
  --request-sha256 TRUSTED_REQUEST_SHA256
```

These operands must be selected by the trusted operator; computing a hash of an arbitrary candidate-supplied document does not confer authority. No approved request or fabricated successful observer receipt is distributed. The complete request format is implemented by `selected()` in `score_artifact.py`:

- `schema`: `neural078_trusted_grade_selection_v1`; `task_id`: `NEURAL-078`.
- `operator_authority_id`: the external operator's attribution, not a credential or signature.
- `source`: exact `{bytes, sha256}` of this package's `SOURCE_MANIFEST.json`.
- `numeric_grading_authorized` and `candidate_access_closed`: literal true from the separately trusted selection. The earlier producer review has numerical grading false and cannot authorize this operation.
- `producer`: `repository`, `source_directory`, `attempt` and `package` absolute paths, plus `selection`, `review` and `external_receipt`, each an exact `{path, bytes, sha256}`. The operator root must contain the exact `authoring/delivery-20261105/common/neural078-holder-readiness-successor-v1` route and its selected reference-v3 export. See README.md for the source-only installer; the same operator root is supplied as `repository`. The producer attempt and original external receipt must already exist and be complete.
- `observation`: exact `{path, bytes, sha256}` of the independently trusted outer-exit observation described below.
- `output`: a fresh absolute directory, separate from producer custody, source and package.
- `runtime`: absolute `docker_binary`, Unix `docker_socket` and `docker_config` paths, plus an existing immutable `image` identifier. The image must equal the original explicitly reviewed producer image. No pull, build or installation occurs.
- `other_future_bytes`: a genuine nonnegative integer reflecting the current externally selected outside reservation. A number alone does not establish current capacity.

The outer observation schema is `neural078_trusted_outer_exit_v1`. Its exact fields are `schema`, `authority_id`, `adapter_source`, `program_source`, `selection`, `review`, `external_receipt`, `argv`, `process`, `signals_sent`, `completion_observed_after_process_exit`, `candidate_access_closed` and `scope`. The five source/receipt operands are `{bytes, sha256}` pins; `argv` is the actual complete original adapter invocation. `process` has genuine integer `pid`, `pgid` and zero `returncode`, literal-true `natural_exit`, `reaped`, `group_absent`, and finite `elapsed_seconds` no greater than 2,100. `signals_sent` must be empty. Completion must have been observed after the outer adapter exited naturally, and candidate access must be closed. Scope is the original eight-person/15-member/eight-packet/195-field scope object.

This format is not an observer implementation. A truthful external observer and controlled operator custody remain prerequisites. Fresh PID/group and resource-name absence cannot prove historical timing or independently authenticate an arbitrary assertion of success. In particular, the original observer's worker receipt is not evidence of the enclosing adapter's final exit. That distinction is why a separately selected outer observation is required.

## Admission and protected access

The host authenticates all current source members before compiling helper modules, then checks the byte-identical original source, selection, method/runtime reviews, central review, frozen programme, complete source/export collection, original external receipt and outer observation. It reuses the original observer's complete admission over the commitment, retired view, both native phases, full report and separate-grade handoff. It additionally validates strict closure types, native durations, the exact original command operands and the complete report before private metadata access.

No original neural packet is opened by this grading connection. Source/export descriptors bind the original collection; the complete producer evidence binds its prior processing. Current process absence and read-only Docker absence inquiries for all six original resources precede private-reference metadata. The original receipts do not retain every immutable container ID; these fresh inquiries check the retained exact names, not an invented historical ID list. Truthful outer observation and closed candidate access remain essential.

The host then authenticates the selected target binding, answer-worker completion and subsequent recovery records against the original collection pins. All eight packet identities, protocol, frozen scorer sources and gold identity must agree. The earlier host-admission failure stays false; the later recovery does not retrospectively certify original cleanup within 180 seconds. Only metadata is read by the host: it never reads, copies or decodes the gold body.

The trusted native worker receives exact individual read-only source/report/metadata mounts and the original gold file as a read-only mount. It revalidates the complete report before private metadata and performs exactly one bounded, hash-checked gold capture. It calls the unchanged `score.compare`. The emitted numerical result retains the original schema and complete per-field results; the host also checks all 195 field identities. Candidate code and original neural arrays are absent from the grade container.

Host public-report validation executes the unchanged source-derived report validator with scalar `math.isfinite` in place of its sole NumPy operation. This avoids loading a numerical runtime on the host. Native scoring imports the unchanged analysis core with genuine NumPy; no matching, summarization, packet loading or reference calculation function is called.

## Prospective resource and closure contract

This source build authorizes no actual runtime. The future host route uses a continuous 180-second whole interval, a 165-second work alarm and a 16,000,000-byte host capture ceiling, plus a separately bounded source bootstrap of at most 4,000,000 bytes. The retained-output ceiling is 64,000,000 bytes with 128,000,000 cumulative writes and a 20 GiB free-space floor plus current OTHER and remaining owned allocation. These are conservative software limits, not measured feasibility or whole physical I/O.

One trusted grade container requests 512 MiB memory, no extra swap, one CPU, 32 PIDs, 64 MiB scratch, read-only root, no network, no capabilities, no-new-privileges, no init helper and no image healthcheck. Its UID/GID matches the actual nonroot owner of the original owner-readable gold file; no permission change or gold copy is performed. Docker Desktop UID mapping and the selected image's NumPy/runtime behavior are unqualified. The worker interval is 15 seconds inside a 30-second phase. Its original phase clock includes score validation and final marker publication.

The owned grade resource is removed by its authenticated immutable ID, and both ID and name must be absent before completion. Unknown creation identity or cleanup ambiguity fails closed and leaves evidence for operator recovery; there is no automatic retry. Final completion checks the original clock after publication. A late/interrupted publication removes only its own authenticated marker; a foreign replacement is preserved. A final completion file still requires external observation of this grader's actual natural exit before downstream use.

## Scientific limits and generated evidence

This is fixed-cohort descriptive reconstruction of a matched error-minus-correct FCz analysis with ocular, pre-response, timing and support controls. Public correctness, hand, congruency and response time are intentional analysis covariates. Units remain native EEGLAB amplitude, not calibrated microvolts. Unsupported participants and aggregate null dispositions are valid. Numerical agreement with this fixed answer is not independent physiological confirmation, clean held-out generalization, raw-neural understanding, causal reasoning, exact manuscript reproduction, discovery or SOTA. The mixed 195-field score includes substantial metadata/support agreement and must not be presented as 195 independent scientific successes.

`test_generated.py` constructs all eight participant records and all 195 fields, complete producer metadata, generated recovery metadata and a fake Docker transport. It does not load original packets, gold or native resources. The generated scorer tests substitute only scalar finiteness and an unused array-axis declaration for NumPy; they do not qualify genuine native NumPy. The positive route exercises the real host orchestration and unchanged comparison function. Rejection cases cover malformed populations, mixed programme bytes, false integer exits, signals, missing recovery provenance and writable native mounts. `test_publication_deadline.py` supplies targeted publication fault controls. Original failures and superseded opinions remain in private authoring evidence; they are excluded from this public source projection.

Source-only inspection, controls and commits add zero benchmark IDs and establish no runtime, scientific or submission-ready qualification.

## Operative namespace correction

This successor fixes R1 from the preserved namespace revision opinion. Creation retains the ordinary default PID mode; admission requires the effective inspected `HostConfig.PidMode` to be exactly the empty string. IPC is explicitly requested with `--ipc private`, and the inspected `HostConfig.IpcMode` must be exactly `private`. Host, other-container, shareable, missing and incorrectly typed modes are rejected before worker start. No unverified explicit PID flag is introduced. This source correction is generated-metadata evidence, not observed native isolation. All other producer, scorer, population, private-binding, lifecycle and scientific contracts are unchanged. The private predecessor and its superseded opinions remain historical. This public package projects only the accepted successor-v2 code.
