# Working in this fork

## Repository, branch and pull request

- **Upstream repository:** `brain-researcher/brain-researcher-benchmark`.
- **Our fork:** `Donglomur/brain-researcher-benchmark`, an independently owned GitHub repository.
- **Default and integration branch:** `publish/neuroscience-200`, containing the neuroscience work.
- **Preserved upstream branch:** `master`, retained with its original history.
- **Feature branch:** a temporary place to commit one coherent change.
- **Pull request:** the review and CI record for merging that branch into the integration branch.

Branches and PRs work together. Merging a PR adds its changes to the base branch;
deleting its completed feature branch does not remove the merged commits or PR.
Work in this fork does not change upstream unless a separate upstream PR is made
and accepted.

## Make a change

```sh
git clone --branch publish/neuroscience-200 --single-branch https://github.com/Donglomur/brain-researcher-benchmark.git
cd brain-researcher-benchmark
git switch -c feature/describe-the-change
# Edit and run the checks relevant to the change.
git add path/to/changed-file
git commit -m "Describe the resulting behavior"
git push -u origin HEAD
gh pr create --repo Donglomur/brain-researcher-benchmark \
  --base publish/neuroscience-200 --head feature/describe-the-change
```

Review the exact diff and complete CI before merging. Use small coherent PRs and
avoid branches that mix unrelated task families. GitHub automatically deletes
completed PR branches in this fork. Remove local branches only after their work
is merged and no worktree or unfinished work depends on them.

For existing clones, verify the remote URL before pushing: some authoring checkouts
use `origin` for upstream. Private construction histories contain materials that
must not be published; their commits are not a safe source for a blanket push or
cherry-pick. Publish only the reviewed public source subset on this fork's history.

## Catalog and layout changes

The public catalog and task homes under `benchmarks/paper/<ID>/` and
`benchmarks/neural/<ID>/` are generated from the checked-in canonical specifications
and expansion registries. Each track index groups its original 100 separately
from expansion drafts. Task homes link to existing definitions and implementations;
they do not relocate or duplicate scientific source. Do not edit generated guides
by hand. The generator does not read the private execution ledger. Regenerate it
with `python3 tools/build_public_catalog.py`, then check the generated diff and run
`python3 tools/build_public_catalog.py --check`.

Keep task IDs stable. Moving a package can break manifest paths, source hashes,
container build contexts and command documentation; update and verify those
consumers together. The original three Harbor examples live under
`examples/original-three/`. Their legacy bare IDs still resolve through
`tools/run_task.sh`. Their inherited planning and result documents are grouped in
[upstream history](../examples/original-three/upstream-history/README.md).

Historical source manifests describe their recorded revisions. Do not rewrite them
merely to make a new layout appear historically identical. Record a new selection
when source or scientific contracts change.

## Archived and retained branches

The [November 16 branch archive](history/BRANCH_ARCHIVE_20261116.md) preserves
153 unfinished or legacy branch tips as tags, with exact recovery commands.
Another 48 task branches remain because they back open upstream PRs. Branch count
is not a benchmark count, and an archived change is not an accepted change.
