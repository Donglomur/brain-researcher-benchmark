# Human ripple model artifact comparison

Submit one strict UTF-8 JSON file, at most 32,768 bytes, describing the three phase models below. This component compares model diagnostics with a fixed local reference; it does not run your code or establish how your estimates were obtained. The original paper reconstruction and an A/B code-access experiment remain outside this component.

The declared reference fits each phase with numeric ACC=0 for wrong and1 for correct, raw trial unchanged, and formula `response ~ ACC * trial + (1 | subject/channel)`, REML, unit weights, zero offset. Contact means the nested pair(subject,channel), not a pooled channel string. The fixed coefficient names are `(Intercept)`, `ACC`, `trial`, `ACC:trial`. Response uses released source ripple-rate units; no additional scaling is implied.

Use exactly the top-level keys `schema_version`(integer1), `task_id`(`PAPER-FIND-003`), `input_sha256`(the literal `input_sha256` field value in `PUBLIC_CONTRACT.json`), `submission_status`, and `models`. Include exactly one model entry for stimulus, feedback and interval, in any order. Each entry has exactly `phase`, `status`, `reason`, `fit`. A reported entry has status`reported`, reason null and the fit below. An abstained entry has status`abstained`, a nonempty reason up to512characters and fit null. Overall status is `complete` for three reports, `partial` for one or two, `abstained` for zero. The supplied whole_abstention.json is a fully valid example with no numerical payload.

Every reported fit has exactly these six fields:

- `coefficients`: an object with all four exact named coefficients.
- `covariance`: `{axes:[four unique coefficient names], values:[[four numbers],...four rows]}`. Include the entire4×4 covariance, including cross terms. Row and column order both follow axes; consistent permutations are accepted.
- `variance_components`: absolute variances with exact keys `subject`, `nested_contact`, `residual`. These are source ripple-rate squared, not standard deviations or relative theta.
- `support`: integer `n_obs`, `n_subjects`, `n_nested_contacts` and `row_ids_sha256`. The digest is SHA256 of ascending original wide data row IDs, each decimal integer followed by LF, including the last. Row1 excludes the CSV header. These are claims compared with the reference, not proof of input use.
- `method`: exact keys `estimator`(REML/ML/other), `random_effects`(subject_plus_nested_contact/subject_only/contact_only/pooled_contact/other), `weights`(unit/other), `offset`(zero/other). A different claim remains gradeable and is reported separately.
- `reml_diagnostic`: null, or `{criterion:number, convention:string}`. The supported comparable convention is `lme4_profiled_REML_original_design_including_constants`; `other` is accepted but not compared as the same objective.

The fixed phase counts are8052/8058/8074, with34subjects and181nested contacts per phase, from8082wide rows. The public contract and schema provide exact identities and limits. Missing phase reports must be explicit abstentions. Ordinary admission forbids unknown/duplicate keys, NaN/infinity, numeric booleans, destructive underflow and nonfinite binary64 values. Finite negative variances or asymmetric covariance are retained as numerical/math diagnostic errors rather than silently repaired.

The primary reported discrepancy is the signed interval correct-trial slope error: `(beta_trial + beta_ACC:trial)_candidate − reference`, in ripple-rate/trial. The full report also preserves all coefficients, complete covariance, variance components, four derived contrasts and their covariance, optional objective and support/method agreement. Derived contrasts are wrong slope, correct slope, interaction, and ACCdifference at trial0. Covariance units depend on the number of trial-slope factors; the scorer does not aggregate mixed units. Fixed required denominators are12coefficients,48covariance entries and9variance components; partial reports never shrink those denominators. Whole abstention and malformed artifacts are handled without reading private fitted models.

Lower absolute error means closer numerical agreement. There is no single blended reward, significance claim, scientific pass threshold, or inference that a submitted fit is globally optimal. A zero score is numerical agreement with this specific reference. Ordinary file scoring does not establish a new fit, hidden evaluation cohort, independent experiment, or research readiness. No private reference parameters or answer files belong in the public packet.

Local scoring command:
`python3 tools/neurobench.py score PAPER-FIND-003 --submission submission.json --output artifacts-build/FRESH --review ROOT_REVIEW.json --other-reserve-bytes 102000000`
Each invocation requires a separately pinned current-cost allocation. This command grades a submitted artifact; it does not execute a submitted analysis program.
