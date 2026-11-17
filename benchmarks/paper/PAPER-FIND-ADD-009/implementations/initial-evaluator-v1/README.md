# Voice-synthesis feature evaluator

This standard-library Python package computes two concrete endpoints for `PAPER-FIND-ADD-009`: speech-only, DTW-aligned mean Pearson correlation across 40 Mel bands, and paired-sentence WER/PER with a median over seven listeners. It audits the complete declared test population, matched methods and session/trial exposure. It neither trains a decoder nor generates speech. Scientific qualification remains unknown.

Run from the repository root:

```sh
python3 -m unittest discover -s benchmarks/paper/PAPER-FIND-ADD-009/implementations/initial-evaluator-v1/tests -v
python3 benchmarks/paper/PAPER-FIND-ADD-009/implementations/initial-evaluator-v1/evaluator.py acoustic --plan manifest.json --reference operator-reference.json --prediction submission.json --output score.json
python3 benchmarks/paper/PAPER-FIND-ADD-009/implementations/initial-evaluator-v1/evaluator.py transcriptions --plan listening-plan.json --reference operator-tokens.json --prediction listener-tokens.json --output listening-score.json
```

Reference files belong on the operator side. This process is an offline scorer, not an isolation sandbox: do not give a contestant the reference file, operator command line or directory. Output includes input-byte SHA-256 receipts, qualification holds and denominator counts; it does not include target features or target tokens. Per-band and per-listener results are assessment outputs and need their own release policy.

See [the interface and scientific scope](../../docs/initial-evaluator-v1.md) and [source provenance](provenance.json). Tests construct all their data locally and run no neural model or speech model.
