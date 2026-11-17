# Study description binding validator

This stdlib-only tool checks a **description** of the two planned neuroscience comparisons. It does not execute a study, read referenced artifacts, verify scientific validity, enforce budgets, authenticate reviewers or qualify a benchmark. A successful exit is `description_consistent_not_qualified` and grants no execution authority. It registers zero tasks.

The existing `docs/neuroscience-benchmarks/study-design-v1/paper.template.json` and `neural.template.json` remain unchanged, unbound planning drafts. This component accepts a normalized companion document (`neurobench.paired-study-binding.v1`), not a filled copy of either draft. The exact source template hashes are pinned in the validator and [FORMAT.md](FORMAT.md). This makes joins and denominators explicit; a template hash alone does not verify the referenced template or policies.

## Generated demonstration and checks

From this component directory, using Python 3.11 or later on Linux or macOS (POSIX). The loader uses POSIX file-open flags; native Windows is not supported:

```sh
python3 -I -S -B generated_examples.py --output /tmp/neurobench-generated-study-controls
python3 -I -S -B validate_study.py /tmp/neurobench-generated-study-controls/paper.generated.json
python3 -I -S -B validate_study.py /tmp/neurobench-generated-study-controls/neural.generated.json
python3 -I -S -B test_validate_study.py
```

The output directory must not already exist. The generator invents both bindings, all identities, artifact pins, review declarations, thresholds, budgets and policies. **These are test inputs, not scientific defaults or real assignments.** It adds no empirical evidence. Generated cases exist only inside the generated JSON. The source tests also use invented metadata, including refusal cases; no model or neural data is used.

For an independently prepared description, run `python3 -I -S -B validate_study.py YOUR_BINDING.json`. Exit 0 means the description meets this component's fixed contract; exit 2 means rejection, with a reason in JSON on stderr. Supply only metadata you are authorized to inspect. The validator opens exactly the supplied regular JSON file (maximum 4 MiB, final-component symlinks rejected), not any artifact locator. It does not fetch papers, data, code, receipts, schemas or policies. The metadata may contain private identifiers; it is not a public report by default.

## What is checked

- Paper: the complete `paper_data` and `paper_data_code` comparison through reproduction, improvement development and improvement confirmation; equal declared phase allowances, explicit sanitized official-code access and separate locked improvement claims.
- Neural: the four program/investigator × numerical/specialist cells, including a primary investigator-mode contrast; equal development and numerical allowances, explicit additional live LLM allowance, no assessment LLM budget for fixed programs, and locked assessment policies.
- Exact task revisions and canonical inline case/assignment pins; complete task × phase × model/scaffold × repeat × arm assignments; matched pairs, case rosters, declared condition order, independent units and crossed dependence membership.
- Primary/exploratory estimands, endpoint directions and effect thresholds, declared uncertainty/multiplicity and source-family weighting; per-endpoint task/phase applicability and all-applicable-pair failure denominators, plus explicit retry/missingness rules. The contrast-wide pair count is an operational total; unrelated tasks do not enter an endpoint's denominator.
- Exposure inventories, protected-confirmation overlap declarations, prospective selection and fixed/sequential stopping, cost and comparator policy references.

## Limits

The validator checks the presence and consistency of policy references and declarations, not whether those policies are sensible, enforceable, truthful, prospective or independently reviewed. Only the embedded case roster and assignment bytes are recomputed. All external artifact hashes, access restrictions, model identities, budget measurements, exposure histories and review identities remain unverified. An arbitrary but internally consistent policy can pass; expert review, artifact verification, execution controls and an actual frozen study are still required elsewhere.

Version 1 intentionally accepts only complete paired matrices and the two stated designs. It rejects partial assignment samples, missing phase rosters, omitted factorial cells and raw draft templates. Continuous endpoint missingness requires a declared policy rather than a fabricated zero; endpoint scales remain separate. It does not establish novelty, superiority, statistical power, task independence or submission readiness. Direct neural signal understanding and RL environments require separate designs and are not selected here. [FORMAT.md](FORMAT.md) describes fields and canonicalization; [binding.schema.json](binding.schema.json) describes shape. Use the Python validator for the additional cross-document joins.
