# NEURAL-005: descriptive neural predictive contribution

This standalone, standard-library component assesses whether adding the provided ERP features improves next-round choice prediction for a frozen matched modeling procedure. It supplements an already admitted complete score report. It does not run a candidate, load data, fit a model, authenticate upstream artifacts, or certify a scientific result.

The existing primary ranking remains equal-participant all-ERP log loss, lower is better. The scientific contrast is a separate descriptive quantity:

`gain = (1 / 7) * sum_person[log_loss(history) - log_loss(all_erp)]`.

Positive gain means lower observed loss with ERP features for the chosen procedures on these seven development people. Weakening the history model can inflate this contrast, but cannot improve the unchanged absolute all-ERP ranking. A credible interpretation still requires competent references and matched training-only methods; this component does not verify model adequacy. Negative and zero contrasts remain valid reports.

## Full scope and outputs

Keep all 26 training people and 3,254 training examples; all seven development people; all 816 next-round queries in each of three views; and all 2,448 predictions from 21 complete person/view protocols. The views are history (50 features), history plus three prestimulus features (53), and history plus all seven ERP features (57). Eligibility uses the same original current-trial seven-ERP support before any masking. No reduced-support option is offered.

The adapter checks the previously admitted report's scalar scope and recomputes its equal-person summaries and six signed contrasts. It retains four absolute arms (the three views and the training-participant-macro prior), all person scores, and all six contrasts: history minus all ERP; history minus prestimulus; prestimulus minus all ERP; and each view minus the prior. Undefined AUC in a one-class person remains undefined without dropping that person from log-loss or Brier scoring.

Seven leave-one-person-out gain summaries show sensitivity to individual people. They are descriptive summaries of the same result, not confidence intervals, cross-validation refits, favorable subset selection, or additional benchmarks. The primary result always includes all seven people. Previously exposed development people held out of training are not a newly unexposed confirmation cohort.

## The exact matched-history control is infeasible

Let H contain all 50 allowed history features. H includes episode and current round; each admitted participant:episode:round case is unique. Within a person, two cases with equal H must have equal episode and round, and hence must be the same case. Every exact full-H stratum is therefore a singleton. This structural proof does not need neural values, continuous-history values, target inspection, or arbitrary numerical tolerances.

The returned control state is `infeasible_exact_within_participant_full_history`, with 816 development singleton strata and zero movable cases. It performs zero ERP randomizations. Repetition count, seed and p-value remain null; no null-fitting or refitting policy is selected. The identity permutation is not evidence that a scientific null was tested.

This rules out this exact within-person matching scheme. It does not prove every possible conditional test impossible. Coarsening history, removing its identity fields, pooling participants, or assuming a conditional sampling law would require a separately justified scientific design. Conditional independence given a full history need not survive binning that history. Conditional randomization/permutation methods need an appropriate conditional distribution and dependence assumptions; their independent-observation theory does not automatically transfer to overlapping sequential observations. See [Berrett et al., sections 2.1, 3.1 and 5](https://arxiv.org/html/1807.05405v2) and [Winkler et al., exchangeability](https://pmc.ncbi.nlm.nih.gov/articles/PMC4010955/).

For all-ERP contribution beyond H, a future validated null would concern all seven ERP components jointly. For the offer-specific contribution beyond prestimulus, it would concern the four offer components conditional on H and the three fixed baseline components. Moving all seven components tests a different question; shuffling columns separately discards their joint structure. Neither null is implemented here.

## Interpretation and timing

The source paper's Table 2 predicts same-row choice from ERP terms and round. This benchmark's current-to-next-round prediction is an explicit extension, not a reproduction of that endpoint. The published sequence is expectations, offer, affect report, then choice; current choice and affect belong to a forecast made after current-trial completion. Next-trial measurements and future prefixes remain prohibited. The next target must be the consecutive round of the same partner episode, with no bridging across removed rounds or partner boundaries. See the [primary study](https://pmc.ncbi.nlm.nih.gov/articles/PMC12373756/) and [pinned author analysis, Table 2](https://github.com/jpheffne/2025_epe_eeg/blob/4f5767df1516e0ec3c234d51ba36e4b741eb60e8/analysis/eeg_epe_ms.Rmd#L381-L388).

Processed ERP amplitudes are offline features. Event-relative windows do not establish online preprocessing or independently authenticated trial-epoch linkage; the author's positional ERP/behavior binding does not settle those holds. A favorable predictive contrast is not a causal neural effect, an intrinsic conditional-information estimate, or proof that emotion explains the gain. An unfavorable contrast does not establish conditional independence. No scientific success threshold, confidence interval, or p-value is supplied.

## API and trust boundary

`assess(report, projection_receipt, schedule)` returns the contribution report or raises `ValueError` for malformed or inconsistent supported inputs. The public module uses only Python's standard library. It does not import the existing grader or any candidate module. Its separate private integration check pins the existing grader and metric helpers without copying them into this public bundle.

The trusted operator must first authenticate the exact preparation, target-free expected schedule, training/development partition, feature projection, candidate artifact, matched-method declaration and complete score report through the existing operator's `admit_prepared` and `admit_score` checks. The schedule is an independently fixed input, never a candidate-selected subset. It has exactly `participants` (seven unique canonical numeric-string identities) and `cases` (816 records with only `participant` and `case_id`, formatted `participant:episode:round`). This bundle contains invented identities only, not the real participant roster.

The pure adapter checks consistency with that supplied schedule; it cannot authenticate the real roster, input hashes, training rows, fit history, source isolation or lifecycle closure merely from a dictionary. Receipt fields are assertions after trusted admission, not new proofs. The operator retains the complete original score artifact and its custody evidence. This component copies only validated score fields, not arbitrary extra input fields.

Use the same training-only feature transformations, model family, tuning opportunities, splits, seeds and resource policy for each view. Hold all candidate artifacts and predictions fixed before protected scoring; no private score feedback or held-person fitting is authorized. Existing execution/resource controls remain the caller's responsibility. The component cannot detect hidden fitting, unequal effort or deliberately weakened methods from scalar scores.

All scientific qualification and submission flags remain false. This is one existing assignment with an additional descriptive contract component, not a new benchmark or a completed scientific experiment.

## Engineering verification

Run `python3 -I -S -B test_scientific_contribution.py -v` from this directory. The tests construct invented full-size metadata and analytic scalar metrics. They cover full support, equal-person weighting, one-class AUC, positive/negative/zero gain, sensitivity, unchanged ranking, malformed counts and identities, incomplete admission, nonfinite/boolean metrics, fabricated contrasts and qualification promotion. They do not open authentic arrays or targets, fit models, or establish scientific validity.
