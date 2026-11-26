# Contributing

Contributions develop the paper-research and neural-data tracks in
[Donglomur/brain-researcher-benchmark](https://github.com/Donglomur/brain-researcher-benchmark).
Open PRs against **`publish/neuroscience-200`**. The [development guide](docs/DEVELOPMENT.md)
explains branches, review and source maintenance.

## One change per pull request

Keep one complete, independent change in one commit and one PR. Include the
regression tests, documentation and current source bindings needed for that change
to work and be reviewed. Separate unrelated work, but keep coupled fixes together;
do not split a complete change or repeat merged work just to increase PR counts.

A separately selected new source-package capability may use exactly two ordinary
commits in its one complete PR when registration needs a commit that already
contains the package. Snapshot A must have the verified actual preceding default
as its parent and contain the exact reviewed package. Registration B must have A
as its parent, preserve every package byte, and complete the registration, tests,
CI, documentation and current bindings, with `source_commit` and linked
`evidence.commit` naming actual A. Review the complete feature, ordered history
and containing-file identities before pushing both commits together once. Do not
push an intermediate snapshot, open an intermediate PR or dispatch CI for an
incomplete change. This exception requires separate selection; it does not extend
any separately scoped publication-helper authorization. All serial review,
identity and check gates remain in force.

Independent work can be prepared in parallel. In this serial delivery queue, keep
only one open, unmerged PR at a time; this limit does not restrict unrelated
contributors' PRs. After a normal merge and immediate verification of the actual
default commit, tree and parents, the next branch and PR may start while the
preceding merge's post-merge checks run. An ordinary queued change must wait to
merge until those checks and its own required checks and review pass. A failed
default may advance only through the separately selected, independently reviewed
repair procedure in the fork workflow; ordinary queued changes resume only after
the repaired default passes its complete post-merge gate. Follow the
[fork workflow](docs/DEVELOPMENT.md#branches-and-pull-requests) and use the
[PR template](.github/PULL_REQUEST_TEMPLATE.md) to describe the problem, result,
validation actually run and remaining limitations.

## Scientific contribution

A task should state its scientific question, paper/data/code provenance, complete
case population, splits, permitted observations, metric and comparison conditions.
Separate historical reproduction from prospective improvement. Document the exact
inputs, environment, resource requirements, licenses and unresolved limitations.

Supply implementation source with meaningful positive and adversarial checks.
Preserve failed or negative outcomes and distinguish generated software controls
from authentic-data and model runs. A source contribution can be accepted with
explicit limits; whole-task qualification needs evidence for the complete stated
contract, functioning evaluation and independent review.

## Where changes belong

- Put task definitions and task-specific source in `benchmarks/paper/<ID>/` or
  `benchmarks/neural/<ID>/`. Keep implementation packages with closed inventories
  intact, and give alternate implementations explicit roles.
- Put scientific code used by several tasks in `benchmarks/shared/`. This directory
  also retains related-only sources and families without an assigned task owner;
  see the [shared-source index](benchmarks/shared/README.md). Record the exact
  relationship or unresolved ownership in `benchmarks/registry.json`.
- Put task-agnostic framework code in `src/neurobench/`; use `scripts/` for commands.
- Put current user, scientific and contributor guides in `docs/`. Retained
  publication records belong in `docs/provenance/`; only proven inactive material
  belongs in `archive/`.

Keep IDs and scientific scope stable unless the PR explicitly proposes a reviewed
scientific change. Update the registry and current source bindings when code moves.
Historical source manifests retain their original paths and hashes; see
[provenance](docs/provenance/README.md) before changing one.

## Validation

From the repository root, with Python 3.11 or later:

```sh
python3 -I -S -B scripts/catalog.py --check
python3 -I -S -B scripts/check_navigation.py
python3 -I -S -B scripts/check_repository.py
python3 -I -S -B scripts/check_source_integrity.py
python3 -I -S -B -m unittest discover -s tests/framework -v
```

Run the affected implementation's documented checks as well. Maintenance tests
live in `tests/maintenance/`; scientific source-package controls stay with their
packages. Do not change scientific populations, metrics or evidence merely to
make a check pass. The PR should state the resulting behavior, tests actually run,
and remaining limits.

Public commits must exclude protected references, private records, credentials and
unpublished working histories. The inherited examples retain their own
[contribution guide](examples/original-three/CONTRIBUTING.md).
