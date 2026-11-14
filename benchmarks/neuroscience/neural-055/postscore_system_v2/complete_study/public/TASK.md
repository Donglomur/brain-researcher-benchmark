# NEURAL-055: repeated-image EEG identification

Identify which of200 candidate images produced each of200 EEG responses from one held-out participant. Each query averages all80 released repetitions of one image, and every candidate occurs exactly once. Return independent-query probabilities and a separate one-to-one batch assignment.

This is a new prospective draft of the benchmark, using the original17-channel released THINGS-EEG2 arrays and ten leave-one-person-out cases. Its numerical conventions and development split are explicit new construction choices, not asserted to be the author's published protocol or an already measured benchmark. The source delivery includes preparation and scoring code; actual data assets are separately required.

## Data and access

For your current case, `CASE.json` gives opaque query IDs and candidate IDs. `ASSETS.json` binds the query EEG, candidate image features, source channel/time coordinates and `TRAINING.json`. Query EEG has shape200×17×100. Candidate features follow the exact `CASE.json` candidate order. Training contains the other nine people's mean EEG responses to16,540 training images (four repetitions averaged), matched fixed-checkpoint image features and original training-concept IDs. The held-out person's labeled training EEG is not supplied.

Candidate image features come from a pinned, fixed image checkpoint, with no dataset-fitted transformation or EEG fitting performed by the shared extractor. Fit any further learned transforms within the development split. If constructing an author-derived reference, degree-four polynomial KernelPCA must not be silently replaced by ordinary PCA, and its fitting must also honor the split.

The original200 assessment concepts remain excluded from supervised training. Each original training concept's ten exemplars and all repeats stay grouped. The330 development concepts are the lowest SHA256 values of UTF-8 `NEURAL-055/draft1/concept-development/` followed by the original THINGS concept ID, among the1,654 training concepts. Ties use the concept string. The other1,324 concepts are inner fit concepts. For each outer case, inner validation holds out each of the other nine people in turn and the same330 development concepts. Every learned preprocessing, model-selection and calibration step obeys that separation. After the fold-specific policy is fixed, final refitting may use all original training concepts from the other nine people.

All program/policy development for an outer fold excludes the outer person's recordings. Start each fold in an isolated development context, freeze its recipe before receiving the unlabeled outer query batch, and do not transfer outcome-driven code/policy changes between folds while claiming untouched assessment. The overall construction recipe is fixed before outer outcomes. Overlapping training cohorts and public recordings limit independence and exposure claims.

You may inspect the entire unlabeled current-person batch and exploit the one-of-each candidate prior. Every compared method receives the same batch prior, permitted features, tools and explicitly supplied encoder condition. No method receives query labels or scoring feedback. Use only the current outer-fold public directory; another fold contains data that are held out in this case.

## Prediction format

Return a JSON object matching `PREDICTION_SCHEMA.json`:

- `schema`: `neural055-prediction-v1`.
- `case_id`: the current case ID.
- `query_ids` and `candidate_ids`: the complete respective200-ID rosters, each exactly once.
- `probabilities`:200×200 finite, non-Boolean values in[0,1], aligned to those row/column ID lists. Each row sums to1 within absolute tolerance **1e-6**. No evaluator renormalization occurs.
- `assignment`:200 candidate IDs, aligned with `query_ids`, using every candidate exactly once.

You may reorder the ID lists if all corresponding rows, columns and assignments follow them. Probability columns need not sum to1. The assignment need not equal row argmax or a prescribed optimization algorithm. Uniform probabilities and valid low-accuracy assignments remain valid submissions.

The probabilities describe independent-query predictions before applying the one-of-each assignment constraint. Do not substitute hard assignment indicators. Raw correlations are not probabilities; any probability conversion or calibration must be specified and selected using permitted inner development data before outer predictions. Normalization alone is not evidence of calibration quality.

The parser rejects missing/duplicate/unknown IDs, extra fields, nonfinite values, incorrect dimensions, invalid bijections and duplicate JSON object keys. Maximum serialized prediction size is4MiB per participant. This is a transport bound, not a compute allowance.

## Scoring

Primary participant Top-1 is `correct assigned pairs / 200`. The primary panel score is the arithmetic mean across all ten people. All200 queries for each of all ten people are required; no favorable subset represents a complete panel. There is no performance acceptance threshold.

Secondary independent-query Top-1 takes the largest submitted probability. Exact ties choose the first tied candidate in the original public `CASE.json` candidate order, regardless of submitted column order. That public order is frozen during preparation, before predictions and scoring; it cannot be selected using gold or predictions.

Secondary log loss is the mean **natural negative log probability** of the true candidate, first within each person, then equally across ten people. There is **no clipping**. True-class probability zero yields explicitly represented infinite loss; rows are never discarded. Assignment-assisted and independent-query accuracy remain separate metrics. Rank, uncertainty and biological-significance metrics are outside this draft scorer.

## Scientific scope

The EEG values are released noise-normalized, transductively whitened coordinates, not microvolts. Historical whitening uses both training/test covariance and repeat groups. This is zero labeled target-person calibration, not strictly inductive preprocessing. Whitened coordinates mix physical electrodes. Rapid presentation also permits preceding/following-image contributions; prestimulus activity is not guaranteed signal-free.

This is80-repeat identification in ten public people and a fixed200-image panel, not single-trial decoding or a new sealed cohort. Matched reference construction must include an adapted encoder without target-person feature selection, candidate-only and image-condition alignment controls. Published independent correlation-ranking scores are not directly comparable to this assignment-assisted, changed-calibration contract.
