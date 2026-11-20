# Running the SMC full-panel condition

`run_full_panel.py` is a trusted operator entry around the existing full-panel API and aggregate owner. It prepares a frozen run, executes the two access conditions through the retained owner, and routes private grading through a bounded grading role. It does not provision a runtime, train a model, establish authoring isolation, or qualify a machine by constructing JSON files.

The existing `benchmark.py --request` interface remains the interface for material export, development views, method freezing, inference release, prediction freezing and scoring. This entry does not replace its scientific implementation.

## Prerequisites and scope

Use the repository revision matching the entry's pinned source dependencies. The existing scientific source manifest is unchanged: the portable entry and grading helpers are separate maintained files. Preparation builds a fresh external component containing the selected scientific code and explicit operator bindings; it does not overwrite the shipped placeholder bindings.

The operator must supply an authentic full-panel pair, both frozen methods, a selected material binding, a selected deployment binding, and the matching runtime configuration. The bindings are trusted operator configuration, not participant evidence. Their hashes only authenticate which configuration was selected. The retained episode and owner still validate the source-selected qualification records and deployment, and perform their original runtime checks. Shipped unresolved bindings are refused.

Execution requires the supported Linux scientific environment, an immutable qualified image, the selected Docker endpoint and cgroupfs/cgroup-v2 delegation, matching PID visibility, pidfd support and the original ownership prerequisites. The Python environment needs the scientific dependencies of the retained full-panel API; this is not a standard-library-only scientific runner. Nothing in a source-control result substitutes for actual platform, package, containment or original-input qualification.

The task remains the original 20 ms full panel: 574 test trials, 35 observed bins and 137 held-in neurons, with the same four metrics and protected future/held-out targets. The velocity decoder fits TRAIN data. The two serial access conditions are `paper_data` and `paper_data_author_code_and_weights`. A fixed-output candidate is only an infrastructure check, not a competent scientific reference or an improvement over the paper.

## Prepare and inspect

Run the existing authoring interface first and freeze both methods before either inference release. Place the preparation request outside the fresh output and repository. All selected metadata descriptors use exactly `path`, `bytes` and `sha256`; paths are canonical absolute paths, and digests identify real frozen files rather than placeholders.

The request has these exact fields:

- `schema`: `smc_full_panel_public_prepare_v1`.
- `pair`, `material_binding`, `deployment_binding`, `runtime`: selected metadata descriptors.
- `methods`: one selected frozen-method descriptor for each of the two access conditions.
- `output`: a fresh private external directory under an existing parent.
- `max_component_bytes`, `max_overlay_bytes`: explicit finite preparation caps.

The request output must be disjoint from the repository and every selected input directory, including the request's directory. For example, put the request in an `inputs` directory and select a sibling `prepared` directory. Do not place the output beneath the request directory. Preparation writes separate input, component, protocol and overlay directories. It does not call the retained owner invocation function or launch a child.

```sh
python3.11 -I -B path/to/run_full_panel.py --repository-root "$REPO" prepare \
  --request "$REQUEST" --request-sha256 "$REQUEST_SHA256"

python3.11 -I -B path/to/run_full_panel.py --repository-root "$REPO" inspect \
  --prepared "$PREPARED" --prepared-sha256 "$PREPARED_SHA256"
```

`prepare` returns the descriptor of `PREPARED.json`. Inspection reauthenticates the selected source, component inventory, protocol, runtime and method selections. Preparing or inspecting a record does not authorize execution or claim successful runtime qualification. Failure before dispatch can leave private construction files; it is not evidence about resources created by some other operation.

## Execute

```sh
python3.11 -I -B path/to/run_full_panel.py --repository-root "$REPO" execute \
  --prepared "$PREPARED" --prepared-sha256 "$PREPARED_SHA256" \
  --recovery-read-bytes "$RECOVERY_READ_BYTES" \
  --recovery-write-bytes "$RECOVERY_WRITE_BYTES"
```

The retained recovery ranges are 128 KiB through 256 MiB for reads and 128 KiB through 64 MiB for writes. These are recovery allowances, not the whole scientific input/output budget.

Execution authenticates the prepared run, requires fresh execution and owner directories, and exclusively records dispatch before replacing the process with the authenticated canonical overlay runner. It does not invoke the repository's unadapted predecessor runner. The original owner performs qualification, production admission, ownership journaling, capture and recovery. An execution error, missing result or failed `exec` is never treated as proof that an owned resource is absent. Do not remove the dispatch record to retry an unresolved run.

The original improvement-owner deadline is 22,560 seconds, including its final 60-second recovery allowance. The producer retains its original six-CPU and memory profile, PID limit, zero-swap policy, measured counters and closure rules. These limits do not silently become a hard bound on all operator processes; whole-operator supervision and parent-loss containment require their own qualified deployment.

## Protected grading

Protected grading runs only after the retained owner has completed and its exact result descriptor is available. It additionally requires an explicit trusted grading-runtime configuration matching the selected immutable image and Docker endpoint. That configuration supplies the exact read-only inputs and fresh private grading work root. It is not a participant-selected container profile or a self-attested qualification flag.

Its exact schema is `smc_full_panel_grade_runtime_v1`, with keys `schema`, `docker`, `socket`, `image`, `readonly_mounts`, and `work_root`. `docker` is the selected executable descriptor. `image` contains `id`, `architecture`, `labels`, `container_base_labels`, and `environment`; its immutable ID must equal the admitted deployment image. The image and effective container label maps are separately validated through the pinned label policy. Read-only mounts use identical canonical host/guest paths. At most ten explicit mounts are allowed; the helper adds its fixed source, prepared inputs, request, runtime metadata, target and evaluator mounts, with a total ceiling of sixteen. The selected Unix socket is used by the host client and is never mounted into the grading container.

```sh
python3.11 -I -B path/to/run_full_panel.py --repository-root "$REPO" protected-grade \
  --prepared "$PREPARED" --prepared-sha256 "$PREPARED_SHA256" \
  --owner-result-sha256 "$OWNER_RESULT_SHA256" \
  --target "$PRIVATE_TARGET" --evaluator "$PRIVATE_EVALUATOR" \
  --output "$GRADE_WORK_ROOT/report/REPORT.json" --scratch-bytes "$SCRATCH_BYTES" \
  --grade-runtime "$GRADE_RUNTIME" --grade-runtime-sha256 "$GRADE_RUNTIME_SHA256"
```

The grade helper validates the genuine saved owner proofs before private target mounts, then runs the unchanged grader in a separate bounded role. Its limits are fixed: 2 GiB memory, a 600-second CPU soft limit with a 605-second hard limit, 720 seconds of work and a separate 60-second cleanup allowance. The scratch cap is separate from RAM and cannot exceed 512 MiB. The 2 GiB container limit includes its 1 GiB temporary filesystem; host supervisor RSS is outside that limit. The CPU limit covers the single grader interpreter across child authentication and exec, not host metadata checks or Docker-client work. The grading container has one CPU, one numerical thread, a read-only root, no network, no Docker socket, and no host PID or cgroup namespace. The actual containment and installed runtime must still pass future qualification; generated tests only check the source wiring and refusal paths.

The unchanged grader revalidates the saved execution proofs and uses its exclusive `GRADE_STARTED.json` lock. It validates both frozen predictions and methods before protected scoring. The original four-metric evaluator remains unchanged. Numerical failure retains the grading lock: it is not permission for another attempt. Timeout, nonzero exit or unresolved owned cleanup does not establish a valid score or resource closure.

The grading report is `work_root/report/REPORT.json`, the bounded supervisor result is `work_root/RESULT.json`, and per-call evidence is under `work_root/calls`. Preserve failed and partial evidence. A report file alone is not sufficient evidence of a successful bounded grade.

## Verification and limitations

The focused source controls use generated fixtures for path, descriptor, inventory, dispatch, saved-proof, bound-wiring and failure/closure checks. Numerical evaluation and native observations are explicitly represented as fixture boundaries. They do not run a biological benchmark, measure difficulty, establish physical containment, or demonstrate improvement over a paper. The public entry carries the original scientific and ownership checks into a portable composition; authentic scientific runs and their interpretation remain separate work.
