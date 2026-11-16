# Contributing

This fork develops paper-reproduction/improvement and neural-data-understanding
benchmarks. Open PRs against **`publish/neuroscience-200` in
`Donglomur/brain-researcher-benchmark`**. See [the development workflow](docs/DEVELOPMENT.md)
for commands, branch cleanup and review expectations.

## What a contribution should establish

1. State the scientific question, original paper/data/code provenance and exact endpoint.
2. Define the complete case population, splits, permitted observations, tool/code access,
   metric, comparator and reproduction/improvement conditions.
3. Supply documented source with positive and relevant adversarial controls. Preserve
   failed or negative outcomes and distinguish generated checks from authentic-data runs.
4. Document external inputs, licenses, runtime/resource requirements and unresolved holds.
   Keep protected answers, private records and credentials out of the public history.
5. Update the source definitions and regenerate the public catalog when they change.

A source contribution can be merged before scientific qualification when its limits
are explicit. Calling a benchmark finished requires evidence for the complete
stated task, usable inputs/runtime, functioning evaluation and independent review.
Metadata counts and green software CI alone do not meet that standard.

## Checks

From the repository root, with Python 3.11 or later:

```sh
python3 tools/build_public_catalog.py --check
python3 tools/check_public_navigation.py
python3 -I -S -B -m unittest discover -s tests -p 'test_public_catalog.py' -v
```

Run the affected component's documented checks as well. Do not alter its scientific
scope or its evidence pins just to make a failing check pass. Explain the concrete
change, tests actually run and any remaining limits in the PR.

The [original example contribution guide](docs/original-examples-contributing.md)
retains the upstream task format and uncued-judgment criteria. Those example-specific
criteria are separate from this programme's broader two-track evaluation design.
