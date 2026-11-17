# Paired MAE arithmetic successor

This task-local component preserves NEURAL-095's paired endpoint,
`mean(abs(cue - tp) - abs(neural - tp))`, over all 258 query trials, its 40
condition groups and eight contexts. It replaces only the two functions in
the predecessor [paired.py](../neural-095-four-cell/paired.py). It is not yet
selected by the registered scorer or protected runtime.

The predecessor first rounds both absolute errors to binary64 and then
subtracts them. For a generated target of 1000 ms, cue prediction 0 ms and
neural prediction 1e-14 ms, it returns zero despite the paired expression being
1e-14 ms. Dividing each paired term before summation can also underflow a
representable subnormal mean to zero. These are arithmetic counterexamples,
not scientifically meaningful neural gains.

The successor evaluates the same expression using exact rational values of
the supplied floats and rounds each final mean once. The context macro uses
the exact context means before its final rounding. No prediction is adjusted,
and this cannot recover measurement precision absent from the data. It retains
the existing refusal of nonfinite or overflowing individual residuals and the
64-ULP consistency check against separately rounded arm scores. The consistency
envelope is neither a scientific threshold nor an uncertainty interval.

`pair_difference` and `verify_paired_arithmetic` keep the predecessor's callable
interface. The caller must still perform all four public captures, exact ID
alignment and trusted private loading. Integration must explicitly bind this
module into the scorer and revise its source pins; predecessor packages and
past scores remain unchanged. The generated test exercises that binding through
the existing complete four-cell `evaluate` path, including shuffled IDs and an
invalid last submission that must prevent reference/target access.

The controls use generated arrays only and an independent 1200-digit Decimal
oracle for extreme finite values, unequal group sizes, signs and macro means.
Run `test_paired.py` with the existing NumPy environment through the authorized
shared test pool. No authentic recording, reference score, old prediction,
candidate fit, downloaded payload or model trial is needed.

The scientific source remains the [Sohn–Jazayeri task](https://doi.org/10.1016/j.neuron.2019.06.012)
and [DANDI 000130](https://dandiarchive.org/dandiset/000130). This repair changes
no source definition, observation window, released `tp` target, split, units or
access mode. Frozen-program performance remains a distinct tool/model outcome;
native interpretation and actual adaptive investigation remain undelivered.
Selected-runtime authentic numerical qualification, participant isolation and
matched-method evaluation remain unresolved.
