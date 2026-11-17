# MINT original Poisson-process information reference

This component recovers the analytical target for **S1 Appendix Figure C(B)** of the [MINT paper](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1012934). It computes information from the source-defined probability distributions, and summarizes supplied estimator outputs against those targets. It does not generate observations, fit a method, invoke MINT, or establish an improvement over the paper. The registered task remains source unresolved.

The previous CA1 evaluator estimates information from observed responses. Its empirical information values are not known truths. Here the probability law is specified by the original paper, so analytical truth is available. This is an additive original-paper endpoint component; the historical CA1 implementation is unchanged.

## Original source branch

The retained [S1 Appendix](https://journals.plos.org/ploscompbiol/article/file?type=supplementary&id=10.1371/journal.pcbi.1012934.s001), SM6.1, SM6.4, and Figure C(B), specifies:

- One through four neurons with conditionally independent Poisson counts, means 1 and 2 for the two stimulus values, and equal trials per stimulus. The means are expected counts per simulated observation; no additional duration conversion is introduced.
- Responses discretized into `0, 1, 2, 3, >=4`. The final bin includes four. Binning is fixed across sample counts and estimators.
- Plugin, quadratic extrapolation (10 repetitions), shuffle subtraction (30 shuffles), and KSG comparisons; 25 simulation repetitions per population and sample-count condition.
- Mean information and SEM across repetitions, with both unbinned and binned analytical information references. Units are bits.

These facts concern Figure C(B). Figure 2A/B instead uses 20 neurons and correlation scenarios; CA1 Figure 2C uses biological sessions and a decoder. Neither branch is pooled into this component. The source's 5,000-versus-50,000 repetition discrepancy concerns Figure C(A), not this 25-repetition panel.

The original Figure C(B) sample-count grid, exact generator/RNG implementation, KSG observation representation and settings, numeric estimator curves, and native MINT parity have **not** been recovered. No arbitrary default grid is substituted. The core toolbox and Figure 2 wrappers are separate sources and do not establish execution of Figure C(B). Source pin and locator details are in [SOURCE.json](SOURCE.json).

## Analytical computation

For stimulus `s`, each neuron has a Poisson distribution with mean `lambda_s`, where `lambda_1=1`, `lambda_2=2`, and each stimulus has probability one half. The binned conditional joint distribution is the product of the five categorical probabilities, including the complete Poisson tail for `>=4`. `binned_truth(N)` enumerates all `5**N` outcomes and computes their mutual information.

For the unbinned population, the likelihood ratio depends only on the sum of counts `T`. Thus `I(S;R_1,...,R_N)=I(S;T)` and `T|S=s` is Poisson with mean `N*lambda_s`. `unbinned_truth(N)` sums this one-dimensional distribution. It does not use a truncated and renormalized joint distribution.

After count `K`, each Poisson tail is bounded by `p(K+1)/(1-lambda/(K+2))`, because subsequent probability ratios decrease. The equal-weight mixture of these tail bounds also bounds the omitted information in bits for the binary stimulus. The default truncation bound is at most `1e-13` bits. This is a mathematical truncation bound; it excludes binary64 roundoff. Independent high-precision controls test the finite-sum calculation.

The difference between unbinned and binned truth quantifies information lost by this particular discretization. Signed estimation error relative to the binned truth can describe finite-sample bias for an estimator consistent for that binned distribution. It cannot by itself isolate finite-sample bias of KSG: KSG's limiting value and exact input representation are unresolved. The code therefore labels errors by their reference distribution rather than claiming that every difference is sampling bias.

## Use

Only the Python standard library is required. From this directory:

```sh
python3 -I -B poisson_truth.py
python3 -I -B poisson_truth.py --estimates /operator/path/estimates.json
```

The first command prints four analytical references. The second accepts an explicitly declared grid, requires every combination of four populations, grid entries, 25 repeat IDs, and all four source methods, and optionally includes named candidates. It reports each cell separately, including all repeated estimates, mean, sample-standard-deviation SEM, and signed errors against both references. It creates no pooled error score, confidence interval, winner, or pass threshold.

The estimate packet uses this structure (the one shown row is illustrative; incomplete packets are rejected):

```json
{
  "branch": "MINT-S1-Appendix-Fig-C-B",
  "input_role": "operator_estimates_unqualified",
  "trials_per_stimulus_grid": [20],
  "candidate_methods": [],
  "estimates": [
    {
      "n_neurons": 1,
      "trials_per_stimulus": 20,
      "repeat": 1,
      "method": "plugin",
      "estimate_bits": 0.15,
      "draw_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    }
  ]
}
```

The sample count, estimate and digest above are schema examples, **not paper values or observations**. `trials_per_stimulus` counts observations for each stimulus; total observations are twice that value. Source method identifiers are `plugin`, `qe`, `shuffSub`, and `ksg`. Repeat IDs must be integers 1 through 25. A draw digest must agree across methods for the same cell and repeat and must differ across repeats within a cell. These declarations detect inconsistent pairing and obvious reused draws; they do not authenticate source inputs or prove independence. The output always preserves that limitation. Raw observations, native estimates and private evaluation material belong outside Git.

Tests use deterministic mathematical controls and generated estimate packets. Run them through the wave's shared test pool, as recorded in the external handoff; they do not run an original simulation or candidate study.

## Remaining qualification

Admission still requires the complete original sample grid and generator binding, the exact source estimator observation path (especially KSG), controlled native comparator values, candidate exposure rules, a frozen ordered error endpoint and meaningful-effect/uncertainty rule, and paired source-matched runs. Original analytical distribution parameters are public, so this table is calibration/reference material and cannot be called a hidden prediction target. No author baseline, empirical superiority, or current SOTA result is claimed.
