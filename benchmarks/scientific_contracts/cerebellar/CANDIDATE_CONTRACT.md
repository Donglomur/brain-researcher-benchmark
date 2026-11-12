# Cerebellar contact-count candidate contract

This companion makes the existing NEURAL-030 prediction question usable by a candidate and separates performance against a fixed reference from evidence of incremental neural information. It adds pure input projections, output validation and paired evaluation. It does not run candidates, read native files, establish biological identities, or qualify the benchmark. The existing canonical endpoint and all scientific holds remain unchanged.

## Question, target and information time

For each held-out complete trial, predict finite nonnegative **expected contact-onset counts** in every ordered 100 ms bin of the planned reward-delay interval, starting at movement end. One-second trials require 10 outputs and two-second trials 20; fractional predictions are permitted. A contact onset is the right-hand sample of a measured binary 0-to-1 transition, with a genuine preceding sample. Counts are not licking-rate estimates, jaw motion, reward probability, or a paper figure reconstruction.

Prediction issuance is after the complete planned interval. A candidate may use the entire supplied interval's handle trajectory and its selected neural channels when predicting any bin in that interval. This is retrospective decoding: later samples within the supplied window are available even for its first bin. It is not forecasting or an online decoder. No signal outside the prepared interval is supplied. Actual reward jitter can put delivery inside this planned interval; no claim that all predictors precede actual delivery is made. The source has whole-recording calcium processing, so this also does not establish fold-isolated raw preprocessing or causal inference.

The [primary methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC11343686/) describe synchronized 200 Hz behavioral acquisition, contact sensing in the learning-imaging mice, and processing applied across recordings. The [pinned author README](https://github.com/wagnerlabnih/garcia-garcia-neuron-2024/blob/124c83e1af83e9680e05f9827448579d02345fa3/README.md) defines binary contact, handle, clock and aligned-array fields. These support the source interpretation, not authentication of any uninspected recording. The count-decoding endpoint is our benchmark task, not a claim to reproduce the paper's original temporal-decoding analysis.

## Cases and split

Retain all 16 expected learning-imaging session records: five one-second expert, five two-second novice and six two-second expert. A case is a session, with its own cells and calibration data. Do not pool cells across sessions or identify animals by their within-group index. The same five mice are the intended biological cohort; the genuine mapping remains unauthenticated.

The existing preparer orders complete trials by authenticated movement chronology and assigns floor-based contiguous 60/20/20 train/development/query partitions before fixed QC. It refuses missing support, overlap of actual input windows across folds, or an empty admitted partition. It retains private dispositions. This companion accepts that prepared result, preserving its original order and gaps; it does not recompute splits, select good outcomes, or certify native chronology/QC. Query trials are later trials within each session, not held-out mice or unseen sessions.

The existing code-99% sensor-occupancy rule, paper-90% discrepancy and genuine 300-sample history requirement remain explicit holds. QC conditions the population on measured contact behavior. It is performed privately before candidate delivery; neither QC flags nor excluded-trial targets become candidate predictors.

## Candidate information and fit lifecycle

`compile_panel(public)` accepts the existing complete public preparer object and returns a target-free plan and 64 operator assembly views: four conditions for each of the same 16 cases. Every view keeps identical trial membership, handle/context inputs and output bins. These are conditions of one assignment, not 64 benchmarks.

| Condition | Visible predictors besides training/development counts |
| --- | --- |
| `context_handle` | Opaque trial/session IDs, original trial order, planned delay, learning stage, movement-relative handle time and two handle channels |
| `grc` | The same context/handle plus neural time and GrC signals |
| `cf` | The same context/handle plus neural time and CF events |
| `joint` | The same context/handle plus neural time and both neural signals |

Neural-free means the fields and values are absent. It does not mean zeroing a neural matrix. Unknown/private fields, query counts and malformed source objects cause refusal before projection. No query contacts/rates/onsets, actual reward time, source workspace, sensor QC, animal mapping or donor map is included. Arrays are copied without cross-view aliases. Source-shaped 32-character opaque IDs and declared dimensions are syntax checks, not identity evidence.

The complete view is an operator assembly object, not a packet to deliver before fitting. Deliver `calibration_packet(view)` first: only training and development records, with their counts. Training supplies coefficient/statistic fitting; development permits hyperparameter/model selection. Freeze the selected predictor and fitting procedure before delivery of `query_packet(view)`, which contains query predictors and the complete required output roster only. Do not refit on development, query predictors or query outcomes in this selected companion protocol. Do not carry learned state between independently calibrated cases or feed private scores between arms. Both frozen-program and case-adaptive code-authoring modes may construct their predictor during calibration; query execution here is frozen prediction, not a claim that unrestricted adaptive investigation is implemented.

For matched comparisons, freeze the same candidate source, model-selection rule and resource accounting for all conditions. Different fitted coefficients are expected because the visible features differ. A context model must be allowed the same full-window temporal modeling capacity and calibration opportunity as its neural counterpart. Record all resources and failures; never choose a favorable condition or silently drop a case. These source functions create the operands but do **not** enforce process isolation, model freeze, resource limits, source equality or honest use of delivered features. An actual executor and its custody checks remain required.

## Output and private evaluation

Return one JSON object for every case and condition:

```json
{"schema":"neural030_prediction_v1","task_id":"NEURAL-030","session_id":"<supplied opaque ID>","arm":"joint","predictions":[{"trial_id":"<supplied opaque ID>","counts":[0.25,0.0]}]}
```

The example abbreviates a vector; the actual response must have every supplied trial and all 10 or 20 bins. `parse_response(body, max_bytes=...)` rejects duplicate keys, nonfinite JSON numbers and an explicitly supplied byte limit. `validate_response` rejects extra fields, wrong condition/session, missing or duplicate trials, wrong vector lengths, booleans and negative/nonfinite values. Case and trial rows may arrive in any order; evaluation restores the frozen plan order. The parser's limit applies to already received bytes and does not implement filesystem/process limits.

`score_matched_panel` requires the complete 16-case plan, all four response panels, all private expected rows, the complete fixed context-plus-handle ridge prediction vector, and an operator-attested session mapping to exactly five declared mice. Labels and all returned metrics stay operator-private until the campaign's reporting boundary. The wrapper cannot authenticate labels, mouse IDs, or whether the submitted reference numbers came from the fixed reference. No smaller cohort or unbound fallback is accepted by this companion.

The unchanged `score.py` owns every metric and aggregation: mean bin loss per trial; equal trials within a session; equal sessions within a mouse; equal mice. Primary loss is MSE. Secondary Poisson deviance uses its existing 1e-12 floor, including the zero-label/zero-prediction convention. Null and negative gains remain results. Large arithmetic overflow refuses. Cells, bins and sessions are not additional independent mice.

Three comparisons have different meanings:

1. **Existing primary, preserved:** fixed context/handle ridge loss minus joint candidate loss. This measures improvement over a fixed transparent anchor. It does not by itself show that neural information helped.
2. **Additive matched-candidate contrast:** candidate context/handle loss minus candidate joint loss, with the same submitted procedure, allowed calibration, temporal access and resources. GrC-only and CF-only contrasts are reported as fixed secondary ablations. The joint condition remains primary; no best-arm selection. This contrast estimates incremental predictive utility of neural availability conditional on the specified learner and protocol. It is not causal or semantic understanding.
3. **Descriptive alignment diagnostic:** loss for mismatched neural bundles minus loss for the original joint queries, using the **same already fitted joint predictor**. A positive value means alignment helped that predictor. Do not refit the candidate on the mismatched query panel.

The first gain decomposes arithmetically into improvement of the candidate context model over the fixed ridge plus the matched neural increment. This matters: a better behavioral predictor can improve the fixed reference while producing zero neural increment. The engineering controls exercise that case explicitly.

`mismatch_query_packet(joint_view)` cyclically assigns query trial i+1 modulo n within the same session to recipient i. Neural time, GrC and CF travel together; recipient handle/context/IDs stay fixed. The function returns query-only data and a separate operator-only donor record. It requires at least two query trials; if any case lacks support, the complete mismatch diagnostic is unavailable rather than case-pruned. No randomness or label-dependent selection is used. This single mismatch is descriptive: it neither preserves temporal dependencies as an exchangeability test nor supplies a permutation p-value. Its execution with one frozen fit remains unverified by the pure evaluator.

## Baseline adequacy, uncertainty and remaining holds

The existing ridge uses train-only normalization and coefficients, a fixed alpha grid selected on development MSE, and no development refit. Its same-bin handle means/velocities and timing features are a useful reproducible anchor, but they are not evidence of a strong nonlinear/full-window behavioral baseline. A matched context candidate is required to distinguish that limitation from a neural effect. Empirical baseline adequacy, matched agent/baseline modes, sensible temporal models, and all original null/reference checks must be assessed on authentic packets before scientific acceptance; no new trained baseline is claimed here.

Retain every trial/session/mouse result and the five paired mouse gains. The evaluator adds only their descriptive range, explicitly with no confidence interval. A prospective mouse-level inferential convention and practical-effect threshold remain to be frozen before outcomes. Five animals limit inference; tiny engineering fixtures do not establish power, reliability, generalization or a neural effect. No iid-bin confidence interval, repeated-session population claim or mismatch permutation inference is justified.

All 14 installed runtime gates and 11 canonical holds remain open. In particular, official access, native format, true session/mouse identity, contact/clock support, cohort/QC eligibility, whole-recording preprocessing exposure, rights, runtime isolation, reference adequacy, independent replication and resource/uncertainty protocols are not settled by this companion. Admission, scientific qualification and benchmark-count deltas are zero. The Dryad data grant remains separate from the unlicensed external author MATLAB code; this addition vendors neither data nor author code.
