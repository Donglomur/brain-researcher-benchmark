# Released geometry example: numerical reproduction component

The recovered author geometry example cannot supply the missing empirical
five-category decoder. Its binary classifier uses five-fold cross-validation
and the coefficients of its first fitted fold; the empirical Fig. 6 analysis
uses five-category, one-versus-one decoding with balanced 80/20 trial splits,
500 repetitions and session-specific greedy ensembles. The [source recovery
report](../../docs/decoder-source-recovery-v1.md) records that distinction and
the remaining empirical deliverable.

This component independently expresses two numerical parts of the released
geometry example: the simulation transform **given explicit random draws**, and
the pooled-covariance geometry **given fitted binary classifier coefficients**.
Neither function fits a model or creates a random realization. It adds an
executable partial reproduction component alongside the existing LFP/SU PAC
component. It does not complete reproduction of the original findings, bind an
improvement endpoint, or establish a native MATLAB rerun. The canonical task,
improvement contract, historical results and existing evaluator are unchanged.

## Source and exact scope

The source is [SBCAT-release-NWB at a25e8cc3](https://github.com/rutishauserlab/SBCAT-release-NWB/tree/a25e8cc3f61630a428f190381745257d4506f148).
Exact source file bytes, SHA-256 and Git blob identities are retained in
[source-evidence.json](source-evidence.json). Author implementation files remain
outside the repository; the numerical expressions here are independent.

`main_popGeometry_noiseCorrs.m` selects two neurons, one tuned neuron, two
categories, 200 trials per category, both common and signal-dependent noise,
noise-axis mode 2, and classifier mode 2. The generator corresponds to the
paper's illustrative geometry mechanism (Fig. 6f). Its exact published random
draws, MATLAB RNG state, fold assignments and historical fitted coefficients
have not been recovered. A newly supplied realization is not that historical
figure. The released example calls itself an example; its presence does not
establish full paper reproduction.

`geometry.py` preserves the mode-2 calculation: sample covariance over all
rows, including between-category variation; the leading covariance eigenvector
as noise axis; the acute subspace angle to the classifier normal; sample
standard deviations of projections in each category; and their arithmetic
mean. The projected precision is the source's square root of the sum of
squared normal projections divided by covariance eigenvalues. It has inverse
activity units. No z-scoring, covariance regularization, class centering, pooled
projection SD, or variance substitution is introduced.

The coefficient normal is obtained by normalizing `beta`, replacing the
source's randomized hyperplane-point/QR calculation. These represent the same
one-dimensional subspace where the source construction succeeds. Raw vector
signs and signed projections need not match, but the returned angle, standard
deviations and projected precision are sign invariant. This also defines the
normal when the first coefficient is zero, where the source divides by zero.
This algebraic repair is disclosed; native numerical parity is untested.

The source helper selects projection classes by row position, although its
other operations inspect labels. This implementation requires equal contiguous
class blocks (all category 0, then all category 1), matching the released
generator, and rejects reordered labels. It does not silently sort or remap a
recording. Singular covariance gives no projected-precision value; a tied
leading eigenvalue gives no unique-axis angle. Both conditions are reported
using a scale-dependent floating-point tolerance. The source instead divides
by zero or selects an arbitrary eigensolver axis; no finite repaired statistic
is presented as its output.

## Inputs and execution

Only NumPy and Python's standard library are needed. No dependency is installed
and no source or recording is downloaded by this component.

`replay_simulation(draws)` expects exactly these arrays:

| Field | Shape | Meaning |
|---|---|---|
| `sigma_uniform` | 2 × 2 | Supplied uniforms in [0,1); source SD is `2*u+1` |
| `independent_normal` | 2 × 200 × 2 | Category × trial × neuron standard-normal innovations |
| `signal_normal` | 2 × 200 | Trial innovations multiplied by category SDs 2 and 0.2, added to **both** neurons |
| `common_normal` | 400 | Trial innovations multiplied by SD 2, added to both neurons |
| `permutations` | 2 × 2 × 200 | Neuron × category × destination-trial source indices; each is an exact permutation of 0–199 |

Tuned-neuron means are 10 and 5; untuned-neuron means are zero. Negative
simulated values are retained. The output contains `data`, `labels` and
`data_scrambled`; the scramble preserves each category/neuron's exact marginal
values. MATLAB random-number consumption and distributional provenance must
be established by the producer of the supplied draws, not inferred from shape
validation.

`geometry_from_coefficients(data, labels, beta)` takes trial × neuron values,
the two equal class blocks, and one coefficient per neuron. The intercept does
not affect a hyperplane's normal and is not an input. It returns geometry,
never accuracy. To reproduce both source conditions, supply the intact and
scrambled data with their **respective** fitted source coefficients; reusing
one condition's coefficients is a different analysis. The coefficients of
the released five-fold binary example cannot replace the ten binary learners
in the empirical five-category ensemble analysis.

The CLI reads JSON and writes a new output file, refusing overwrite:

```sh
python geometry.py replay /approved/explicit-draws.json /approved/replayed-values.json
python geometry.py geometry /approved/data-labels-beta.json /approved/geometry.json
```

The geometry JSON has exactly `data`, `labels` and `beta`. These commands
document the interface; no authentic scientific run was performed. Native
execution, fitting and scientific acquisition retain the project protocol and
resource requirements.

## Verification and remaining qualification

Nine analytical/generated controls passed in the shared test pool. They cover
closed-form diagonal covariance, angle and inverse-covariance precision;
class-SD aggregation; sign/scale/translation/orthogonal-rotation invariance;
activity units; singular and isotropic covariance; explicit-draw source
parameters; exact within-category scrambling; and malformed inputs.
These are software controls, not simulated biological findings or empirical
performance. No author MATLAB code was executed, no classifier was fitted,
no source recordings/private targets were read, and no candidate was evaluated.

First-class reproduction and improvement require separate future scores and
matched paper+data versus paper+data+author-code access conditions. This
component supplies neither participant packages nor those scores. Complete
empirical cohort identities, original trial/ensemble selections, preprocessing,
author decoding execution, numerical figure targets and protected evaluation
remain unresolved. A geometry-example result must not be reported as a win on
the Fig. 6 maintenance decoder or Extended Data Fig. 7a encoding decoder.
