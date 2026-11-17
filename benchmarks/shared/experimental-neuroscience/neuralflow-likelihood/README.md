# Experimental held-neuron prediction and spike likelihood

**NOT READY for authentic benchmark evaluation.** This package provides independently authored evaluator components motivated by NeuralFlow. It does not add a registered benchmark ID. The intended paper-level scope retains all 30 population attempts (15 per animal) and four stimulus conditions; this export implements only likelihood and information-boundary components. No authentic data, trained models, historical reference execution or scientific qualification is included.

The complete cohort index checks every declared population, its original unit order and all four stimulus conditions. `public_view` returns exactly one population/trial/held-neuron query. It removes the held neuron's spikes and all undeclared fields, including choice targets and arbitrary nested metadata; returned arrays are independent copies. The caller must use separately isolated held-neuron roles. Combining queries in one participant context reveals the very spikes withheld in another query. This helper is not a physical isolation runner or proof of training provenance.

`curve_log_density` evaluates a submitted intensity function against evaluator-only spike times. The wire representation is explicit piecewise cubic polynomials in seconds, with rates in Hz. Coefficients use ascending powers relative to each interval's left knot. Knots and diagnostic quadrature grids are evaluator-bound, span the full observed interval and cannot be changed in a submission. The function checks nonnegativity throughout each polynomial, including interior extrema. There is no clipping, inferred endpoint convention, default spline fit or extrapolation.

The primary calculation uses the analytic polynomial antiderivative evaluated in binary64. A trapezoidal integral is returned separately as a diagnostic. This prospective numerical representation does not claim the paper's unknown spline boundary conditions or historical grid. It deliberately prevents arbitrary submitted cubic curvature from escaping a trapezoidal likelihood penalty. Exact-form integration is not an assertion of zero floating-point error; unrepresentable/negative computed results refuse the whole component, with no silent case removal.

The underlying point-process identity is log density equal to the sum of log rates at observed spikes minus the time integral of the rate. The paper's reaction-time normalization separately divides each model's joint spike/reaction-time density by its own reaction-time density. Therefore `normalized_population_comparison` subtracts each constituent neuron's own reaction-time log density before summing. It must receive trusted model-engine values: it is not a grader for arbitrary contestant-reported scalar likelihoods. See the paper's [Methods, equations 15–16 and LONO validation](https://www.nature.com/articles/s41586-025-09199-1#Sec11).

Silent trials contribute the negative integrated intensity and remain in all denominators. A zero rate at an observed spike represents negative-infinite log density; JSON reports a null value with `zero_event_density=true`, never a dropped case or an epsilon reward. Paired differences preserve positive/negative infinity and the undefined difference of two negative infinities as explicit statuses. Positive finite log densities are allowed: a density is not a probability mass bounded by one.

`score_lono` requires a prediction for every neuron of every retained trial in every population, including failed fits using explicit fallbacks. It returns each case and all 120 population-condition summaries with trial, neuron, spike and fallback counts. `compare_lono` compares two complete prediction sets on identical targets and numerical grids. It does not claim reference competence, infer broad biological uncertainty, choose a scalar composite or count cases as benchmarks.

The required scientific comparators for the intended paper-level task are: normalized constituent single-neuron models and the historical choice-conditioned PSTH for reproduction, plus a separately protected matched-information reference for improvement. The historical PSTH uses validation choice information; it must not become a supposedly target-free protected baseline. This source neither fits those references nor replaces them with a convenient surrogate. Authentic clock/interval/case membership, archived model bindings, numerical calibration, complete references, shared geometry, grouped uncertainty and protected program execution remain required before task qualification.

All code here is independently authored standard-library Python. The adapter also contains prospective choice-feature, split and scoring helpers; those are not a complete choice benchmark or a historical pipeline. No upstream implementation, paper content or dataset is redistributed. The CLI's 16 MiB per-file/output ceiling is a component engineering bound, not an authenticated whole-cohort workload limit. Source APIs can be used by a separately admitted streaming evaluator.

## Commands

Run from this source directory:

```sh
python3 -I -S -B -m unittest discover -s . -p test_likelihood.py -v
python3 -S -B cli.py project-one --input private-query-request.json --out new-query.json
python3 -S -B cli.py score-lono --input private-grading-request.json --out new-private-score.json
python3 -S -B cli.py normalize --input trusted-density-records.json --out new-density-comparison.json
```

The query request has `projection`, `roster` and a five-field `case` identity. Grading has `projection`, `roster`, complete `predictions` and evaluator-owned `numerics` rows. Normalization has `population`, `single_neurons` and `expected_units`. The tests provide complete invented examples and boundary failures. JSON rejects duplicate fields and nonfinite literals; input files must be ordinary single-link files and outputs are created exclusively with 0600 mode. These local file checks are not a hostile-candidate sandbox. Never give a candidate the grading request, complete private index, numerical target data or another held-neuron role's packet.

The roster and projection are trusted evaluator inputs. The 30-population/four-condition check establishes structural coverage only: it cannot detect a missing original trial when another trial preserves that condition. Authentic trial membership must first be admitted and pinned independently. The scorer then requires every case in that immutable projection, including silence and failed-fit fallbacks. Candidate-submitted cubic coefficients are intensity predictions, not authenticated NeuralFlow model outputs or proof of latent-path construction.

The 28 test methods use invented arithmetic and information-boundary fixtures only. Tests check software behavior and do not establish biological validity or performance. The unchanged likelihood arithmetic also passed 22 independent analytic cases during source review; that check is not an authentic NeuralFlow reproduction. These commands perform no scientific fitting or model evaluation. See [PROVENANCE.json](PROVENANCE.json) for the public scientific reference and redistribution scope.
