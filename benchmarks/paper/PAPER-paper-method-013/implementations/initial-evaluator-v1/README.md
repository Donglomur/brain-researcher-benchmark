# DeepCaImX assembled-output evaluator

Scores final ROI masks and calcium traces for all ten fixed recordings in `PAPER-paper-method-013`: strict IoU > 0.5 segmentation precision/recall/F1, Pearson correlations on reference neurons detected by every compared method, and paired runtime comparisons. It also emits the fixed tile geometry with padding identified.

Requires Python 3 and NumPy. From this directory:

```sh
python3 evaluator.py score --reference /operator/reference.json --submission /candidate/submission.json --output /operator/new-report.json
python3 evaluator.py tile-layout --output /operator/new-layout.json
```

Inputs are separately supplied, SHA-256-bound reference and submission manifests plus binary masks and finite traces in NPZ files. Outputs must be new files. See the [full interface, policies and examples](../../docs/initial-evaluator-v1.md).

This is a post-assembly numerical evaluator. It does not run a model, reconstruct native assembly, authenticate references, or establish electrical fidelity. Native execution, frame-index mapping, checkpoint identity, donor/tuning partitions, rights and protected-reference admission remain held. Scientific qualification is unknown.

The evaluator hashes and parses each manifest from one captured byte sequence. It also hashes and decodes each NPZ from the same captured bytes, rejects duplicate array members, and reports the captured manifest identities. This binds the assessed content to its supplied hashes; it does not attest provenance or provide filesystem isolation. NPZ decoding retains one compressed input snapshot in memory alongside its decoded arrays, so runtime admission must include that extra compressed input size.
