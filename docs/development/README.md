# Source organization and development

Start with [contributing](../../CONTRIBUTING.md) and the [fork workflow](../DEVELOPMENT.md).

- `benchmarks/<track>/<ID>/task.json` is the task definition.
- Task-specific packages live in that task's `implementations/`. The
  [shared-source directory](../../benchmarks/shared/README.md) includes multi-task
  programmes, related-only sources and families without an assigned task owner.
- `benchmarks/registry.json` declares ownership and source relationships.
- `src/neurobench/` contains generic framework modules; `scripts/` contains public
  commands and explicit maintenance entry points.
- `tests/framework/` and `tests/maintenance/` hold common tests. Implementation
  controls remain with their source packages.

## Checks

```sh
python3 -I -S -B scripts/catalog.py --check
python3 -I -S -B scripts/check_navigation.py
python3 -I -S -B scripts/check_repository.py
python3 -I -S -B scripts/check_source_integrity.py
python3 -I -S -B -m unittest discover -s tests/framework -v
```

[Repository ownership and source integrity](source-integrity.md) are separate checks:
the repository checker covers declared artifact ownership and layout, while the
source-integrity checker verifies recorded pins for four enrolled bundles. Neither establishes
scientific or execution qualification.
Run the affected package's checks and preserve relevant negative results.

## Specialized workflows

- [Curation contracts](../curation/README.md): artifact schemas, rubric and bounded
  worker instructions for scientific intake.
- [Isolated source queue](source-queue.md): local reviewed commits and serial
  integration for a separate construction checkout.
- [Historical records and relocation](../provenance/README.md): preserve original
  identities while documenting current paths and source changes.

[Historical reconstruction builders](../../scripts/maintenance/README.md) require `--construction-root` for their
original-layout inputs and `--output-directory` for a separate staging directory
outside the public repository. They do not regenerate current task definitions
or overwrite frozen provenance. Do not present a missing private dependency as a
public runtime, fetch unselected data to satisfy a check, or copy private build
histories into the public fork.
