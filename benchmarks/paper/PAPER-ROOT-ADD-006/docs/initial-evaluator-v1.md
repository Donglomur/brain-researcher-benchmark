# Initial localizer-to-choice evaluator

This package computes three localizer-trained outcome decoders, response-time-censored first-level neural probability/reward effects, and a prospective nested participant-held-out comparison predicting behavioral parameters. It is a complete numerical pipeline at a declared primitive-export boundary. It is **not** a complete native paper reproduction or a scientifically qualified benchmark. Canonical task/history remains unchanged.

## Source contract and resolved semantics

The canonical task SHA256 is `c4d1438fbdf13e3ecb5d5ce8ead240d10f0115b046bb63edc7c1144d96f9daf4`. The source is [Russek et al., Nature Communications (2024)](https://www.nature.com/articles/s41467-024-48547-z), [open-access primary article](https://pmc.ncbi.nlm.nih.gov/articles/PMC11106265/), data [ds005065 version 1.0.0](https://openneuro.org/datasets/ds005065/versions/1.0.0), and author code revision [`1c9b3c92c77d4f5a4e4ccfa36d5a695814a2f612`](https://github.com/evanrussek/MEG_Heuristics_Risk_Preferential_Information/tree/1c9b3c92c77d4f5a4e4ccfa36d5a695814a2f612). `provenance.json` records primary source paths, content hashes and specific interpretation limits. No author code is vendored.

The pinned `Train_Classifiers_Apply_To_Task.m` selects localizer blocks 1–3. Image classes are `1=O1, 2=O2, 3=OS, 4=C1, 5=C2, 6=C3, 7=C4`. Each of the three outcome classifiers learns against all seven image classes plus one null example per localizer trial at −200 ms. The binomial negative log likelihood is averaged over examples and penalized by `0.002 * sum(abs(beta))`; the intercept is unpenalized. The independent solver uses nonnegative split coefficients and a projected-gradient convergence certificate. Solver equivalence to MATLAB `lassoglm` is not established.

The paper specifies division by the 95th absolute percentile. The pinned script calls an absent `scaleFunc` separately for localizer and task data. This implementation prospectively uses NumPy's linear-interpolated 95th percentile of **all absolute localizer-plus-null matrix entries**, fitted separately for each training time and reused for task epochs. It does not center sensors. Scalar pooling, interpolation and reuse on task data are prospective choices that protect assessment preprocessing; they are not claimed as an exact reconstruction of the unavailable helper. The source time grid is 0:10:500 ms, whereas paper descriptions and primary inference domains differ. A caller must predeclare an increasing subset of that grid; no interpolation or assessment-selected peak is allowed by this evaluator.

`Task_Reactivation_Analysis.m` applies the sigmoid to logits, then jointly regresses `RP(O2) − RP(O1)` on:

- intercept;
- `(5 − choice_number)/5 − 0.5`, where `choice_number` is 1–4;
- `abs(o2_val) − abs(o1_val)` in raw reward units.

Each test time retains trials with `rt_ms >= test_ms`. Safe reactivation is the mean sigmoid probability of OS over precisely the same trials. This implementation reports each participant and eligible-trial count and rejects a first-level design with fewer than four retained rows or rank below three. This is a prospective failure rule; the author script uses a pseudoinverse without identifying rank failures. Paper Equation 7 reverses both response and predictors and uses the full probability contrast: **the pinned-code probability coefficient is twice the paper-equation coefficient**, while the reward coefficient is unchanged.

All 21 release participants `sub-S001` through `sub-S021` must appear. First-level results retain all 21. Second-level analysis excludes `sub-S006` and `sub-S019`, as explicitly identified by the source; the paper associates these exclusions with repeatedly choosing the same action. BIS is not an endpoint here. Metadata roster coverage does not authenticate empirical participants.

## Prospective behavioral comparison

This extension predicts `beta_prob` and `beta_rew` separately using nested leave-one-participant-out ridge regression. It does not recreate the paper's robustfit statistics, Gaussian-smoothed maps, hierarchical behavior estimation, integrated BIC or permutation significance. The paper/source peak-domain mismatch (observed maps include initial training rows but permutation maps drop the first two) remains unresolved for native reproduction.

At each candidate training/testing time cell, the baseline includes the other neural effect, safe-outcome reactivation, and three participant-level task controls: mean and standard deviation of `abs(p1*o1_val + p2*o2_val − safe_val)` and mean `abs(o2_val) − abs(o1_val)`. Here `p1=choice_number/5`, `p2=1−p1`. Expected-value distance is an explicitly prospective objective difficulty control; it is not the participant's fitted subjective value. The augmented model adds the target neural effect. Each model selects its time cell and positive ridge penalty independently using inner participant-held-out mean squared error, entirely within each outer training cohort. Feature standardization and target centering are fitted anew within every training fold. Deterministic ties use score, time indices, then penalty.

Outputs include every held-out prediction, truth, selected time and penalty, training participant list, baseline/full MSE and paired MSE improvement. A fixed-seed 2,000-resample participant bootstrap describes uncertainty in fixed cross-validated losses; it does not account for overlap of model training folds or uncertainty in estimated behavioral targets. It is not a confirmatory significance test or registered reward.

Published behavioral parameters were estimated with hierarchical EM. Simply holding out the observed target does not remove information passed through shared population priors. Consequently each input must declare a participant-only behavior fit, no shared prior, and unverified native parity. Shared-population-fit declarations are rejected. The declaration is **not authenticated** by this package; participant-independent label construction remains a scientific admission gate. The native launcher also refers to missing `likfuns2.jl` and undefined parameter lists, so this package does not imply a runnable native behavioral reference.

## Input boundary and operation

Use an existing Python 3.11 environment with NumPy and SciPy. Validation used Python 3.11.6, NumPy 2.4.6 and SciPy 1.17.1; the exact validation interpreter is recorded in external construction evidence. Select an existing environment that provides these dependencies before running the commands below. No installation is performed. From the package directory:

```sh
python3.11 evaluator.py /absolute/path/manifest.json /absolute/path/result.json
python3.11 -m unittest discover -s tests -v
```

`manifest.json` is JSON with `schema_version:1`, `task_id`, exact `contract_sha256` and `source_revision`, `input_kind` either `generated_engineering_control` or `unqualified_primitive_export`, `event_table_conversion_status:"unqualified"`, predeclared `train_ms`, `test_ms`, positive `ridge_alphas`, and `participants` in complete source order. These frozen settings and their SHA256 are included in results; an external protected operator must govern when the manifest is frozen.

Each participant supplies:

- `participant_id`; unique nonempty `localizer_trial_ids`, `task_trial_ids`, and `sensor_names`; localizer/task IDs must be disjoint within participant;
- relative `arrays` filename and its `arrays_sha256`;
- `behavior_parameters:[beta_prob,beta_rew]`, a nonempty `behavior_parameter_provenance`, and `behavior_parameter_fit_scope:{"participants":["sub-S001"],"cross_participant_prior":false,"native_model_parity":"unverified"}` with the actual participant ID;
- `provenance.release:"ds005065/1.0.0"` and `provenance.native_paths` with exact release-relative localizer/task/events paths shown below.

The NPZ file contains exactly `localizer`, `task`, `localizer_ms`, `task_ms`, `image_class`, `block`, `choice_number`, `o1_val`, `o2_val`, `safe_val`, and `rt_ms`. Epochs are numeric trial × sensor × time arrays; vectors align with the corresponding epoch axis. Image class/block vectors align to localizer rows; choice/reward/RT vectors align to task rows. IDs and sensor names record the primitive export's claimed ordering; an independent exporter must establish their native truth. The loader verifies finite numeric arrays, exact timestamps, shape/alignment and packet content hashes. It never enables pickle and never attempts to deserialize opaque MATLAB/MCOS objects. Path traversal and false qualification assertions are rejected.

The exact release mapping for `sub-S001` is:

```text
localizer: derivatives/Epoched_Preprocessed_Data/Epoched_Localizer_Data/sub-S001_Epoched_Localizer_Data.mat
task: derivatives/Epoched_Preprocessed_Data/Epoched_Task_Choice_Data/sub-S001_Epoched_Task_Choice_Data.mat
events: derivatives/Event_Info_Tables/sub-S001_table.mat
```

Source loader names are instead `Subj_1_Epoched_Train_Data.mat`, `Subj_1_Epoched_Task_Choice_Data.mat`, and `Subj_1All_Event_Time_Table.mat`. The mapping above records release metadata; it does not prove content equivalence, run order or event-row correspondence. Source expectations are concatenation of localizer run cells and task run cells, selecting phase LOC blocks below four and TASK CHOICE events. A safe native conversion remains outstanding. The generated test helper `tests/test_evaluator.py::write_packet` is an executable example of the exact manifest/array schema, and its labels/provenance are explicitly engineering controls.

## Verification and remaining gates

The tests run bounded generated controls: analytical coefficient recovery, simultaneous correlated predictors, RT boundary/rank failure, closed-form logistic intercept and ridge reference, other-task-row perturbation independence, held-out-target mutation invariance, complete 21-participant pipeline with 19 retained, and missing participants, bad hashes, path escape, object NPZ, population-prior labels and false qualification rejection. They establish implementation behavior only. No authentic arrays, model service, native analysis, dataset archive or scientific run was used.

Outstanding gates include native MCOS extraction and authoritative event/channel/participant joins; full authentic population and content hashes; native scaling/solver/behavior parity; source probability coefficient units and inferential-domain reconciliation; authenticated independent target fits; protected references and isolated candidate replay; equal access and resource budgets; exact grading targets/tolerances; code/component/stimulus rights; and authentic runtime, full lifecycle storage and independent scientific qualification. Data CC0 is recorded by the canonical contract; code license is absent. Public access and source results do not establish blind evaluation, frontier improvement or causal benefit of code access. Every result keeps `scientific_readiness:"unknown"`, `scientific_qualification:false`, and `whole_paper_reproduction:false`.
