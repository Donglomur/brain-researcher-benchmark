# FIND025 submission and comparison contract

This package makes the two claim families in PAPER-FIND-025 concrete: DR/WC null/potent population decomposition and projections, plus choice/context decoding, movement prediction and fixed/randomized-delay controls. It provides a submission validator and a descriptive comparison reporter. It does not execute the original neuroscience analyses or establish a paper reproduction result.

Start with [CONTRACT.md](CONTRACT.md). The sixteen obligation names are output groups within one existing assignment, not sixteen benchmarks. [pending_plan.json](pending_plan.json) intentionally leaves the original cohort/condition/support and protected-protocol mappings unresolved. Its empty assignments produce an incomplete report, not a successful benchmark.

## Contents

- `find025_contract.py` validates operator plans, candidate artifact declarations and separate evaluator score records, retaining every assigned missing or failed case.
- `operator_plan.schema.json` and `submission.schema.json` describe JSON shapes. Python additionally enforces cross-field identity, coverage, access and comparison rules.
- `metric_primitives.py` contains independently authored arithmetic on already-adjudicated operands. It is not a full array scorer, cohort constructor or target loader.
- `invented_fixture.py` and `test_find025_contract.py` provide the complete 50-method invented interface suite. Their symbolic animals, sessions, artifacts and scores are engineering fixtures, never substitute scientific data.

Code-version reconstruction, final-paper reproduction and protected improvement are separate lanes. Historical delay-trial-mean squared correlation, prospective paired-vector squared correlation and signed variance explained have distinct metric IDs. Paper reproduction remains held. Protected comparisons require common declared target/support and prediction artifacts, grouped protocol references, disclosed parameter intake, comparable baseline reruns and matched resources. Equality of IDs/hashes is declaration consistency; it does not verify provenance, actual fitting, artifact content, target custody or execution.

No heterogeneous aggregate or numeric paper pass is produced. The reporter always records execution and scientific qualification as false. Meaningful superiority, inference, actual fold/vector definitions and final-paper correspondence remain scientific work.

## Use with Python 3.11

From the repository root, using only the Python standard library:

```sh
python3.11 -I -S -B -m unittest discover -s benchmarks/scientific_contracts/find025 -p test_find025_contract.py
```

Ordinary readable source files and directories suffice; no executable bit, dependency installation, dataset, model, network or MATLAB runtime is required. The command tests invented declarations and arithmetic. It does not run a scientific benchmark.

The Python API is `validate_plan(plan)`, `validate_submission(plan, submission)` and `report(plan, submissions, evaluator_records)`. Inputs are decoded bounded JSON objects. Artifact descriptors are never followed as filesystem paths, and candidate self-scores are not accepted in submissions. The integration operator supplies and validates the authentic plan and separate evaluator records before any real use.

## Provenance and limits

The scientific assignment concerns [Separating cognitive and motor processes in the behaving mouse](https://doi.org/10.1038/s41593-024-01859-1). Its inspected source identities are pinned in the module and pending plan: Git commit0038351ee773c2aee8758b3d74b0c9bf2991f543 and the code envelope in [Zenodo record13941415](https://zenodo.org/records/13941415). Source/paper cohort counts, metric/time/support differences and unresolved dispatch/repair decisions remain documented in the contract. No source-version mismatch is silently repaired.

Seven operative source/schema/contract/template/fixture files are byte-exact copies of the accepted private construction. The test file has one reviewed literal change: the protected historical-fit test now declares historical_full_session, preserving its noncomparability check without contradicting the separate precomputed-parameter intake rule. Dedicated tests retain precomputed-intake rejection. All 50 methods and all production/schema bytes are unchanged; this README is packaging documentation. Historical validation/failure statements in CONTRACT.md refer to preserved private source-construction evidence, which is not bundled here. Publication portability checks are a separate validation stage; they grant no scientific credit.

This package contains independently authored benchmark components, including the exact accepted independent metric primitives. It contains no upstream MATLAB implementation, opaque archive, rank CSV, original arrays, saved reference outputs, model weights, private receipts or review transcripts. Original paper, code and data rights remain separate; these files grant no access or redistribution rights for those inputs. No task counts, installed scientific procedures or qualification states change by publishing this source.
