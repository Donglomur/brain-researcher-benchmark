# NEURAL-015 initial evaluator

Executable, standard-library construction package for complete-cohort word-onset
grid scoring and source-informed clock alignment. It does not contain or execute
a neural model, native recording, transcript, media file, or scientific baseline.

See [the interface and scientific scope](../../docs/initial-evaluator-v1.md).
`provenance.json` records the exact contract and primary-source pins.

From the repository root:

```sh
python3 -m unittest discover -s benchmarks/neural/NEURAL-015/implementations/initial-evaluator-v1/tests -v
python3 benchmarks/neural/NEURAL-015/implementations/initial-evaluator-v1/evaluator.py --help
```

Every result is explicitly unadmitted; scientific qualification remains unknown.
