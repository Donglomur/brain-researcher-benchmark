# Registered-response decoding sensitivity (STEINMETZ-001)

## Scientific question and source

How does prediction of a mouse's registered left/right response vary across two
spike-count window recipes and two cross-validation recipes in one session?
This is a **paper-derived computational method case**, not a reproduction of
the regional choice-coding finding in [Steinmetz et al. (2019), Figure 4c and
Methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC6913580/). That analysis
separates task-related components and examines movement-relative regional
activity. The present task uses raw counts from every stored unit.

The original-study session is Cori, 2016-12-14, published as NWB in DANDI
`000017/0.240329.1926`, asset `92694e6e-84fd-4198-a7e3-64e764f8e086`.
The unmodified 311,814,662-byte file is baked into the image at:

`/app/data/steinmetz/sub-Cori_ses-20161214T120000.nwb`

Its SHA256 is
`d8433a826049f82cd832f41f98a9f9fafad0ac66998d4dbfd89b15b594fc4236`.
`/app/data/steinmetz/source_manifest.json` supplies provenance, license and
attribution. **No runtime download or external data is needed.** Public method
and metadata definitions are in `/app/method_contract.json`; it contains no
fitted reference answers. See the
[published release](https://dandiarchive.org/dandiset/000017/0.240329.1926).

The [author's data dictionary](https://github.com/nsteinme/steinmetz-et-al-2019/wiki/data-files)
distinguishes the registered response from initial wheel motion. Choice `-1`
means right, `+1` left, and `0` no-go. The `included` flag is not the paper's
complete response-timing selection. Retaining all NWB units includes MUA
(multi-unit activity), Good and Unsorted clusters; these are not all certified
single neurons or the paper's quality-selected population.

## Public numerical contract

1. Read NWB `intervals/trials` and `units`. Retain trials with `included=True`,
   choice exactly `-1` or `+1`, and finite `visual_stimulus_time` and
   `response_time`. Use original trial IDs and table order; verify selected
   stimulus times are nondecreasing. Report exclusions without silently
   reordering trials or adding correctness, contrast or movement filters.
   Use every stored unit, in unit-table order; retain original unit IDs in any
   optional analysis receipt. Reject malformed, nonfinite or unsorted spikes;
   retain duplicate spike timestamps as stored, without deduplicating.
2. Build raw spike counts for each selected trial and unit. Both windows are
   left-closed/right-open, with no clipping to trial start/stop:

   | Window | Alignment | Relative interval |
   | --- | --- | --- |
   | `stimulus` | `visual_stimulus_time` | `[0, 0.25)` seconds |
   | `peri_response` | registered `response_time` | `[-0.1, 0.1)` seconds |

3. Generate five-fold memberships once per split recipe and reuse across both
   windows. `blocked` is `KFold(5, shuffle=False)` on retained table order.
   `random` is `StratifiedKFold(5, shuffle=True, random_state=0)` on signed choice.
   Fold IDs are 0–4. Every trial must be held out exactly once per recipe.
4. Within each training fold fit `StandardScaler(with_mean=True, with_std=True)`
   (population variance, `ddof=0`); use that fitted transform for held-out rows.
   Fit L2 `LogisticRegression(C=1, solver="lbfgs", tol=1e-4, max_iter=2000,
   fit_intercept=True, class_weight=None)`, with the public software baseline
   in the method contract. Treat a convergence warning as failure. Positive
   decision values predict left (`+1`); zero or negative predicts right (`-1`).
   Report the held-out decision value and probability of left, not training
   predictions. No tuning against the held-out trials is permitted.
5. Also predict each held-out trial using its **training-fold majority** class;
   ties choose `-1`. Separately report the full selected sample's majority
   fraction as a descriptive quantity, not a trained baseline.
6. Report all four keys: `stimulus_blocked`, `stimulus_random`,
   `peri_response_blocked`, `peri_response_random`. Each cell's accuracy is the
   **unweighted mean of five fold accuracies**; also report pooled held-out
   accuracy and the population (`ddof=0`) standard deviation of fold scores.
   The headline is `stimulus_blocked`. Never substitute pooled accuracy for
   the unweighted mean when fold sizes differ.
7. Count registered-response events in three disjoint categories: before
   stimulus; `stimulus <= response < stimulus + 0.25`; and at or after the
   window end. These counts partition selected trials. They do **not** measure
   first movement onset or establish that a window is pre-movement.

Use the same selected trial and unit support in all four recipes. Fail if the
input cannot support the declared folds; do not replace failed fits, impute
missing source fields, or suppress numerical failures.

## Required outputs

Write to `${OUTPUT_DIR}` (default `/app/output`). Fractions are in `[0,1]`, not
percentages. IDs and counts are integral; JSON numerical values must be finite.

- `trial_predictions.csv`: one row for every `(recipe, trial_id)` pair, with
  `recipe,trial_id,fold,true_choice,predicted_choice,baseline_choice,decision_value,probability_left`.
  Choice columns use `-1/+1`, never reversed labels or zero/one recodings.
- `folds.csv`: exactly 20 recipe/fold rows with
  `recipe,fold,n_train,n_test,n_correct,accuracy,baseline_choice,baseline_n_correct,baseline_accuracy`.
  Counts and accuracies must recompute from the submitted held-out rows.
- `results.json`: `status="ok"`, the public `pipeline_id`, `n_trials`, `n_units`,
  `selection_counts`, `response_timing_counts`, `global_majority_fraction`,
  `cross_validated_accuracy`, and dictionaries
  `accuracy_by_window_and_split`, `pooled_accuracy_by_window_and_split`,
  `accuracy_std_by_window_and_split`, `baseline_accuracy_by_split`,
  `pooled_baseline_accuracy_by_split`. The first three dictionaries contain all
  four recipe keys; baseline dictionaries contain `blocked` and `random`.
  `selection_counts` contains `n_source_trials`, `n_not_included`,
  `n_included_nonbinary_choice`, `n_included_binary_invalid_alignment`,
  `n_selected_trials`, and `n_source_units`. Exclusion categories are sequential
  and mutually exclusive. `response_timing_counts` uses `before_stimulus`,
  `within_stimulus_window`, and `at_or_after_window_end`.
- `run_metadata.json`: the public method-contract fields, plus `status="ok"`,
  `n_trials`, `n_units`, `selection_counts`, `response_timing_counts`, and
  `primary_recipe="stimulus_blocked"`. Copying the public template is allowed;
  fill measured counts from the source. Extra diagnostic fields are welcome.
- `findings.md`: a short, evidence-bounded interpretation of the four measured
  results, their baselines and timing limitations. No wording or effect
  direction is prescribed.

CSV row order and extra columns do not matter. Every required source-keyed row
must be present exactly once. Optional `analysis_arrays.npz` or other diagnostics
are not required submission formats. The verifier checks source-derived trial
identities, folds, labels, counts, held-out predictions and numerical consistency;
it does not infer scientific validity from prose. Categorical results are exact;
decision values/probabilities use absolute and relative tolerance `1e-6`, and
summary values absolute tolerance `1e-6`. Use enough precision in saved outputs.
Scoring is binary: all required checks pass for reward 1; otherwise reward 0.

## Interpretation and failures

The window recipes differ in duration as well as alignment, and the split recipes
differ in stratification as well as temporal allocation. A difference cannot be
attributed to just one factor. Contiguous KFold trains on trials before and after
the held-out block, with no temporal buffer: it is not prospective prediction.
Trials/folds/units from this one session are not independent animals. Do not call
fold variability a population confidence interval or interpret above-baseline
decoding as isolated, causal or necessarily pre-movement choice information.

If input verification or analysis fails, exit nonzero and write parseable
`results.json`, `run_metadata.json` and `findings.md` with
`status="failed_precondition"` and a nonempty reason. Do not invent a result.
