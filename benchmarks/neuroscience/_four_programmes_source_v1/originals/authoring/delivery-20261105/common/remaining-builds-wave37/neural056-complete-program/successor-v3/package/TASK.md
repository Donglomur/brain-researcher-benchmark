# NEURAL-056: complete image-to-EEG modelling

Predict every coordinate and time point of all 200 test-image responses for each of ten THINGS-EEG2 participants. The full target is the mean of all 80 test repetitions. Training contains 16,540 images from 1,654 disjoint concepts, four repeats each. One outcome block is [200,17,100]. Each role must produce all 30 participant/control blocks; cases, controls, modes and reference variants are not new benchmarks.

This source programme extends the existing canonical prospective task. It does not reproduce the paper's historical OLS, polynomial KernelPCA or random 40-repeat-half numerical endpoint. All original source recipes and scorer bodies remain in legacy/ with exact provenance. The canonical representation stays AlexNet ReLU7 (4096 values), resized224×224/ImageNet RGB normalization; the low-level control is bilinear RGB16×16 (768 values). Exact ImageNet checkpoint and complete numerical backend are unbound execution prerequisites, never inferred from a model name.

## Information and investigator state

The outer participant supplies no training or query EEG. Only the other nine participants' training partitions can inform the final prediction. Query images/features are legitimate inputs; query responses and reliability never reach actors.

Development uses all nine inner held-person folds. Fit means use the other eight people and all ten exemplars of each of1,324 fit concepts. Validation uses the inner-held person's four-repeat mean on all ten exemplars of330 distinct development concepts. The exact original opaque-concept hash rule is retained. Standardization is fitted on training rows only. The final nine-person mean over all1,654 training concepts is exclusively a refit view.

F commits one complete train/query program before seeing any neural views. Its fixed finite configuration roster is shared across contexts; the highest complete representation validation mean selects one configuration for all three arms of an outer participant. Ties choose the earliest predeclared trial. Missing or undefined validation scores refuse selection.

I uses a frozen model, prompt, tool schema, seed schedule, configuration roster and round budget. A **fresh session starts for each inner/final training context and each arm**. The LLM can ask a bounded Python tool to inspect its own X/Y: neural responses, feature distributions and derived summaries. It receives that tool's bounded JSON result. It sees no query inputs during investigation and no held responses. It then seals the actual generated train/query program and configuration; training seals the fitted model before a separate query process receives query features.

The next investigator context never receives prior raw views, generated source containing observations, fitted models, tool outputs or conversation state. Cross-fold selection transfers only aggregate development scores and the chosen predeclared configuration index. Final refit starts fresh under that selected policy/configuration. Every actual generated source/configuration and original tool/provider lifetime is recorded.

I arm matching is at the **frozen policy level**. Its comparison is not an identical-fitted-estimator ablation: different data may lead the investigator to generate different code. F retains identical pre-view code. Both have identical underlying training information, configuration-trial ceilings and per-outer application compute ceilings. Whole-role provider-token ceilings are equal; actual spending and unused allocations are reported, not described as equal actual cost. F can spend its selected finite authoring rounds before views; I spends its selected rounds inside fresh contexts.

This measures adaptive tool-assisted image-to-EEG modelling. It does not measure no-tools waveform comprehension. The submitted code can inspect training arrays in F; I additionally sees its own Python inspection outputs directly.

## Required references and controls

The fixed reference is centered ridge with unpenalized intercept, population-standardized training features and alpha1. A separate prospective tuned-ridge reference evaluates the fixed grid [0.0001,0.01,1,100,10000] over every inner person and control, chooses by the representation mean, and applies the same selected alpha to all controls. These references are implemented but empirically unqualified. The old fixed alpha1 source and result endpoint are preserved.

Three arms are mandatory: representation, low-level, response-permuted. The last uses identical4096 image features and a one-step rotation of complete ten-exemplar concept response groups, preserving coordinate/time vectors and within-group order. Inner fits rotate only their1,324 fit concepts; final fits rotate all1,654 training concepts. Opaque context/arm aliases hide the operator's arm mapping, although feature dimensionality reveals the low-level arm. These controls test training alignment; they are not guaranteed nulls or evidence of a unique neural mechanism.

The fixed reference, tuned reference, F and I each produce30 blocks (120 total study blocks). Separate processes train and query, with read-only source/model/input mounts and a fresh writable output. Providers and inspection tools are also source-owned isolated processes. Every started operation, failure, original stream, cost, code identity and descendant cleanup contributes to the full attempt.

## Endpoint and interpretation

Pearson correlation is computed across200 test images for each of all1,700 channel/time cells, then averaged equally across cells and equally across ten people. Constant predictions score0 with undefined raw correlation; a constant target makes the cell, person mean and full primary mean undefined. Nothing is silently excluded. Participant-paired representation-minus-control effects remain separate.

Odd/even40-repeat split-half correlation is descriptive and never corrects or rescales the primary score. The complete original collector/scorer is exercised after all120 outputs are admitted, and its per-coordinate results must match the new wrapper.

Released MVNN used training and test partitions and mixes channel coordinates. Values are released noise-normalized EEG, not microvolts. Session/sequence identities are unavailable; neighboring-image effects and model/stimulus exposure remain. This is exposed public-development data with transductive preprocessing, not a new blind population study, causal acquisition test or physiological electrode-localization claim. No confidence interval, binary success threshold or SOTA claim is supplied.

## Source-only status

No authentic arrays, headers, neural targets, checkpoint bodies, feature extraction, provider calls, fits or scientific scores were executed during construction. Ten independent qualification records, all archive/coordinate alignment, exact CPU/feature/model environments, original ownership/isolation and complete capacity remain gates. See GATES.json and OPERATOR.md.

## Actor and inspection interface

The frozen program is standalone Python using the qualified standard library and NumPy. It must accept these literal arguments:

    program.py --stage train --input /input/0 --output /output --config-json JSON
    program.py --stage query --input /input/0 --model /model --output /output --config-json JSON

In train, /input/0/context.json declares train_rows, feature_count, response_shape, opaque training identities and the seed. training.npz contains exactly x[train_rows,feature_count] and y[train_rows,17,100]. For inner training, train_rows=13240; final refit uses16540. The actor writes its chosen fitted model files under/output. It receives no query file in this process.

In query, context.json declares query_rows, feature_count and query image order. query.npz contains only x[query_rows,feature_count]; query_rows is3300 for inner validation or200 for final assessment. /model is the exact read-only output of the completed training process. Write exactly prediction.npz containing one finite float32/float64 array prediction[query_rows,17,100]. No additional file is admitted. Do not emit scores, modify model files or refit using query inputs.

An I inspection request returns an inspect action containing standalone Python. That process has only its own train directory mounted at/input/0 and writes exactly/output/analysis.json containing finite JSON. The JSON result is returned to the same LLM session; arbitrary stdout/stderr are retained privately for accounting but are not substituted for the typed tool result. A final action returns the train/query program and its realized finite configuration. The final source/configuration is frozen for that context before fit and query. No inspection session can access another arm, person, query file or held target.

All actors receive the same full input support within the selected arm; lower-level feature dimensionality is the intended control difference. The supplied fixed reference learns training population standard deviation (zero values become1), a training response mean and centered ridge coefficients. Query normalization reuses those frozen statistics. No network, runtime installation or checkpoint download is permitted.


