# NEURAL-065 V1 typed-character evaluator

Evaluates pinned Brain2Qwerty V1 typed-button predictions using sentence CER averaged within each resolved person, then equally across people. Includes alias/session/template checks, supplied alignment-pair accounting, an allowlisted query export, complete neural-only and language-only arms, and paired person uncertainty. Optional fixed-LM results remain separate.

Requires an existing Python 3 runtime and only the standard library. Run from repository root:

```sh
python3 -B -m unittest discover -s benchmarks/neural/NEURAL-065/implementations/initial-evaluator-v1/tests -v
python3 -B benchmarks/neural/NEURAL-065/implementations/initial-evaluator-v1/evaluator.py queries private_packet.json > query_manifest.json
python3 -B benchmarks/neural/NEURAL-065/implementations/initial-evaluator-v1/evaluator.py evaluate private_packet.json neural.json language_only.json > private_report.json
```

No neural payloads or models are bundled. Manifest consistency does not establish authentic source completeness, raw DTW reconstruction, model exposure, competent reference performance, or protected evaluation. Typed-button targets differ from the paper's intended-key analyses; native metric parity is unverified. V2 is excluded. Scientific qualification remains unknown.

See the [complete interface, provenance, prospective policies, and remaining holds](../../docs/initial-evaluator-v1.md). Generated examples and engineering controls are in `tests/test_evaluator.py`.
