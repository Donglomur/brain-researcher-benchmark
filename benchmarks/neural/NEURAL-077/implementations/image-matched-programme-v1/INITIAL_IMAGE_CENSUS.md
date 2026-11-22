# ERP full32 initial-image census

This operator collector uses the existing `erp-full32-visual-v1` interfaces to check all 6,400 initial query images. One Session render feeds both direct and programme projections. It checks identical PNG bytes, projection contents, normalized participant headers, and wire round trips. It is not a participant executor, provider client, predictor, or scorer. See [FULL32_VISUAL.md](FULL32_VISUAL.md) for the wider condition.

## Generated controls

Run the standalone harness directly; ordinary unittest discovery does not initialize its pinned module and fixture root. Omit `--method` to select all 16 methods:

```sh
"$PYTHON" -B "$IMPLEMENTATION/tests/generated_census_controls.py" \
  --candidate "$IMPLEMENTATION/initial_image_census.py" \
  --candidate-bytes 28622 \
  --candidate-sha256 44a66b3d4cd50134da73202464b6a6bc5c8aa2eaa58029a422b3175b361eb05c \
  --fixture-root "$FRESH_FIXTURE_ROOT"
```

The fixture root must be absolute and absent, with an existing ordinary parent. Select the interpreter and finite execution resources before running it. These controls use source/runtime/viewer stubs and synthetic image bytes. The full-6,400 case exercises orchestration with recorded fsync calls; smaller controls exercise real fsync and file-descriptor failures. No original input, NumPy, renderer, native participant, or provider is used by this harness.

## Original-input collector

The collector requires an externally frozen plan and its exact byte count and SHA256:

```sh
"$PYTHON" -I -B "$IMPLEMENTATION/initial_image_census.py" \
  --plan "$PLAN" --plan-bytes "$PLAN_BYTES" --plan-sha256 "$PLAN_SHA256"
```

The exact plan fields are `schema`, `qualification`, `source_root`, `source_guard`, `accepted_source_commit`, `public_root`, `manifest`, `output`, `runtime`, `limits`, and `hash_whole_shards`. Use schema `erp-initial-image-census-plan/v1` and qualification `shared_render_local_initial_projections`. Source, public-input, and output roots must be ordinary absolute paths and pairwise disjoint. Output must be absent and its parent must exist.

The source guard is an exact `{path,pin}` descriptor of a finite JSON `files` roster, whose rows carry `repository_path`, `bytes`, and `sha256`. It must close the existing programme binding and required APIs. The caller establishes the relationship between `accepted_source_commit` and those guarded source bytes; the collector does not obtain Git history or refresh pins.

Only the frozen 5,428-byte public manifest with SHA256 `241870678fed37fca67cc9c64e2e3a0830e0a97f9815332e27fa3018ed6c9f3f` is accepted. Its declared public extent is 235,921,250 bytes, including 32 query shards totalling 234,460,034 bytes. No private-target root or credential is an input. `hash_whole_shards` explicitly selects whether full query shard bodies are additionally authenticated.

Runtime fields bind invocation, prefix, Python/NumPy versions and NumPy origin, zlib compile/runtime versions, and runtime bodies. The script uses POSIX file and signal APIs. Resource fields are exactly `read_bytes`, `write_bytes`, `work_seconds`, and `closure_seconds`; `validate_plan` checks their ranges. Those ranges do not prove that a chosen operation fits. The caller supplies independent outer deadlines, process ownership and cleanup, and adequate resources. Logical read charges include conservative dependency allowances rather than a kernel I/O measurement.

## Evidence limits

Outputs retain an authenticated roster, attempt journal, hash-chained census, and final result. Successful scratch is deleted only after its census row is fsynced; deleted bytes stay cumulatively charged. Failures and partial journal tails remain visible. Completion requires all 6,400 deterministic query IDs, closed packet source, and no unresolved write accounting.

A hash census cannot replay discarded PNG bodies. Shared-render equality is not two independent renders, native delivery, a completed paired benchmark arm, later viewer actions, demonstration rendering, physiological validity, or scientific performance. The collector does not attest its own outer process closure.
