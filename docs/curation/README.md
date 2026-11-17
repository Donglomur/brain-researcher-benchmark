# Scientific curation contracts

These contracts define the artifacts and responsibilities of a bounded scientific
worker and its durable controller. They do not execute a study, grant data access
or certify benchmark readiness.

- [Contract guide](../../src/neurobench/curation/contracts/README.md).
- [JSON Schema](../../src/neurobench/curation/contracts/curation-contracts-v1.schema.json).
- [Canonical question-family rubric](../../src/neurobench/curation/contracts/evolvable-rubric-v1.md).
- [Worker contract](worker-contract.md).

The schema and rubric retain their normative identifiers and meanings. They live
with the framework's curation validator; the worker instructions describe how a
single assigned stage uses them. Application-discovered skills remain under
`.claude/skills/` and refer to these shared contracts.

From the repository root:

```sh
python3 -I -S -B scripts/validate_curation.py
```

A successful check establishes contract consistency. It does not establish that a
particular scientific claim, oracle, dataset, or submitted artifact is valid.
