# CAVIaR paired fixed-posterior predictor

This standard-library component supplies two prospective estimators for the fixed-posterior mean described in [the CAVIaR paper](https://doi.org/10.1038/s41593-025-02053-7), Supplementary Algorithm 4. It does not fit a posterior, construct charge targets or score an experiment. The accepted V2 implementation and its 22-control test file are unchanged.

Call `predict_paired(FixedPosterior, HeldHologram, ProspectiveSettings)` from `algorithm4_predictor_v2.py`. The typed API requires explicit weight standard deviations, two-dimensional power-curve means/covariances, target and power IDs, units, fitting declarations, draw count, seed and rejection cap. It has no experiment CLI. The module's referenced [SCIENTIFIC_CONTRACT.json](SCIENTIFIC_CONTRACT.json) is supplied here as a current curated contract.

## What the paired outputs mean

The literal estimator samples a joint positive-orthant Gaussian power curve for each target/draw, a Gaussian weight unless its mean is exactly zero, and independent Bernoulli spikes. Each accepted power curve and weight is shared across powers. Negative weight draws are retained. Exact zero weight mean is the zero point mass even when a nonzero standard deviation is declared. Prediction has no positive-power mask, extra observation noise or spontaneous-current term.

The Rao-Blackwell estimator uses the same actual accepted power-curve draws and integrates out weight/spike sampling. It is a competent variance-reduced reference/control of the same fixed-posterior mean. It is not a new neuroscience finding or evidence of better held performance. A fair improvement comparison needs a prospectively fixed sufficiently precise or variance-reduced reference and Monte Carlo uncertainty; eliminating avoidable sampling noise alone is not frontier improvement.

The returned `removed_conditional_covariance_of_mean` sums conditional weight/spike covariance across targets/draws and divides by J squared. It conditions on the accepted power curves. It excludes their Monte Carlo uncertainty and is neither total predictive/posterior uncertainty nor a scientific score. The contract gives the exact formulas and assumptions.

## Inputs and study obligations

Official `beta` conventions remain unresolved: this API never guesses whether an official value denotes a standard deviation, variance or other parameter. Typed covariance validation does not repair fits. Joint rejection exhaustion and nonfinite arithmetic fail without returning a partial prediction; failed targets or folds must not be silently dropped.

Metadata strings do not authenticate posterior provenance, real training exclusions or physical calibration. Explicit target-ID joins do not prove matching positive support across powers. The intended response is integrated synaptic charge in nC only after authentic calibration; naming a unit does not establish a trace window or convert raw data.

A future study must retain all 14 experiments and their complete held-hologram folds, powers and repeats, bind the all-trials-except-held-hologram fitting rule, and resolve animal/slice identities, support, schema, unit, calibration, repeat-reduction and historical-caller/comparator/demixer obligations. Fourteen experiments must not be assumed to mean fourteen independent animals. Charge construction, fitting and scoring belong to a separate trusted pipeline.

Practical workloads are not sandboxed. For N targets, K powers, J draws and rejection cap A, work includes O(J N K² + J N A), working storage O(N K²), and preparation O(N² + K² + N K). An outer owner must bound these inputs and supply real process budgets and recovery. Finite-float validation of J is not practical admission.

## Existing controls

From the repository root, using Python 3.11.18:

```sh
python -I -S -B -m unittest discover -s benchmarks/neuroscience/components/caviar-paired-predictor-v1 -p 'test_algorithm4_predictor_v2.py' -v
```

The file contains 22 invented controls. Retained execution comprises 21 controls on the earlier implementation and one focused huge-J-before-RNG control on V2; the complete current 22-control file was not rerun wholesale during assembly. The final mathematical/source review is accepted. This package's CI job is configured to authenticate five files and execute all 22 controls; its outcome must be read from the exact future run.

[PROVENANCE.json](PROVENANCE.json) records the unchanged Python identities and documentation boundary. No authentic data, fits, empirical score, novelty/SOTA claim, benchmark registration or qualification promotion is supplied by this publication.
