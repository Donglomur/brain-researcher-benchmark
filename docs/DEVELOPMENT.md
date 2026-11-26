# Working in this fork

## Branches and pull requests

The owned repository is `Donglomur/brain-researcher-benchmark`. Its default and
integration branch is `publish/neuroscience-200`. The preserved `master` branch
retains the original upstream history. Work in this fork does not change
`brain-researcher/brain-researcher-benchmark` without a separate upstream PR.

Before using an existing clone, inspect `git remote -v` and confirm which remote
points to this fork; some authoring checkouts use `origin` for upstream. Confirm
the PR's base repository and branch explicitly. The example below creates a fresh
clone whose `origin` is the owned fork, then starts one change from its current
integration branch.

```sh
git clone --branch publish/neuroscience-200 --single-branch https://github.com/Donglomur/brain-researcher-benchmark.git
cd brain-researcher-benchmark
git fetch origin
git switch -c feature/describe-the-change origin/publish/neuroscience-200
# Edit one complete change, including its tests and required current bindings.
# Run the affected checks and review the staged diff before committing.
git add path/to/changed-file
git diff --cached
git commit -m "Describe the resulting behavior"
git push -u origin HEAD
gh pr create --repo Donglomur/brain-researcher-benchmark \
  --base publish/neuroscience-200 --head feature/describe-the-change
```

Keep the change in one commit and one PR, including its coupled tests,
documentation and current source bindings. Describe the concrete problem and
result, validation actually run, and remaining limitations using the
[PR template](../.github/PULL_REQUEST_TEMPLATE.md).

Keep only one open, unmerged PR at a time within this serial delivery queue; this
limit does not restrict unrelated contributors' PRs. Advance the default branch
only through one normal merge at a time. After a merge, immediately verify that
`publish/neuroscience-200` points to the actual merge commit, its tree matches the
reviewed and tested tree, and its ordered parents are the preceding default commit
and the reviewed PR head. Once these identities match, refresh the fork remote and
start the next single branch and PR from that actual merge commit. Its checks may
run while the preceding merge's post-merge checks are still running. Use a unique
branch and keep its published head unchanged while its checks are running.

Before merging an ordinary independent change in this delivery queue, require
both the complete preceding post-merge checks and the next PR's required head and
branch-push checks to pass. Review the exact diff and complete the required review
for the current PR revision. Refresh the live
fork default and verify that it is still the actual commit used as the PR's base.
Confirm that the successfully tested checkout and prospective merge have the same
tree and ordered parents: live default first, reviewed PR head second. Then use
**Create a merge commit** for a normal merge. An ordinary queued change must not
create the next default-branch push before the preceding post-merge checks pass.

A failed, missing or cancelled preceding post-merge check blocks ordinary queued
merges, even if the next PR is green. Preserve the evidence and diagnose the cause
before selecting a specific repair or individually justified recovery. This
workflow does not authorize automatic retries or recovery. Do not cancel, retry
or skip runs to accelerate publication, or weaken coverage.

If a diagnosed default failure requires a source change, a separately selected
repair PR may advance that failed default without requiring its failed gate to
turn green. This is a narrow exception for resolving that failure, not for an
ordinary queued change. Wait for every existing queued or running predecessor
run or check to finish. Reconcile the full expected post-merge roster and preserve
any explicitly diagnosed missing entries, the diagnosis and original failed runs.
If an ordinary queued PR is
already open, let its active checks finish and close it before opening the repair
PR. Keep the repair focused and obtain an independent review of its connection to
the failure and its evidence.
Require all repair-head and branch-push checks to pass, including focused evidence
that the fix works on the successfully tested prospective merge tree. Refresh the
live default and prove that the tested checkout and prospective merge have the
same tree and ordered parents: the current failed default first, the reviewed
repair head second. If either identity changes, rebuild and repeat validation.

Only after that review and validation may the repair be normally merged. Verify
its actual default commit, tree and ordered parents immediately, then require the
repaired default's complete post-merge gate to pass before ordinary queued changes
resume. The predecessor's failed run remains failed; a successful repair does not
rewrite it as a pass. No required repair or ordinary-PR check may be bypassed, and
no scientific contract may be weakened to make a check pass. Preserve relevant
failures as well as successful results.

If the default changes, pause the pending merge. Wait for active checks to finish,
then rebase or rebuild the candidate on the latest verified default and repeat
its required checks, review and tree/parent verification. Use a fresh branch
instead of force-pushing; close the stale PR before opening its replacement or a
separately selected repair PR. The latest default's complete post-merge gate must
also pass before an ordinary dependent candidate merges. Retain the original
failed runs and superseded PR history.

Independent work may be prepared in parallel; within this delivery queue, only the
preceding post-merge checks and the next PR's checks may overlap. Shared runner
capacity can reduce or erase any speedup, so this workflow promises no delivery
rate. Do not recreate already
merged work or split dependent changes to increase the number of PRs.

The fork automatically deletes merged feature branches; local branches can be
removed once their work is merged and no worktree or unfinished work depends on
them.

## Task and implementation ownership

Each registered task has a directory under `benchmarks/paper/` or
`benchmarks/neural/`, with its authoritative `task.json`. Implementation packages
live beneath their owning task or in [shared source](../benchmarks/shared/README.md).
The shared directory includes multi-task programmes, related-only sources and
families without an assigned task owner. `benchmarks/registry.json` records these
relationships and unresolved ownership explicitly.
An ownership relationship does not establish complete runtime or scientific
qualification. Retained and alternate sources keep explicit roles.

Generic framework modules live in `src/neurobench/`; public command wrappers live
in `scripts/` and work from a repository checkout without an editable install or
custom `PYTHONPATH`. Historical reconstruction builders under `scripts/maintenance/` require an explicit
`--construction-root` and an `--output-directory` outside the public repository.
They use original-layout construction inputs and write a separate staging result;
they do not regenerate current task definitions or overwrite frozen provenance.
They are not public quickstart commands; see the [maintenance guide](../scripts/maintenance/README.md).

## Catalog and source changes

Edit the authoritative definitions and registry, then regenerate browsing views:

```sh
python3 -I -S -B scripts/catalog.py
python3 -I -S -B scripts/catalog.py --check
python3 -I -S -B scripts/check_navigation.py
```

Do not edit generated track indexes, task README pages or catalog files by hand.
Additional task guides belong in the task's `docs/` directory and must be linked
through the registry or current documentation.

Move a complete implementation package with all of its consumers. Update current
imports, manifests, source inventories, CI commands and guides together. Preserve
closed package inventories and distinguish unchanged scientific bodies from path
or entry-point repairs. `scripts/check_repository.py` validates repository ownership
and layout against `benchmarks/integrity/source-ownership.json`. The separate
`scripts/check_source_integrity.py` uses `benchmarks/integrity/current.json` for four
enrolled bundles; [the guide](development/source-integrity.md) explains both scopes.

Historical records describe their recorded revisions. Do not rewrite their old
paths or hashes to make a new tree appear historically identical. The
[provenance guide](provenance/README.md) and
[November 16 relocation ledger](provenance/relocations/2026-11-16.json) preserve the
old-to-new relationship. A changed source binding may require fresh qualification;
a passing navigation check does not supply it.

## Execution and local outputs

The current campaign commands require explicit `campaign_authority` and the
private construction/runtime inputs named by their contract. They refuse execution
when those requirements are absent; a historical runtime declaration does not
provide authority. Metadata inspection remains available. Delivery exports are
confined to the ignored `.neurobench/exports/` directory and are local generated
artifacts, not new benchmark registrations.

## Tests and specialized authoring

Framework tests are in `tests/framework/`, maintenance tests in
`tests/maintenance/`, and source-package controls beside their implementations.
Run the affected checks and retain failures as well as passes. See
[contributing](../CONTRIBUTING.md) for the normal verification commands.

The [isolated source queue](development/source-queue.md) is a specialized local
construction workflow. It does not publish source automatically. Private build,
agent and archive histories are excluded from public pushes.

The original examples have their own [instructions](../examples/original-three/README.md).
[Archived public branches](provenance/git/BRANCH_ARCHIVE_20261116.md) retain their
recorded recovery mapping; branch counts are not benchmark counts.
