# Working in this fork

## Branches and pull requests

The owned repository is `Donglomur/brain-researcher-benchmark`. Its default and
integration branch is `publish/neuroscience-200`. The preserved `master` branch
retains the original upstream history. Work in this fork does not change
`brain-researcher/brain-researcher-benchmark` without a separate upstream PR.

```sh
git clone --branch publish/neuroscience-200 --single-branch https://github.com/Donglomur/brain-researcher-benchmark.git
cd brain-researcher-benchmark
git switch -c feature/describe-the-change
# Edit the relevant source and run its checks.
git add path/to/changed-file
git commit -m "Describe the resulting behavior"
git push -u origin HEAD
gh pr create --repo Donglomur/brain-researcher-benchmark \
  --base publish/neuroscience-200 --head feature/describe-the-change
```

Verify the remote URL in existing clones: some authoring checkouts use `origin`
for upstream. Review the exact diff and complete CI before merging. The fork
automatically deletes merged feature branches; local branches can be removed
once their work is merged and no worktree or unfinished work depends on them.

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
