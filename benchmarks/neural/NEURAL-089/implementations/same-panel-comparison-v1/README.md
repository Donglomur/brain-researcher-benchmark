# Same-panel LibriBrain access-condition comparison

This additive operator scorer compares a complete restricted-observation answer
set with a complete frozen-program answer set on the same supplied NEURAL-089
query panel. The existing standalone scorer handles one submission. The native
programme's candidate/reference grader requires fit/seal/pointwise execution
closures and cannot represent a restricted-observation response as a native
programme role. This component supplies the missing paired assessment boundary;
it does not replace or bypass that programme's execution qualification.

The unchanged metric sources are copied from `scoring-role-separation-v2`, with
their original byte hashes in `SOURCE_BINDING.json`. Both submissions retain the
exact existing probability ABI: task/schema header and one 39-probability vector
for every opaque query ID. Every class remains in the macro-F1 denominator,
absent classes contribute zero, and the lowest index wins argmax ties. Original
90-run membership, native 88/1/1 partitions, 306-by-125 MEG windows, training-only
normalization and full-event eligibility are unchanged. A supplied panel must
still be independently bound to complete authentic preparation; a smaller
invented panel is useful only for software controls.

## Operator comparison declaration

`compare.py` requires a separate strict JSON declaration:

```json
{
  "schema_version": 1,
  "task_id": "NEURAL-089",
  "panel_sha256": "64 lowercase hexadecimal characters",
  "conditions": [
    {
      "access_condition": "restricted_observation",
      "submission_sha256": "SHA256 of exact restricted submission bytes",
      "query_observations_sha256": "SHA256 of frozen common query-information artifact",
      "labeled_calibration_sha256": "SHA256 of frozen common labeled-calibration artifact"
    },
    {
      "access_condition": "frozen_program",
      "submission_sha256": "SHA256 of exact programme submission bytes",
      "query_observations_sha256": "same common query-information SHA256",
      "labeled_calibration_sha256": "same common labeled-calibration SHA256"
    }
  ]
}
```

The example strings describe fields and are not valid hashes. The two information
artifacts must identify the complete permitted information, including class and
channel/time order, all eligible query windows and the complete allowed labeled
calibration context. The operator freezes these artifacts before participant
exposure and records the actual presentation and execution separately. If the
two conditions expose different information, use a separately named comparison;
this scorer refuses different declared information hashes. It does not open the
information artifacts or certify their contents, equality of actual exposure,
tool restrictions, compute budgets, source freeze or native closure. Thus matching
hash declarations establish only a declared information contract, never observed
same-information access. Presentation restrictions and programme qualification
remain separate missing runtime evidence.

Run with already qualified, operator-held outputs:

```sh
python compare.py --restricted restricted.json --program program.json \
  --panel panel.json --comparison comparison.json --targets targets.json \
  --targets-sha256 PRIVATE_TARGET_SHA256 --output new-result.json
```

All public/private file-role aliases are rejected before any input body is read.
The operator must keep paths stable; this is not a concurrent-mutation sandbox.
The panel and declarations are validated, then both exact submission hashes and
complete probability sets, before protected targets are opened. A missing,
duplicated, extra or malformed response in either condition leaves the whole
comparison unscored. Exit statuses are 0 scored, 2 invalid submission, 1 operator
error. Output creation is exclusive and inherits the existing bounded JSON I/O.

The result contains each original score and confusion matrix, restricted minus
programme macro-F1 and accuracy, 39 per-class F1 differences, and a paired
correctness table. These are descriptive finite-panel quantities. No independent
event confidence interval or significance test is added: there is one participant
and one held recording, with overlapping phoneme windows and possible narrative
overlap. No combined reward or success threshold is introduced.

`test_compare.py` uses six invented queries and hand-computable predictions to
exercise identity joins, score arithmetic, both-arm completeness, input-hash
substitution, unequal calibration/observation declarations, file-role aliases and
private-read ordering. No authentic recording, model, native candidate or online
API is run. This package adds source capability only; direct presentation,
complete authentic preparation, reference competence, native runtime feasibility,
equal actual exposure and scientific performance remain unestablished.
