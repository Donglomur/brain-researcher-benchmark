# Synapse elimination: processed-input evaluator

This package derives continuous binary-event rates and local coactivity within 10 μm of dendritic arc distance, maps consecutive structural assessments to explicit retained/eliminated/censored outcomes, and evaluates fixed competing predictors with leave-one-mouse-out fitting and calibration. All repeated spines and dendrites from a mouse stay in the same fold.

Dependencies: an existing Python 3 environment with NumPy. From the repository root:

```sh
python3 benchmarks/paper/PAPER-FIND-REP-011/implementations/initial-evaluator-v1/evaluator.py INPUT.json OUTPUT.json
```

`OUTPUT.json` must not already exist. `example_control.json` supplies a generated engineering input for this command; it is not empirical data or a scientific reference.

The processed-input interface assumes complete continuous activity traces and independently adjudicated structural identities. Native archive conversion, authentic cohort validation, original mixed-effects/spatial/timing analyses, protected replay and scientific qualification remain unresolved. The fixed prediction policy operates on a retrospectively adjudicated cohort; it is not a survival model or causal analysis.

See [the complete input contract, calculations, validation and limits](../../docs/initial-evaluator-v1.md).
