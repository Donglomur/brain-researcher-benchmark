# Source component notes — 16 November 2026

These notes were collected from the construction-branch README at commit
`4c477e534e6b4ae378a7e2bacb08d3e0b603fc5e`. They describe source availability
and the limits recorded for each release. They are not a current readiness census.
Use the [catalog](../../benchmarks/catalog/README.md) for navigation.

## Clinical CCEP metadata preparation source

[CCEP native metadata preparation](../../benchmarks/neuroscience/clinical-ccep-native-metadata/README.md)
provides a prospective complete five-recording operator metadata projection and
validation command. It requires separately authenticated private native inputs
and external reader dependencies. Generated CI checks do not establish native
execution, waveform conversion or a new scientifically qualified benchmark.


### NIDER120 trusted-owner source

[The NIDER120 owner kit](../../components/nider120-owner-v3/README.md) supplies the reconciled Linux engine, private-input setup interface and [concrete provisioning requirements](../../components/nider120-owner-v3/PROVISIONING.md). It preserves all 120 fields (21 exact counts, 27 author-reported quantities, 72 unreported diagnostics), 24 material slots and the separate private reference. It is trusted-owner source and must not be mounted into a candidate workspace.

The public check authenticates all 44 manifest members before running 13 existing setup controls and 3 projection controls on generated metadata. It performs no scientific inference, Docker operation or model evaluation:

```sh
python3 -I -S -B components/nider120-owner-v3/run_public_checks.py \
  --manifest-bytes 7273 \
  --manifest-sha256 e0b0b4274fdb9dc481780970a694e9c696efe6f3b9c22dc8198bc7438b2ea8af
```

The existing scoped V3 compatibility result is historical evidence. Runtime-image distribution, fresh Linux target admission and any further scientific qualification remain separate; this source addition does not increase the number of finished benchmarks.


### Hybrid frozen-artifact provisioning

[Hybrid artifact provisioning](../../benchmarks/neuroscience/hybrid-artifact-provisioning/README.md) creates an authenticated location map for all 80 folds and a fresh, unselected no-refit operation proposal for authorized operators holding the exact private source and data bundle. It preserves all 20 people and 4,884 trials. It supplies no scientific assets or complete public replay runtime; generated interface checks do not establish authentic replay or readiness.

### PFC clean runtime source

The [PFC clean runtime source package](../../benchmarks/neuroscience/pfc-clean-runtime-source-v1/README.md) supplies the accepted Linux ARM64 build recipe, all 17 wheel descriptors, the pinned Python base and the four existing public Full99 input identities. Its 17 source files total 296,263 bytes; wheels, image layers and scientific inputs are not bundled. The external delivery-manifest SHA-256 is `d8ff7c06357357e9b274e3b0d2d50dcc52bb2acd4fbd1d6aa4d7602220d590d2` (2,882 bytes). CI authenticates every member before parsing source JSON and the two verifier ASTs, without importing those verifiers or running a build. The existing 99-recording/69-case scope is unchanged. Image distribution, fresh-host admission, full compatibility on the new runtime and exact installed-component notice lineage remain open; this source publication adds no benchmark ID or scientific result.

### Hybrid complete replay source

The [complete Hybrid replay source](../../benchmarks/neuroscience/hybrid-complete-replay/README.md) supplies all 43 declared source positions for the existing no-refit replay, preserving 20 people, 80 held-session folds and 4,884 trials. Its operator materializer binds explicit local paths and creates a fresh, unselected operation proposal. This supplies the authored source closure that the earlier provisioning component left external; the case map, immutable reference and frozen model artifacts remain operator-provided inputs. The existing [artifact-provisioning component](../../benchmarks/neuroscience/hybrid-artifact-provisioning/README.md) optionally supplies model-location maps.

The owned CLI replays the fixed reference programme and all 80 historical models, then requires equality with the complete reference score.

The endpoint remains within-person cross-session interpolation of processed behavior. Source publication does not establish unseen-person prediction, raw-neural understanding, a completed protected replay or new scientific performance. The historical runtime and fresh execution admission remain required. CI authenticates the complete public package before its admission-only generated controls; it excludes the inherited lifecycle test bank and scientific execution.

The external source-manifest SHA-256 is `6b346c779ab5f5450f2d495e5f631ce73c9570eae2a1b67dc3298aec4767bb3b` (7,534 bytes). The public package contains 53 files; CI authenticates all 52 manifest members before the twelve admission controls and does not rerun the 15 inherited lifecycle controls.


### Hybrid frozen-model candidate interface

The [Hybrid candidate package](../../benchmarks/neuroscience/hybrid-frozen-model-candidate/README.md) adds a frozen external programme condition to the same 20-person, 80-fold, 4,884-trial behavioral task. It supplies the complete 43-position source closure, reuses all 80 original trained models, and scores committed predictions with the unchanged paired-person scorer. The published [reference-only replay](../../benchmarks/neuroscience/hybrid-complete-replay/README.md) and its parity checks remain unchanged.

For an authorized operator, the [candidate binding instructions](../../benchmarks/neuroscience/hybrid-frozen-model-candidate/OPERATOR.md#separate-frozen-model-candidate-arm) specify the four Python files and their immutable manifest, then the existing `prepare_operation.py` command creates a fresh unselected operation. Legitimate complete case/reference/model assets, the exact historical runtime and fresh capacity/endpoint admission are still external prerequisites. Candidate-internal reads and whole-runtime qualification remain unresolved; `new_fits=0` describes trusted evaluator/reference-model fits, not an inspection of arbitrary candidate computation. Source freezing does not establish absence of earlier exposure. No authentic candidate result or additional benchmark is claimed.

From the repository root, run only the generated candidate-interface checks with:

```sh
python3 -I -S -B benchmarks/neuroscience/hybrid-frozen-model-candidate/run_checks.py \
  --manifest-sha256 600584659a526fb3f4c91e46afa0c1242b185f8a99fdf33fe17bad1e4278acd4 \
  --candidate-only
```

CI authenticates all 54 package files before the nine invented controls; it does not run a candidate, model fit, native container or scientific evaluation.

### Helsinki synthetic Linux lifecycle diagnostic

The [Helsinki zero-case diagnostic](../../benchmarks/neuroscience/helsinki-zero-case-diagnostic/README.md) supplies a portable trusted-owner `check`/`run` command for one fixed synthetic fork/allocation fixture. `check` authenticates the selected source, executables, local Docker endpoint, cgroupfs-v2 delegation and synthetic amd64 image before any container or cgroup creation. `run` additionally requires a separately reviewed operation selection and complete owned closure. An ordinary GitHub Ubuntu runner may refuse because its driver or delegation differs; this source does not configure Docker or qualify a runtime.

The package has 15 files / 127,871 bytes. Its external SOURCE.json SHA-256 is `8d4543cb25b398ecb9092941114b383303d5e26e3b96c5f62e79afca70fc4d4e` (2,179 bytes). The source-integrity job `helsinki-zero-case-generated-source` authenticates every member before the 13 generated interface methods. CI executes no Docker/cgroup operation, synthetic fixture, model or scientific programme; one generated test invokes only the inert CLI template-refusal path. The [operator instructions and limits](../../benchmarks/neuroscience/helsinki-zero-case-diagnostic/README.md#invocation) retain bootstrap trust, external provisioning and supervision, post-closure CPU accounting versus a hard aggregate fuse, and the unchanged full 79-infant/five-fold production gate. This component adds no benchmark ID, qualified runtime or scientific result.

The [NEURAL-034 portable operator package](../../benchmarks/neuroscience/neural034-portable/README.md) preserves the existing seven-mouse,140-window task with seven isolated folds and six comparators. It provisions exact external inputs and runs an arbitrary submitted Python program through the existing owner and late grader. Its relocation/admission checks use generated fixtures; authentic inputs, image385454, current runtime qualification and historical outcomes remain external. This improves one already-counted finite task and adds no benchmark ID.


### Purkinje complete paired-program source

The [REP013 portable bundle](../../benchmarks/neuroscience/rep013-purkinje-portable/README.md) supplies the complete task-local source for the existing ten-tree/13-component Purkinje comparison. It preserves the corrected integer and signed-bias scorer, all 31 numerical fields, 16 integer/flag fields and 58 diagnostics. Its [operator guide](../../benchmarks/neuroscience/rep013-purkinje-portable/OPERATOR.md) gives the existing A16/B18 packet command and arbitrary-program paired API, with a complete external input-map template. No full repository checkout is needed once this bundle and its independently authenticated release pins are available.

From the repository root, the following command authenticates the complete source and constructs the existing API without reading scientific data or starting a participant:

```sh
python3 -I -S -B benchmarks/neuroscience/rep013-purkinje-portable/portable.py \
  --manifest-sha256 1e1398a2430b32ecc1fc7aefe622ad123dfe8a5c85eed604dcdfc91a9bb526f8
```

Legitimate original inputs and fixed private references, the qualified external owner, original 385454 runtime and independent late-grading authority remain required. Source relocation does not supply those approvals, demonstrate a paper/code benefit, or qualify the broader donor/allometry/Sholl/spine claims. CI authenticates all 35 files before seven generated relocation/admission checks; no new benchmark or authentic result is counted.

The [REP012 portable paired API](../../benchmarks/neuroscience/rep012-portable/README.md) preserves the complete A9/B17 paper-access packets and four pooled-spine reconstruction endpoints over 1,143 released rows. It authenticates the existing paired controller and scalar scorer, with concrete operator API commands and inert external-input/runtime descriptors. Original data, paper/code bodies, private targets and current runtime/owner qualification remain external. This improves one already-counted finite task; it adds no benchmark ID or scientific result.

### Complete EEG waveform context preparation

[EEG waveform contexts](../../components/eeg-waveform-contexts/README.md) exports all 400 independent prompts from the fixed public packet, preserving the four demonstrations and every waveform decimal. The standard-library CLI authenticates inputs, retains failed partial exports, and publishes completion only after every case is written and checked. Generated controls cover the complete roster; authentic export, model inference and no-tools enforcement remain separate qualification steps. This adds no benchmark ID or model result.

### Complete Fly inspection operator source

[Fly native inspection](../../components/fly-complete-native-inspection/README.md) provides a relocatable, create-only operator package for all 42 files and 1,345 trials, preserving the existing inspector, independent auditor and process closure checks. Configuration remains inert until separately selected. Source tests cover relocation and input refusals; original data distribution, actual macOS execution, biological identity and forecasting qualification remain open.

### CONSENSUS35 header operator source

[CONSENSUS35 header operator](../../benchmarks/neuroscience/consensus35-header-operator/README.md) packages configuration, transport, parsing, process ownership and independent auditing for the complete 35-file header inquiry. The create-only configurator preserves the existing source graph and emits inert requests. Generated checks cover all 35 headers and source admission limits; external data and runtime qualification are required before authentic execution. This does not establish numerical reconstruction or a new finished benchmark.

### DUNL coupled reconstruction scoring

The [DUNL coupled scorer](../../benchmarks/neuroscience/dunl-coupled-reconstruction/README.md) evaluates submitted kernels, nonnegative event codes and baselines together. It checks that the convolution, logits and response agree before computing reconstruction losses across the complete declared roster. The portable command and generated checks require only the Python standard library. This is a reconstruction endpoint; historical paper reproduction and prediction on protected data remain separate evaluations.

### NEURAL-021 complete deferred grading

The [NEURAL-021 grading component](../../benchmarks/neuroscience/neural021-deferred-grade/README.md) preserves all 92 query cases and the original R2 scorer. Its command verifies the complete producer output and externally supplied process-closure evidence before accessing protected targets. The package includes the required authored source and generated checks; original scientific inputs, truthful external observation and current native-runtime qualification remain operator prerequisites. This improves an existing task without adding another benchmark ID.
