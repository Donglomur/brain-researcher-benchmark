# Decision-times export evaluator

This standalone Python standard-library component evaluates five-event point-time exports, six stage durations, contrast effects, psychophysical-law parameters, stimulus-aligned ERP curves and participant-held-out likelihood exports. It is an engineering construction component with scientific qualification unknown. It does not fit HMP or reproduce the paper from EEG.

Read [the interface and source scope](../../docs/initial-evaluator-v1.md) before use.

Run from the repository root:

```sh
cd benchmarks/paper/PAPER-paper-signal-add-019/implementations/initial-evaluator-v1
python3 evaluator.py input.json --output result.json
python3 -B -m unittest discover -s tests -v
```

Only generated controls are included. No empirical observations, protected reference, external code, model weights or data are bundled. No third-party packages are required.
