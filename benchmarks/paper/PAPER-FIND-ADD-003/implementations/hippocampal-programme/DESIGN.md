# Hippocampal sequences: complete selected-program design proposal

This is a design checkpoint for canonical PAPER-FIND-ADD-003, not an implementation or scientific result. The accepted selection is commit384fd5dc1b67930f63c24bf96b71d088ae41c506. Root and sole peer paper_c must accept the scientific/interface choices before dependent implementation. All earlier sources stay immutable. No original observation, paper body, model, credential, native process or provider was accessed or executed in this lane.

The recommended question is: **does the current local CA1 representation contain first-odor information beyond simultaneous movement, licking and timing priors, and can a candidate improve the independently fitted matched comparator?** This follows the paper's odor-specific sequence finding while separating current representational information from memory carried forward inside a predictor. It is not chosen because the input is small: all23 behavioral animals, the same11 imaging animals/44 sessions, four days, two imaging variants and eight native families remain mandatory.

## Scientific choice requiring review

| Choice | Information available per query | Scientific claim supported | Method restriction |
|---|---|---|---|
| Recommended: local current representation | One of five disjoint15-frame windows covering source frames95:169; no other query window/trial | Information available in each current local delay representation, conditional on the specified nuisance controls | Deterministic, bounded, pure arithmetic graph; no cross-query state or executable inference callbacks |
| Alternative: whole common-delay trajectory | All75frames95:169 for one held trial | Information in the common-delay trajectory as a whole | Arbitrary isolated predictor; fresh state per trial; no inference about later-bin persistence |

The alternative is scientifically meaningful and allows broad temporal/recurrent methods. However, a classifier can use only early-delay evidence and still score well, so it cannot answer the recommended per-time representational question. The local design includes strong nonlinear models: MLPs, Gaussian-kernel predictors, local temporal CNNs, fixed tree ensembles, within-window attention and finite recurrent unrolling can all compile to the proposed graph. It does not allow every possible frontier method. Online adaptation, stochastic inference, dynamic loops, external tools, methods that require earlier query windows, and methods beyond the declared graph/resource capacities are outside that condition. The choice and these restrictions must be explicit; computational convenience alone is not the justification.

The five fixed windows are95:109,110:124,125:139,140:154 and155:169, one-based. Every one of the75 source common-delay frames is covered once. This is a prospectively declared15-frame discretization, not a claim to reproduce historical half-second bin edges. Actual frame clocks must verify that the full interval lies after first-odor offset and before second-odor onset for every required trial. A mismatch blocks the selected support; it does not authorize a convenient new window. Both preprocessing variants remain required. The unsmoothed/no-flooring variant is the prospective primary; the original variant is a separate mandatory paired sensitivity, not extra animals or automatically an improvement.

## Original reproduction and independent reference

The common paper is the exact held PMC12588557.1 author-manuscript PDF associated with DOI10.1016/j.celrep.2025.116383; its final citation date is separate from the carrier and first appearance. Both A and B receive that same paper and protocol. B alone receives the19 exact author files from ccdorian/dDNMS2025 at5e74479bbf97d47c14133cab5fea40a496ec7d94. Neither candidate receives private reference wrappers, outputs or scorer source. An A image must exclude study-specific author/operator source entirely, not merely alter PYTHONPATH. Generic MATLAB and numeric tools may be common.

The exact originals remain Dryad v400039 all23behavior.mat, rawtrialsstand2torev2_n11.mat and rawtrialsstand2torev2_nosmoothnoflooring_n11.mat, totaling23,042,208,359 bytes with publisher SHA256 values in DEPENDENCIES.json. Actual biological/ROI/trial/clock/variant membership remains unverified. Dryad's held official documentation requires authenticated downloads; the other lane's anonymous401 was for a different exact file. This task does not select acquisition or inspect credentials.

The native reference consists of11 independent complete callable invocations: behavior once, then short sequence, long sequence, time, odor and information for each variant. Each invocation preserves its own original RNG reset and ordered animal/day/ROI/fold computation. The summed declared original-file extents across those loads are115,094,824,195 bytes, not a measured read count or memory budget. Existing wrappers load whole originals. A lazy or split execution would require a separate source/RNG-fidelity review.

The full native output has28,434 slots per variant,56,868 total:

| Family | Slots per variant |
|---|---:|
| Behavioral accuracy |368|
| Behavioral lick latency |368|
| Sequence peak fractions |154|
| Sequentiality index |176|
| Time-bin correlation |176|
| Full time confusion matrices |8,624|
| All odor-decoding accuracy families |12,056|
| Historical odor-information family |6,512|

Behavioral slots are duplicated identically across variants. Preserve source condition/day/mouse order, all undefined entries and every required family; there is no favorable subset or combined cross-unit score. The existing absolute-error metrics remain separate by physical unit and are aggregated within animal, then across animals equally.

The source audit identified consequential fidelity gates. Time decoding subsamples10,000 eligible cells when its eligible count exceeds10,000; its 'all cells' comment is not a guarantee. Odor decoding attempts SVM fits on all padded second-alignment bins before later overwriting the first seven outputs. A failed fit cannot be replaced with a fabricated NaN. The historical `odor_information` name refers to per-cell activity information about baseline versus current time within each condition, not direct odor-label mutual information. Behavior takes the first retained lick in source list order; actual chronology is still a validation issue. Preserve all source matching arithmetic, strict inequalities, tie rules and RNG consumption, including known expressions that differ from their comments.

Conditional on declared geometry/support and no earlier failure, the native odor branch alone attempts168,784 fitcsvm calls across the two variants. Time ECOC and sequence shifts add further data-dependent work. No actual runtime, fit count, native/default parity or historical publication result has been established. MATLAB R2021a, its exact update/platform, Statistics and Machine Learning Toolbox, numeric libraries and licenses remain qualification dependencies. Python substitutes are not historical reference equivalence.

All56,868 positions need a disposition ledger, not just finite/null values: finite, source-structurally undefined, computed source-undefined with observed provenance, native failed, or unstarted. Failure/unstarted cannot become null. Preserve original native artifacts and diagnostics. Inf/complex or other values rejected by the existing contract remain explicit admission gaps; do not clip or recode them to force reference completion. A private reference is admitted only after complete output/source identity, natural process exit, original-clock/resource closure and independent operator provenance. Candidate outputs and published answer MATs never supply gold.

## Labels, data preparation and inherited exposure

The source compares the observed A=1/B=2 odor pair to the final two digits of progress codes. Codes11,12,511,512 begin with odorA;21,22,521,522 begin with odorB. The upstream check merely prints a mismatch, so actual physical label validation remains unresolved. Future preparation must reject unsupported codes and preserve this upstream limitation rather than invent corrected labels.

Selected-session source explicitly uses `.spks`, `.roistats`, `.beh`, `.locomotion` and `.licking`, with the common `.frametimes` axis. No raw-pose dataset is requested. The held alignment constructor lacks locomotion/xoff/yoff fields required by downstream preprocessing; this is a provenance gap, not proof that the released nuisance arrays are absent. Full44-session and paired-variant nuisance shape, units and clocks are admission gates.

Twenty-trial groups correspond to acquisition `ses` chunks only if the original seven-chunk ordering is authenticated. The source smooths and floors within each acquisition chunk before concatenating trials, not necessarily across the whole day. Shared upstream Suite2P/cell selection/deconvolution can still expose other chunks. A one-trial purge cannot undo those upstream operations. Native reproduction retains the actual retrospective source preprocessing; prospective newly learned transformations are training-only. Do not describe the released processed data as raw, wholly inductive or a causal online signal.

Preparation will authenticate the three full originals, generate the complete structural census and preserve all original axes/identities. It will project all required native/prospective views without fitting models or selecting favorable cells. Original byte identities, structural observations, variant alignment and projected-view pins stay separate. Unknown decompressed memory, ROI counts, missingness, lick-event counts and actual allocation must receive prospective resource limits before execution. Exceeding a cap blocks preparation; it never permits cropping the cohort.

## Prospective split, support and information boundary

Retain308 outer folds:11 mice×4 days×7 original20-trial chunks. Each query block contains all20 trials and all five local windows. The nominal120 training trials lose the immediate predecessor and successor of the held block where present:119 at the edges and118 internally. This fixed conservative purge is prospective and does not certify removal of upstream contamination or raw-window overlap. No query trial is purged. Actual chunk ordering and source temporal provenance must be admitted separately.

The six remaining original chunks define nested validation. Each validates over its eligible outer-training members once; inner training excludes that validation chunk and its immediate neighbors, while retaining the outer purge. All bins of a trial remain together. Pool complete inner out-of-fold predictions for parameter/threshold selection. Do not assume a20-trial fold or a condition contains both odor classes. A fitted training set requires both classes; otherwise record failure. Single-class strata get recall/support. Balanced accuracy requires an explicit pair of class supports in the complete out-of-fold result. Missing class or unsupported data cannot be dropped to rescue the primary endpoint.

A local neural view exposes only the current15-sample window on the full source ROI axis, with a typed finite/missing mask. Baseline ROI quality uses the immutable source `iscell>0.3` rule; newly learned feature selection/scaling/imputation uses training only. Candidate feature selection may be trained, but its full mask and provenance must remain auditable. Source iscell/QC is inherited exposure, not newly train-only discovery.

Nuisance views contain only local locomotion samples and local lick counts. Lick temporal cells use exact frame-midpoint edges; no future response, outcome, actual delay or odor-coded condition appears in a predictive view. The current-window one-hot clock is available to nuisance/combined/prior controls, but not to neural-only. There is no prospective time-label target in this design; native time reproduction is a separate endpoint. Any future time-prediction design must remove a clock that directly supplies its target.

The graph receives feature arrays only. Opaque independently shuffled query IDs stay outside it; source trial IDs, acquisition order, other query windows and chronological state are unavailable. Fresh workspace is mandatory per record. Candidate program sources are committed before numerical exposure; native and prospective stages have fresh isolated environments and transfer no fitted artifacts. Public original releases and published answers still make this exposed-source research, not guaranteed unseen-data evaluation or proof against prior memorization.

Mice are the independent aggregation/uncertainty units. Four sessions per animal, five windows, repeated trials and two preprocessing variants are nested measurements. Cells are session-specific and not tracked across days. Held trial/chunk or held reversal is not held-animal or new-session generalization.

## Matched competent comparison

Five mandatory families are neural, nuisance_clock, combined, clock_prior and shuffled_combined. The same candidate program and declared search policy run under the corresponding information restrictions; available optimizer telemetry is retained, not trusted as independently measured work. The independent comparator is built separately and never derives weights, selected parameters, seeds or scores from a candidate.

The source-compatible linear SVM is a matched reference family, but comparison is not confined to a weak default fit. The independent prospective search has20 configurations: four C values(2^-6,2^-2,2^2,2^6) for mean-window linear SVM; the same four for flattened-window linear SVM; and twelve Gaussian flattened-window models crossing those C values with gamma multipliers(.25,1,4)/feature dimension. Class-balanced weights, scaling and missing-value transformations are fitted on training only. The Gaussian kernel is explicitly exp(-gamma×max(0,squared distance)); do not infer an unverified package KernelScale convention.

Every trained reference model attempts20 configurations×6 inner folds, then one final refit:121 nominal fits. Threshold calibration uses only complete inner out-of-fold margins: finite adjacent-score midpoints plus exterior decisions, maximizing paired-class balanced accuracy. Ties use closeness to zero and then lower threshold; model ties prefer lower complexity, then lower C and fixed kernel order. No calibrated-probability claim follows. All failed/unstarted configurations are retained; all-invalid search makes the reference incomplete. No query outcome chooses a configuration, formula or threshold.

The trusted MATLAB fitter and typed export must be source-bound and later qualified, including native convergence diagnostics and a training-only graph/native-predict round trip. Unknown API or failed round trip remains incomplete; never try alternate coefficient conventions until query agreement looks good. The original default native classifier remains in reproduction and is not relabeled a prospectively tuned historical result.

The shuffle control permutes labels per training trial within eligible acquisition chunks and replicates that label across all five windows. It uses a fixed prospective seed and no query labels. Clock/prior is analytic, using training class priors per window with global-prior backoff and a declared class0 tie. It is not an adaptive hidden-answer control. All original native source RNG resets stay unchanged and separate from prospective randomness.

## Proposed pure inference graph

The model artifact is typed JSON plus inert finite numeric arrays. It contains no executable deserialization, imported model class, Python callback, filesystem/network operation or mutable predictor state. A trusted evaluator checks graph topology, shapes, axes, constants and resource bounds before evaluation, then creates a fresh value workspace for each one-window record. Constants and inputs are read-only. Graph contents never receive query IDs, labels or other records.

Proposed primitives are input/constant, reshape/transpose/slice/constant-index gather/concat, matmul, add/subtract/multiply/divide, sum/mean/max/min, abs/square/sqrt/exp/log/tanh, elementwise min/max, comparison, where and softmax. Local CNNs can use gather+matmul; attention uses matmul/softmax and explicit normalization; tree ensembles use comparisons/where; a recurrent model can be unrolled only inside the current window. Reference linear and Gaussian SVMs export the same interface. This is an expressiveness restriction requiring review, not unrestricted arbitrary inference.

The design proposes a10,000-node structural ceiling. Constant bytes, tensor shape products, peak live array bytes, arithmetic work and phase time must be explicitly admitted from the full schema and selected resource policy. Static bounds are not observed RSS. A method that cannot fit or compile is unsupported; no silent reduction of input or an assertion that all frontier methods were searched. Strong nonlinear candidate and reference forms must pass meaningful invented controls after design acceptance; none has run now.

The alternative whole-delay design would remove the graph restriction and allow arbitrary isolated per-trial predictors, while relinquishing every per-time/current-representation claim. Root and peer should choose based on the scientific question and expressiveness, not only process startup cost.

## Complete workload and executable source plan

For the recommended design,3 roles(A,B,independent reference)×2 variants×308 folds×5 families gives9,240 model slots. Of these,7,392 are trained producers and1,848 are analytic prior slots. Every model has20 held trials×5 windows, so private inference evaluates924,000 records with fresh workspace per record. The independent reference has2,464 trained models and298,144 nominal prospective SVM fits. Native11-call reconstruction, its168,784 nominal odor fits, additional ECOC/shuffle work and all preparation are additional. These are source-derived schedule counts, not measured feasibility or extra benchmarks.

The final implementation must contain a real executable composition, not callbacks awaiting an unspecified provider:

1. Start the original global clock before policy, source, image and exposure admission. Validate complete role/image/source manifests and resource reservations.
2. Authenticate originals and execute/admit the complete structural preparation separately. Retain every missing/incompatible disposition and exact projected-view identity.
3. Launch unrestricted native A/B producers and the independent11-call reference through concrete isolated transport; capture all outputs, RNG/attempt records, costs and external closure.
4. Launch all prospective training producers with training-only views. Construct all analytic prior slots. Seal every model before any private query evaluation; missing slots remain failed/unstarted, never successful omissions.
5. Evaluate all9,240 model slots over their complete local records in the trusted stateless evaluator. Retain all924,000 prediction identities/statuses and complete out-of-fold support.
6. Admit candidate/native/reference artifacts and independently observed process closure before private native/prospective comparison. Score neither missing nor uncertified reference as success.
7. Produce the complete report and attempt/failure/resource ledger, then independently observe terminal cleanup. Release retained-byte credit only after owned artifacts are durably retired.

Exact reviewed OSL transport source supplies concrete Docker staging, gated launch, socket capture, holder, process observation, original-clock bounds and cleanup recovery. Its immutable source pins are in DEPENDENCIES.json. H will add actual task-specific preparation, MATLAB producers, graph/model capture, query evaluation, private grading and the outer scheduler. The OSL donor remains unchanged. Actual Docker images, kernel behavior, MATLAB licenses, provider telemetry and numeric/reference competence remain unqualified. No image, process, native function or scoring operation runs during this design task.

## Scores, limits and readiness

For each mouse/day/window, first pool all140 outer out-of-fold predictions. Report classA and classB recall and their supports; BA is their equal mean only with both complete class supports. Average the fixed four days×five windows within mouse, then the11 mice equally. Primary improvement is candidate combined BA minus independently training-selected reference combined BA in the unsmoothed/no-flooring variant. The original variant is reported separately. All families, variants, day/window results, confusion matrices, margins and undefined masks remain visible.

Report all11 paired-mouse differences and descriptive mean/SEM only with complete support. No post-hoc significance gate or favorable support removal is selected. Better combined prediction alone does not identify a marginal neural effect: matched nuisance/clock/shuffle controls and method differences must be reported. This is not CA1 causality, theta inference, raw online decoding, new-animal generalization or a protected-code-benefit estimate.

The full selected native endpoint is not every trajectory/PCA/locomotion panel, original statistical test, raw movie or figure annotation. Published comparison outputs do not establish true biological claims. No private numerical reference, actual inputs, source environment or program runtime is qualified here.

The author source has no verified top-level redistribution license. Local source read/build is authorized; public export of author bodies or restricted derivatives is not. DEPENDENCIES.json separates actual metadata/source hashes from inherited paper/data identities. Resource ledgers keep this H grant separate from prior selection/OSL work, and preserve the source-locator failure. No controls or fixtures have executed. Root and peer acceptance of this design is the next gate.
