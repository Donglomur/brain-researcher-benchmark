# Decision-times initial export evaluator

This component makes a concrete part of the registered task executable: it derives six stage durations from five event times, computes participant-level contrast and speed/accuracy effects, evaluates the three published latency equations, preserves the source's contrast-held-out scoring convention, and calculates original electrode-group ERP contrasts and paired participant-held-out likelihood differences. Its input is a complete explicitly inventoried export. It does not estimate events from EEG, fit nonlinear laws, perform native HMP model selection, reproduce figures, or supply a numeric reproduction grade. Scientific qualification remains unknown.

## Source and semantic decisions

The registered task is unchanged: 26 cleaned participant epoch files, post-acquisition/photodiode correction, 512 Hz recipe. The official analysis revision is `76464a9ca15564897e58256081af4b99d08ae8db`. Sources inspected are its [HMP notebook](https://raw.githubusercontent.com/GWeindel/decision-times/76464a9ca15564897e58256081af4b99d08ae8db/1-HMP_analyses.ipynb), [ERP notebook](https://raw.githubusercontent.com/GWeindel/decision-times/76464a9ca15564897e58256081af4b99d08ae8db/2-ERP_analyses.ipynb), [equations](https://raw.githubusercontent.com/GWeindel/decision-times/76464a9ca15564897e58256081af4b99d08ae8db/models.py), [scoring utilities](https://raw.githubusercontent.com/GWeindel/decision-times/76464a9ca15564897e58256081af4b99d08ae8db/utils.py), and [installation notes](https://raw.githubusercontent.com/GWeindel/decision-times/76464a9ca15564897e58256081af4b99d08ae8db/README.md). The [paper](https://elifesciences.org/articles/108049) identifies the central scientific claims; paper access was intermittently challenge-blocked, so numerical targets were not imported.

The notebook exports five events with source labels C1, P100, N200, LRP, CPP. These labels describe that code snapshot; event indices are the binding identities, and the paper's first-event nomenclature can differ. Six intervals include the start and end. Source combined encoding is event 1→3 and decision is event 3→5, excluding the initial and terminal stages.

`hmp==1.0.0-b2` [event-time source](https://raw.githubusercontent.com/GWeindel/hmp/v1.0.0-b2/hmp/utils.py) uses marginal maximum-probability samples, first ties, and an endpoint from cumulative posterior support plus one sample. `posterior_point_times` implements those operations on five complete normalized marginals. That optional kernel does not estimate posteriors. It rejects zero-mode ambiguity because native HMP additionally masks events absent across a group; grouped missing-event handling is outside this complete five-event interface. The notebook adds a 10 ms postresponse offset before fitting. Therefore `model_end_ms` and behavioral `rt_ms` are distinct required quantities; their difference is reported. No implicit offset removal, sample-rate conversion or endpoint replacement occurs. Native parity still requires executing the pinned environment.

The canonical task calls for correct-response selection. **`correct_only` is the primary latency analysis**; it is always produced. Inspected source notebooks derive a correctness flag but their displayed latency-law grouping retains responded trials. Consequently `all_responded` is also always produced as a separately labeled source sensitivity. Law evaluations explicitly identify which population they score. Accuracy always uses all retained responses in the corresponding participant/condition/contrast cell, even when latency uses correct responses. This source/contract discrepancy remains an explicit parity gate; this package does not rewrite either history or contract.

## Running and input contract

From the package directory:

```sh
python3 evaluator.py input.json --output result.json
python3 -B -m unittest discover -s tests -v
```

No dependencies beyond Python 3.10+ standard library. `tests/test_evaluator.py::fixture`, `laws`, `erp`, and `likelihood` are executable, generated examples of each input block. To create an engineering example without running any scientific workflow:

```sh
python3 -B - <<'PY'
import json
import sys
sys.path.insert(0, 'tests')
from test_evaluator import fixture, laws, erp, likelihood
x = fixture()
x['law_evaluations'] = [laws(x)]
x['erp'] = erp(x)
x['heldout_likelihood'] = likelihood(x)
with open('example.json', 'w') as f:
    json.dump(x, f)
PY
```

Top-level required fields:

| Field | Meaning |
| --- | --- |
| `schema` | Exactly `decision-times-export-v1` |
| `purpose` | `engineering_control` or `empirical_export`; neither authorizes a qualification claim |
| `sample_rate_hz` | Positive acquisition/analysis rate; 512 is labeled the source profile, any alternative explicitly differs |
| `time_unit`, `contrast_unit`, `time_origin` | Exactly `ms`, `percent`, `stimulus_onset` |
| `point_time_method` | `hmp_export_unverified` or `explicit_point_estimates`; provenance remains unverified |
| `expected_participants` | Exact nonempty roster; empirical exports must include `0_epo` through `25_epo` |
| `trial_inventory` | Each participant/epoch once, disposition `retained` or `excluded`; exclusions need a reason |
| `trials` | Every and only retained inventoried trial, no duplicate keys |

Each trial contains string `participant`, string `epoch`, `condition` (`speed`/`accuracy`), `side`/`response` (`left`/`right`), `contrast_percent` in `(2.5,100]`, positive `rt_ms`, positive `model_end_ms`, and exactly five finite nondecreasing `event_times_ms` between zero and model end. The input represents responded trials; missing responses/rejections remain explicitly accounted for in the exclusion inventory. A declared inventory can detect export omissions but cannot prove authentic completeness; native inventory audit remains required.

The evaluator never assumes 100 Hz processing equals 512 Hz. The five-event input is explicit even for an alternative profile; it is not an assertion that five events would be found under altered sampling or width. Source HMP settings (15 PCs, participant scaling, 25 ms half-sine, 100 ms lower RT limit, 100 µV rejection threshold, response offset) are provenance, not operations newly performed here.

## Calculations and outputs

`latency` reports correct-only primary and all-responded sensitivity cells, six stage means, combined encoding/decision and behavioral RT. Participant/condition contrast slopes regress equal-weight contrast-cell means against percentage points. Their units are ms/percentage point. Accuracy-minus-speed effects pair the same participant and contrast. A fixed-seed 2,000-draw participant bootstrap reports percentile intervals for slopes and paired effects. This is a prospective descriptive analysis policy, not the paper's Bayesian mixed model or a causal effect. Singleton intervals are null. Missing correct-response participants, unpaired cells and unavailable contrast slopes remain visible; no sample or posterior-point count becomes a biological replication count.

Optional `law_evaluations` contains independent requested evaluations with `target` (one of the six code stage names, `encoding`, `decision`, or `rt`), `model` (`linear`, `pieron`, `fechner`), explicit `selection`, `mode` (`descriptive`/`leave_one_contrast_out`), and `parameters`. Each parameter entry has `participant`, `condition`, and `values`, covering the complete selected population. In contrast-held-out mode it also has `held_out_contrast_percent` and the exact remaining `fit_contrasts_percent`. This enforces declaration consistency, not independently attested fitting provenance.

Equations receive contrast fraction x and produce seconds; output latency is converted to ms. Linear uses slope and intercept. Pieron uses nonnegative amplitude and exponent with no intercept. Fechner uses parameters k, A, t0 with source bounds `[0,18.51]`, `[0,7.47]`, `[0,3.69]`; z is log((x+.025)/(x-.025)); latency is A*tanh(A*k*z)/(k*z)+t0 and accuracy is logistic(2*A*k*z). At k=0 this implementation uses the continuous limit A²+t0 and accuracy .5, a documented numerical boundary policy. Parameter fitting is deliberately external and unverified.

Law output includes trial MSE in **seconds squared**, equal-participant observed/predicted curve R², accuracy R², and curve RMSE in ms. Constant-target R² is null. The source contrast-LOOCV utility pools observed trials at the held contrast but averages participant predictions; `source_asymmetric_curve_rmse_ms` preserves that asymmetry. `participant_equal_curve_rmse_ms` separately averages participant observations and predictions. Neither is participant-held-out neural likelihood. No winner is selected automatically.

Optional `erp` has `alignment: stimulus`, `amplitude_unit: V`, strictly increasing common `times_ms` from 0 to 1000, unique `channels`, and one `volts` channel×time array per retained trial. It computes source ROI means (O1/Oz/O2, CP1/Pz/CP2, AF3/Fz/AF4), source half-open contrast bins `(3.4999999,49.50000495]` and `(49.50000495,95.50001]`, within-participant trial averages, and equal-participant low-minus-high curves in µV. Window means use trapezoidal time weighting, including on irregular grids. All retained trials must have ERP rows, including legitimate 3% trials outside those source analysis bins. Out-of-bin rows are validated and listed by participant/epoch/contrast as unscored for ERP only; they remain in latency and accuracy populations. Unpaired participants are listed. The component does not recenter raw EEG, fit the CPP relationship, or replace the source cluster-permutation test with an invented significance result. ERP input alignment and source trial-selection parity remain externally auditable.

Optional `heldout_likelihood` contains `unit: natural_log_per_trial`, `same_observation_space: true`, `baseline_model`, and at least two named `models`. Each declares `event_count`, `event_width_ms`, and `folds`. Every fold names `test_participants`, `fit_participants`, `preprocess_fit_participants`, and all retained per-trial `scores` (`participant`, `epoch`, `log_likelihood`). Train/test populations must partition the roster, preprocessing-fit IDs must equal train IDs, every trial is scored once, and models use identical folds. Outputs include paired participant mean and total log-likelihood differences. These checks reject stated leakage, omissions and mismatched panels but cannot prove upstream PCA/HMP was actually fit as declared. All models must score the same observations and likelihood measure; a Boolean comparability declaration is not scientific verification. Event widths/numbers are retained; no test-panel model winner is selected.

## Requirements and retained limits

| Registered requirement | Implemented component | Remaining gate |
| --- | --- | --- |
| Five-event inference | Marginal mode extraction kernel and explicit five-time export analysis | Native HMP inference, environment/API parity, event-number selection |
| Contrast-related latencies | Six intervals, two combined stages, participant effects, published law equations and errors | Authentic exports, frozen native fits and numerical references/tolerances |
| ERP/accuracy relationships | Original ROI/bin ERP differences; full-response accuracy and Fechner predictions | Native alignment, CPP/cluster/Bayesian analysis and figure references |
| Held-out likelihood and alternatives | Exact trial/fold alignment and paired participant likelihood differences | Independent execution attestations, competent fitted baselines and protected evaluation |
| Complete population | 26-participant empirical roster and retained/excluded trial inventory checks | Empirical provenance and native inventory confirmation |
| Rights/resource envelope | No data redistributed; no native analysis run | OSF data terms; 512 Hz author RAM estimate is not measured project usage |

No immutable task/history, registry, shared framework or global inventory is changed. No data, packages, HMP models, authors' private artifacts, or archives were acquired. Official code remains BSD-3-Clause upstream; this package is newly written and does not vendor it. Public paper/results exposure remains. Source review and generated controls do not establish authentic reproduction, improvement, submission readiness or scientific qualification. Output preserves these holds and never emits a binary grade.
