# Portable assessment of four spine associations

This component assesses a completed JSON artifact for the existing
`PAPER-FIND-REP-012` finite reconstruction task. It can be copied to an ordinary
directory and used with Python 3.11 or later, using only the standard library.
The numerical core, output schema, I/O facade and scientific conventions are
unchanged from the accepted local finite task. No dataset or private answer is
included. Four endpoints belong to one benchmark.

The separate all-18-family, 294-callsite released-method programme is outside
this component. This package does not change that programme, canonical routing,
or any readiness declaration. It is an evaluator component, not a complete
Terminal-Bench or Harbor task, candidate runner, or calibrated model study.

## Operator use

Select and record the approved input-manifest hash and private reference length
and SHA-256 independently of submissions. Keep the reference and this invocation
under evaluator control, after the candidate process has ended. A candidate may
not choose its own reference. The command binds bytes to that operator selection;
it cannot establish whether the selected reference is scientifically correct.

```sh
python3 -I -S -B /path/to/component/grade.py \
  --submission /evaluation/candidate/result.json \
  --reference /evaluation/private/reference.json \
  --reference-bytes APPROVED_REFERENCE_BYTES \
  --reference-sha256 APPROVED_REFERENCE_SHA256 \
  --input-manifest-sha256 APPROVED_INPUT_MANIFEST_SHA256 \
  --output /evaluation/grades/new-grade.json
```

Replace all uppercase placeholders with independently approved identities. Both
inputs must be ordinary single-link files with no symlink ancestry and at most
32 KiB. The submission is validated before the reference is opened. The output
parent must already exist and the output must not exist; publication never
replaces an existing result. The complete grade is at most 128 KiB, with at most
another 128 KiB temporary copy during publication. Grade output is operator
material: it contains detailed errors and must not become repeated held-out
feedback without an explicit evaluation policy.

Exit status is 0 for a scored artifact (including inaccurate or abstained
answers), 2 for invalid or unsupported submissions, and 1 for operator/I/O
failure. Malformed references and pin mismatches never become candidate scores.
Only trusted pinned source is imported; submissions remain JSON. This is a
serialized, closed-producer filesystem interface. It is not a hostile concurrent
filesystem sandbox or startup-inclusive execution limit. The enclosing evaluator
must impose its own complete resource and privacy boundaries.

The original `artifact_io.py` facade is retained unchanged as a dependency.
Invoke `grade.py`: direct use of the old facade does not enforce an approved
reference pin. `SOURCE_PINS.json` authenticates the inherited component bodies;
it is not a data/reference approval file.

## Scientific interpretation

See `TASK.md`, `DATA_FORMAT.md`, `RECONSTRUCTION_ASSUMPTIONS.md`,
`OUTPUT_SCHEMA.json` and `PUBLIC_SCORING.md`. This is the exposed Version 2
processed-release reconstruction with four pooled correlations and diagnostic
supports/moments. Three caption p-value discrepancies remain unresolved. Nominal
pooled-spine p values are not mouse-level inference. Exact summary agreement
does not prove fresh computation, input dependence, whole-paper reproduction,
paired paper/code benefits, causal findings or improvement over the paper.

Data redistribution, complete paper/Methods access, competent agent baselines,
protected evaluation, native harness qualification and difficulty calibration
remain separate requirements. No authentic data, reference, fitting, model
campaign or protected evaluation is run by constructing this package.

Run the synthetic adapter controls with:

```sh
python3 -I -S -B /path/to/component/test_grade.py
```

All fixture values and mouse labels in those controls are invented.
