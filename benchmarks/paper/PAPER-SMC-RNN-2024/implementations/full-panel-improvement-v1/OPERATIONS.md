# Operating the full-panel improvement condition

This route measures one complete offline four-metric result on the original SMC
20-ms MC_Maze panel. It permits a frozen method to use the supplied unlabelled
held-in test panel jointly. It does not turn that result into faithful reproduction
of the SMC method, fresh-trial generalization, or an original 5-ms NLB leaderboard
result. The strict condition and reproduction interface remain separate.

## Source entry point

From a checkout containing this component:

```sh
python3 -I -B benchmarks/paper/PAPER-SMC-RNN-2024/implementations/full-panel-improvement-v1/benchmark.py \
  --repository-root "$REPOSITORY_ROOT" inspect --request "$OPERATOR_REQUEST_JSON"
```

Output parents must already exist outside source trees and Git worktrees; each
output itself must be fresh. The request is trusted operator JSON containing the
named arguments of the selected method. It is not a participant-supplied configuration or executable
plugin. `task_path` points to this component's new `task.json`, and `task_sha256`
must match its pinned identity. A freshly authenticated pair supplies the exact
`pair_path` and `pair_sha256`; the earlier strict 71-file export is not a valid
successor pair. The CLI records every returned document on stdout. Preserve the
request, stdout, errors and created outputs outside Git.

Preparation/inspection use NumPy and HDF5 support through the retained source.
Numerical grading additionally uses the retained exact original evaluator and its
scientific Python dependencies. Importability is not runtime or numerical
qualification. Candidate model dependencies belong to the separately selected
scientific image, which remains unqualified for this condition.

## Delivery and submission sequence

1. `prepare` accepts `prepared_root`, `author_source`, `paper`, `task_path`,
   `task_sha256`, `budget_path`, `output`, `max_bytes` and `reserve_bytes`.
   It authenticates the original inputs and rebuilds successor instructions,
   policy, task and manifests. Choose the byte cap from the complete prospective
   export plan; this guide does not authorize acquisition or export. The public
   budget object has only an `improvement` profile: 7,200 CPU seconds, 10,800 wall
   seconds, 8 GiB memory and six threads for each access condition.
2. `inspect` takes `pair_path`, `expected_sha256`, `task_path`, `task_sha256` and
   `max_bytes`. It checks the new identities, exact inventory and original panel.
   Rehashing an old or augmented package cannot establish admission.
3. For each access condition, `development` takes the common pair/task identities,
   `condition`, `output` and `max_bytes`. It copies only the admitted development
   view: training inputs, validation inputs and permitted validation targets,
   metadata, and the condition's allowed source/assets. It excludes
   `inputs/mc_maze/test/eval_input_20ms.h5`.
4. `freeze-method` additionally requires `dev_manifest_path`, `dev_sha256`,
   `program`, `plan_path`, and `selected_artifacts`. The plan names the complete
   cross-trial/adaptation procedure, seed, program hash, planned validation use
   and planned official-asset actions. Candidate artifacts use entries of the form
   `{"path": "...", "development_manifest_sha256": "...", "derivation": "..."}`.
   Their derivation is a bound declaration, not verified training history. Released
   official assets keep their assisted-condition allowlist identity. The frozen
   method snapshots program and selected artifacts; learned parameters may later
   change through that frozen program's permitted computation.
Freeze and authenticate **both** access-condition methods, artifacts and plans
before releasing **either** inference view. The low-level release API validates
its selected condition; the paired runner must enforce this cross-condition
ordering, and source exports alone do not prove delivery to an authoring process.

5. `release` adds `method_path` and `method_sha256` to the common pair/task,
   condition, output and byte-cap arguments. It checks the method and development
   view before creating a complete inference view. `inspect-release` authenticates
   that view using `release_manifest_path`, `release_sha256`, the same method,
   pair, task, condition and cap. It rejects extra observations and changed files.
6. A future qualified runner executes both frozen access-condition programs using
   their released views and the same execution profile. The participant writes
   `offline.h5` and a separate post-run actual-use declaration. The owner must
   authenticate both from the closed output inventory. A pre-run plan is not an
   actual-use report. All programs must be frozen before either phase starts.
7. `freeze` takes the common identities, condition, `outcome: "improvement"`,
   `submissions: {"offline": "..."}`, `declaration_path`, method identity,
   `output` and `max_bytes`. `score` takes that frozen record and its hash, the
   same pair/task/method identities, original `condition_root`, protected `target`,
   exact original `evaluator`, `output`, `scratch_bytes` and `max_bytes`.
   It snapshots the complete numerical submission before first target access,
   reports all four original metrics and retained reference differences, and
   preserves missing attribution/qualification evidence.

The two access conditions are `paper_data` and
`paper_data_author_code_and_weights`. They are distinct from the information
condition `full_panel_offline_transductive_v1`. Both receive the same permitted
observations and execution budget; the assisted condition adds the fixed official
source and asset allowlist. No new dataset, test held-out spike, future spike,
test behavior or final-score feedback is granted.

## Qualification and cost boundaries

These source interfaces establish their own delivery order and file identities.
They cannot prove an earlier authoring process had no other access to the public
test data, authenticate model provenance merely from declarations, or demonstrate
an AI result. A controlled study additionally needs authenticated development
process delivery/custody and an explicitly selected, measured authoring budget,
matched across the access pair. The execution profile above covers in-run
training/adaptation; it does not measure earlier development.

The runtime overlay assembles authenticated retained owner/transport source with
this condition's explicit bindings. It does not launch Docker or make a deployment
qualified. The fresh material identity is selected in `MATERIAL_BINDING.json`;
its actual construction is recorded in `MATERIAL_EVIDENCE.json`. A suitable Linux
image and cgroup/PID view, resource enforcement, owned runtime closure and
protected grading still require actual qualification. Preserve failed outputs and earlier strict-condition evidence.
