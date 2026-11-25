# Paired contextual-program comparison

This additive trusted-operator helper compares two frozen contextual submissions on the same complete declared NEURAL-072 panel. Both use one authenticated evaluator-owned nuisance/lexical reference, one protocol, the same ordered targets and the same protected response arrays. It fills the paired-assessment gap left by independent single-submission reports.

The signed comparison is candidate minus baseline contextual R², equivalently the difference between their contextual-minus-fixed-lexical effects because the lexical reference is common. It pools SSE and within-run-centered SST across each listener/family's runs per target, averages targets, then families within listener, then listeners. It preserves adverse and zero effects and retains both full predecessor reports. The crossed listener × story-family bootstrap is applied to paired cell differences using shared cluster weights. Subtracting separately computed marginal interval endpoints would not provide this interval. More than 10% empty resampling draws rejects the paired interval, including for small replicate counts.

Use an existing NumPy environment from this directory:

```sh
python -B compare.py --protocol protocol.json --cases cases.json \
  --baseline baseline_contextual.json --candidate candidate_contextual.json \
  --reference fixed_reference.json --expected-reference-sha256 OPERATOR_RETAINED_SHA256 \
  --targets protected_test_targets.json --output paired_report.json
```

Both submissions use exactly the contextual-only schema documented in `../fixed-comparator-v2/README.md`. Missing runs, extra runs, wrong row/target dimensions, mismatched case/protocol identities and comparator injection are rejected for either submission before the CLI opens protected targets. The output cannot overwrite an existing file. All input byte hashes and both source pins are recorded. The helper authenticates and executes the fixed-comparator-v2 source (`ef77dccd5d8bae3edcb6c8a4ad41221f531b792ceec7af98c42910faceebd854`), which retains the original pinned numerical recipe and enforces the exact empty-draw limit for both single-submission reports and the paired interval.

This is an assessment tool for contextual predictions, not a direct-observation task or a participant runtime. The operator must independently enforce prospective submission freezing, protected reference custody, identical permitted inputs, candidate capacity, resource matching and no hidden-response feedback. Authentic Narratives population membership, the exact NEURAL-071 case mapping, native preparation, clock/feature lineage, comparator competence and the existing contextual-versus-lexical nesting issue remain unresolved. Complete support refers only to the externally declared frozen cases. Reports always retain `scientific_qualified: false` and `submission_ready: false`; generated controls do not measure neural understanding.

Generated affected controls:

```sh
python -B -m unittest discover -s tests -p 'test_*.py' -v
```
