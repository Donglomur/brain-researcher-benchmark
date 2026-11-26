# Maintenance and historical reconstruction

The public benchmark catalog comes from `benchmarks/registry.json`. Use `python3 -I -S -B scripts/catalog.py --check` to verify its generated views.

`bind_paper_improvement.py` maintains the authorized current paper overhaul. It
requires one validated source-grounded contract per registered paper, preserves
original task/registry bytes, and binds current same-task superiority criteria.
`refresh_paper_integrity.py --write` preserves legacy calibration source closures
against those historical bytes and refreshes their explicit workflow pins. Both
support `--check`; neither executes a model or promotes scientific readiness.
See the [paper improvement guide](../../docs/science/paper-improvement/README.md).

The `build_*` scripts reconstruct earlier construction metadata from an **external input tree in its original directory layout**. The private construction rosters and audits are not included in this public repository. Historical path strings in these builders identify those original inputs; they are not fallback discovery paths for the current catalog.

Every historical `build_*` CLI requires explicit inputs and a separate staging destination:

```sh
python3 -I -S -B scripts/maintenance/build_paper_delivery_manifests.py \
  --construction-root /path/to/original-input-tree \
  --output-directory /path/to/separate-staging-directory
```

The destination must be outside both this repository and the input tree. Builders preserve their original validation and source-pin checks. They write reconstructed artifacts for review; they never overwrite the frozen snapshots in `docs/provenance`, canonical `task.json` files, or the current registry. Current generator pins are identified separately from original construction evidence. Generated Markdown retains links into the original input layout and is not a public navigation page.

`--check` is available for the paper/neural delivery builders and the paper construction audit. It checks the explicitly selected staging destination. The paper construction audit's `--self-test` uses generated metadata and does not require an input tree.

`apply_neural_contract_amendment.py` uses the same input/output arguments plus `--proposal`, relative to the input tree. It writes the proposed roster, original roster and receipt into a **fresh** staging directory. The input roster remains unchanged; applying a staged amendment to current task registrations requires a separate reviewed change.

`neurobench_source_queue.py` provides reviewed source commits and root integration. Its commands and controls are described in [the source queue guide](../../docs/development/source-queue.md). It has no push command. Its generated tests are in `source-queue-validation/test_queue.py`; their `authoring/` names are disposable fixture paths, not public repository layout requirements.

`check_workflow_syntax.py` runs [actionlint](https://github.com/rhysd/actionlint)
1.7.12 before the existing source checks in the shared CI preflight. It checks
all current GitHub workflows, including expression context availability; a
well-formed YAML file alone does not establish that GitHub accepts a workflow.
The optional external shellcheck and pyflakes passes are disabled. Core
workflow, expression and context checks remain enabled, without blanket ignores.

Run the same check from a checkout with Python 3.11 and internet access:

```sh
python3 -I -S -B scripts/maintenance/check_workflow_syntax.py
```

The bootstrap supports Linux x86_64 and macOS arm64. It downloads one official
[1.7.12 release](https://github.com/rhysd/actionlint/releases/tag/v1.7.12) archive,
verifies its exact size and SHA256 before parsing it, admits only the reviewed
regular members, and places only the executable in a temporary directory.
No executable is committed or installed globally. Asset checksums, rather than
release-tag immutability, bind the selected release bytes. The Linux archive's
member roster is checked at runtime; the local qualification used macOS arm64.
Downloads are limited to 8 MiB and declared expanded members to 16 MiB. The
linter has a 60-second timeout, one Go scheduler thread, and a 256 MiB Go soft
memory target; that target is not an operating-system memory limit.
Acquisition runs in one fixed, same-interpreter worker. Its parent allows a
45-second communication timeout across both attempts and verifies the returned
archive bytes again before extraction. The worker permits at most one retry,
only for a transport `TimeoutError` or a `URLError` whose direct reason is that
timeout. Each request is limited to 20 seconds or the remaining shared deadline;
a retry does not reset the deadline. HTTP errors, aggregate deadline expiry,
URL or integrity failures, archive failures and lint failures are not retried.
Flushed attempt and stage markers are retained when acquisition fails.

Process creation and cleanup are outside the parent's communication timeout;
the existing 120-second CI step remains the outer limit. The 60-second lint
timeout and archive admission rules above are unchanged. Offline controls in
`tests/maintenance/test_workflow_syntax.py` use fake transport and lint results;
one harmless short-lived child exercises timeout kill and reap behavior.
These 23 controls do not download an archive or run actionlint.

This source lint pass does not add benchmark tasks, scientific test units,
model runs, or evidence of reproduced or improved neuroscience results.
