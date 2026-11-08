# FIND036 independent reference mathematics

This is future-executable operator source for the accepted full40-session processed head-withdrawal endpoint. It does not authenticate the original archive, reconstruct raw signals, perform a scientific comparison, establish numerical parity or supply a qualified runtime. The common paper HTML is narrative/captions only; complete paper-material access remains an explicit qualification blocker.

The controller provides complete source-clipped float64 feature matrices and binary int64 labels, 0=avoidance and1=escape. It preserves all units/bins and every original label3/4 observation. The mathematical layer rejects values outside[-5,5] rather than silently introducing a different preprocessing path. Full roster, original40-bin-per-unit width, row custody, original outer-fold assignment, shared transductive preprocessing and independent per-phase execution remain controller obligations. No observation, label, identity-key body or original author program was executed/read as numerical input here.

## API

- `fit_bnb(X_train,y_train)` returns two2×D log-probability arrays; `predict_bnb(state,X_query)` returns one escape probability per complete query row.
- `native_fold(X_train,y_train,X_query,session_token,fold_one_based)` returns query_rows×101 float64 probabilities, columns real,null0,…,null99. Native training order must remain source order. The token is the authenticated original session token, supplied only to the native context.
- `fit_references(X_train,y_train,inner_splits=None)` returns the entire mandatory panel's sealed numeric state. The supplied outer-training order is the controller's hidden permutation, fixed identically across A/B/operator. A supplied inner split must equal the canonical adopted sklearn1.6.1 split, including order. There is no test-data argument. No failed reference is replaced or omitted.
- `predict_references(state,X_query)` returns query_rows×3 float64 probabilities in the order BernoulliNB,nested_balanced_L2_logistic,constant0.5.
- `state_to_npz_members` and `state_from_npz_members` exchange exact numeric arrays only. They do not open/write an archive or use pickle. The parent must admit authenticated trusted operator state before materialization, enforce exact keys, NPY headers, expanded-byte caps and provenance, and use `allow_pickle=False`. This helper is not a candidate-model loader and does not certify archive security.
- `retained_state_bytes(D)` is exactly8(7D+54) numeric bytes; it excludes ZIP/NPY headers, Python objects, full input/output retention and optimizer workspace. The100-null output alone is8×101×query_rows bytes per fold. None of these formulas is a complete measured peak-memory bound.

## Original Bernoulli equations

The held original `HierarchicalEventClassifier.py` at revision2b74d2c2f8d6574b6a1b75c0feb99af5e18bb678 constructs `BernoulliNB(fit_prior=False)`, clips observations, retains HW labels3/4 and uses five stratified outer folds with shuffle and seed622. Its defaults mean alpha1 and threshold0. The independent implementation does not import that script or sklearn's estimator.

For featurej and classc, let b_ij=1[X_ij>0], n_c the training class count and s_cj=sum_{i:y_i=c}b_ij. Then p_cj=(s_cj+1)/(n_c+2). With equal priors, the class log-score is log(1/2)+sum_j[b_j log(p_cj)+(1−b_j)log(1−p_cj)]. We compute the escape probability with a stable sigmoid of score1−score0; the shared prior cancels. Constant features and all observation dimensions remain. Both classes must occur in training. This derivation is algebraic source correspondence, not historical BLAS/floating-point parity. Source outputs for other event tasks and feature importance remain outside the selected endpoint.

For each native fold andr∈{0,…,99}, the first16 SHA256 digest bytes of UTF8 `FIND036|full40-null-v1|{session_token}|{fold1to5}|{r}` are read as an unsigned big-endian integer. A fresh NumPy `Generator(PCG64(seed))` shuffles a copy of the original training-label vector only. Query features, training feature order, counts and outer split stay fixed. Independent fold permutations are not one coherent global-label permutation and do not yield a calibrated permutation p-value. These100 controls reconstruct the separately named seeded control, not the paper's unseeded RNG history or51.62% bitwise oracle.

## Prospective logistic equations and selection

Each inner training partition separately fits mu_j=mean(X_j) and s_j=max(populationSD(X_j),1e−8). Constant columns remain; both its training and validation rows transform with that partition's mu,s. A whole-outer scaler before inner validation would leak validation information and is not used. These local scalers do not undo the original whole-session transductive normalization in released features.

The3-fold assignment is exactly `StratifiedKFold(n_splits=3,shuffle=True,random_state=623)` in the adopted sklearn1.6.1 runtime on the supplied outer-training row order. Every class must have at least3 outer-training observations, and each inner training/validation split contains both classes. All rows are held out exactly once. No split reduction or subgroup dropping is allowed. Supplied folds are checked against this generator, not merely accepted because they have plausible sizes. The library import is lazy and version-pinned; availability and algorithm execution were not established in the current NumPy-only engineering environment.

For scaled rowz_i, linear logita_i=z_iᵀw+b and class counts n0,n1, minimize

`L(w,b) = sum_i [1/(2*n_{y_i})] * logaddexp(0,(1−2*y_i)*a_i) + lambda*||w||²/2`.

The intercept is unpenalized. Each class contributes total weight1/2. Gradient_w=Zᵀ[weights*(sigmoid(a)−y)]+lambda*w and gradient_b=sum(weights*(sigmoid(a)−y)). This is the declared balanced loss, not a library C parameter with an unexamined normalization.

For each lambda in[.001,.01,.1,1,10,100], obtain one logit for every inner-held-out row from its corresponding training-only fit. Compute pooled balanced accuracy using the actual float64 sigmoid>=.5 decision. Ties in BA use lower pooled *unweighted* NLL, `mean(logaddexp(0,(1−2*y)*logit))`, then larger lambda. Float64 equality is the tie definition; no arbitrary tolerance or approximate tie grouping is introduced. No probability clipping occurs in selection. The report's[1e−15,1−1e−15] probability clipping convention does not change hyperparameter choice. Refit the chosen lambda and scaler on all outer-training rows. All6×3 inner fits plus the final refit must succeed.

The future solver uses scipy1.15.3 `minimize(method="L-BFGS-B")` with no bounds, analytic objective/gradient, zero initialization, maxiter10000,maxls50,ftol1e−12,gtol1e−8. This is its unconstrained limited-memory BFGS route. Other pinned-version defaults, including maxcor10 and maxfun15000, remain unchanged; either an unsuccessful exit or an exhausted limit makes the comparator unavailable. Recompute the final objective and gradient independently of the solver's stored diagnostics. Require finite theta, successful convergence and maximum absolute gradient<=1e−5, with reported iterations in0..10000. Solver/runtime/backend determinism and competence still require qualification; a source implementation or fake-success test cannot establish them.

The constant reference always returns.5 and cannot replace the two fitted comparators. Prediction uses the fixed full-training scaler and coefficients only; no target, adjustment or adaptive calibration is accepted.

## Numeric state and provenance

The exact12 member keys are schema,n_train,selected_index,log_p,log_not_p,mean,scale,theta,inner_ba,inner_nll,gradient_max,iterations. Scalar integers use one-element int64 arrays; iterations is int64 length19. All other members are finite float64 arrays with prescribed dimensions. log_p/log_not_p are2×D, mean/scale lengthD, theta lengthD+1, inner metrics length6, and final-gradient diagnostics length19. Validation checks probability consistency, scaler floor, selected-index tie rule and all solver diagnostics. A declared state is not evidence that training occurred: the parent's isolated trusted reference producer and authenticated capture provide that provenance. No training labels, individual inner predictions or biological identity fields are serialized.

## What the engineering controls establish

One bounded RAM-only run passed8 control groups: hand-computed BNB probabilities; all100 seeded controls with a direct Bernoulli-product check on one column; logistic gradient finite differences and balanced/intercept behavior; extreme-logit unclipped NLL and all selection priorities; training scaler/constant columns; supplied-fold support/order refusals; fake-solver success/gradient boundaries; exact numeric state/prediction roundtrip and retained bytes. The test's toy expected folds are explicitly not asserted to equal sklearn seed623 assignments. No scipy/sklearn import, full nested solve or authentic numerical program was run. The installed NumPy2.4.6 test environment is not the declared NumPy2.2.6/SciPy1.15.3/sklearn1.6.1 reconstruction runtime.
