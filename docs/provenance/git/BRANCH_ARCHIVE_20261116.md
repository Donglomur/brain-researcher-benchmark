# Branch archive: November 16, 2026

The neuroscience integration branch is `publish/neuroscience-200`; the fork's
default branch remains `master`. This cleanup preserves unfinished work without
merging it into the neuroscience suite.

The [exact recovery index](BRANCH_ARCHIVE_20261116.json) records 153 former
branch names, their commit IDs and matching `archive/2026-11-16/…` tags. Tags
retain the complete history reachable from each tip. Archival does **not** mean
the changes were merged, reviewed for scientific validity, or counted among the
234 neuroscience drafts.

The retained branch list records 48 source branches for open upstream pull
requests, with links to those reviews, plus the two core branches. Those PR
branches remain because the original repository's reviews depend on them.
The PR states are a dated snapshot, not a continuously updated dashboard.

## Recover archived work

Use the exact tag from the JSON index. Fetching an archive does not merge it:

```sh
git fetch https://github.com/Donglomur/brain-researcher-benchmark.git   refs/tags/archive/2026-11-16/qa/all-8-tasks:refs/tags/archive/2026-11-16/qa/all-8-tasks
git switch -c review/legacy-qa archive/2026-11-16/qa/all-8-tasks
```

To propose useful work from an archive, inspect its source, dependencies and
original review first. Create a focused branch from the current neuroscience
integration branch and open a PR in this fork. Avoid wholesale merges: archived
work may include old layouts, data artifacts, unfinished implementations or
scientific assumptions that differ from the current suite.

## Preservation procedure

All 153 tags were created at the exact pre-existing public branch tips in the
same atomic Git push that removed those branch references. Every branch deletion
used an expected-commit lease; every tag creation required that tag to be absent.
A competing ref update would reject the batch. Current open PR associations in
this fork and upstream were checked immediately before the operation.

The two core branches and all 48 active upstream PR heads were verified unchanged
afterward. No private authoring history was pushed, and no upstream repository
or default-branch setting was changed. The 198 branches already removed during
the earlier cleanup had been proved merged or ancestors of the integration
branch; this archive separately preserves work without that proof.
