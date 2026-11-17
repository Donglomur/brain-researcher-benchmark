# Exact reference algebra and work reuse

This is a derivation for a proposed implementation, not an executed numerical test. The source paper uses default LDA for pairwise concept/image decoding. The new references use fixed **regularized binary LDA** for27 overlapping labels, with different splits and features. They are different scientific methods.

## Fixed assumptions

For one outer case/window/arm, let X be the full n×d permitted training matrix after training-only imputation and centering/scaling. Every label has both classes; no row or label is dropped. All27 labels use the same n rows. Let Xc = X−mean(X), G = XcᵀXc, and let label ℓ have n₀ and n₁ rows, class means μ₀ and μ₁, and δ = μ₁−μ₀.

The covariance is the unbiased pooled within-class covariance:

S_w,ℓ = [G − (n₀ n₁/n) δδᵀ] / (n−2).

The chosen reference covariance is S_ℓ = S_w,ℓ + λ I. R1 uses λ=0.1 in standardized raw-feature coordinates. R2 gives each training-standardized PC variance1/8 and uses λ=0.0125. These constants are fixed before all benchmark training, independent of labels, counts, arm dimension or observed covariance. The purpose is a declared regularized model, not a claim of optimal shrinkage.

Every label uses equal class priors, π₀=π₁=0.5, appropriate to the task's balanced prediction target under the Gaussian class-conditional model. Different source prevalences are reported separately. No adaptive shrinkage, learned calibration, label-dependent ridge, class-dependent covariance or empirical-Bayes estimator is silently substituted.

## One common factorization and27 label corrections

Define A = G/(n−2) + λI and κ_ℓ = n₀n₁/[n(n−2)]. Then S_ℓ = A−κ_ℓ δδᵀ. A is common to all27 labels for this arm.

Solve A v_ℓ = δ_ℓ for all27 right-hand sides with the same factorization. The Sherman–Morrison identity gives

w_ℓ = S_ℓ⁻¹δ_ℓ = v_ℓ / [1−κ_ℓ δ_ℓᵀv_ℓ].

The discriminant intercept is b_ℓ = −(μ₁+μ₀)ᵀw_ℓ/2, because log(π₁/π₀)=0. At query x, return q_ℓ = sigmoid(xᵀw_ℓ+b_ℓ) using a stable implementation.

This is exactly equivalent in real arithmetic to solving27 different pooled-covariance LDA systems directly. It is not a claim that all27 pooled covariance matrices are identical. A common factorization is valid because their label-dependent part is the specified rank-one term and λ is fixed. Their right-hand sides and corrections remain label-specific.

With both classes present and λ>0, S_ℓ is positive definite in exact arithmetic, and the denominator is positive. A native implementation must check finiteness, symmetry, positive definiteness, residuals, conditioning and denominator stability; it may not hide a nonpositive or numerically unstable denominator with clipping. Independently formed direct label-specific covariance solves are the required parity reference. If a qualified native implementation cannot establish stable equivalence for an actual case, use admitted direct per-label solves, retain the disposition/cost, and do not silently omit that case. If neither route qualifies, the full result is incomplete.

Direct solves are the **numerical fallback**, not another independently selected scientific model. Their covariance, λ, priors, training rows and means must be identical. This fallback expands computation to at most27 independent covariance factorizations per required arm view; it does not authorize an unbudgeted retry. The future resource plan must explicitly admit either common-factor execution plus fallback allowance or a fail-closed outcome.

## Arm-block reuse

R1 and R2 define each family's transformations without reference to other families, use all the same training rows, and use the same λ across that reference's arms. Hence each arm's A is a principal submatrix of JOINT's A, and each arm's class means are the corresponding subvectors. This property is not true for R0's fixed-total PCA recipe.

For each window, order JOINT as [neural, ocular, visual]. Its Cholesky factor's leading principal block factors NEURAL's A. Separately order NUISANCE as [ocular, visual]; its leading block factors OCULAR's A. Factor VISUAL once per outer case, because its underlying inputs and model are independent of window. Permuting columns is declared and inverted in query transformations.

This gives240×(5 JOINT +5 NUISANCE +1 VISUAL)=2,640 common factorizations per LDA family, versus5,040 arm-wise common factorizations when prefix reuse is unavailable. Every arm still has its own27 right-hand sides, rank-one corrections and predictions. Floating-point parity of the factor prefixes, means, transformations, residuals and outputs must be verified; this is not a measured speedup.

## Input identity reuse

All five VISUAL windows are the same feature/label input for a fixed outer case. The fixed references are pure functions of those inputs and their fixed configuration; the reference information policy does not use window labels. Thus6,000 logical case/window/arm outputs require5,040 distinct reference feature/training views:

240 × [1 VISUAL +5(OCULAR +NUISANCE +NEURAL +JOINT)].

The candidate API permits deliberate window branching. Therefore this trusted-reference equality does **not** permit reuse of arbitrary candidate P/I outputs across windows.

Different held test sessions do not generally share training data here: the inherited split removes that session ordinal in each of the other three training participants. Different held concepts or participants likewise change training membership. All240 outer memberships remain distinct. Potential equality of image-only training multisets across people depends on authentic image/session assignments, multiplicity, canonical order, labels and information policy; none has been established, and none is counted as a saving.

Per-family preparation requires240×(1 visual +5 ocular +5 neural)=2,640 family transformations. This can serve the fixed R0/R1/R2 recipes with separately bound outputs. R0 and R2 single-family PCA eigenspaces are mathematically related by constant scaling, but rank thresholds, ordering, signs and native SVD behavior must qualify before sharing them. No fixed-total joint PCA is reconstructed approximately from truncated family PCs.

## Counts and fallback bounds

For all mandatory fixed references, retaining all logical outputs:

- R0:136,080 binary logistic optimizations after only proven VISUAL-window reuse. Logistic Hessians vary by label; no common linear solve is claimed.
- R1/R2:5,280 factorizations with qualified arm-prefix reuse, or10,080 arm-wise common factorizations without it;272,160 label-specific right-hand sides/corrections in either case.
- If every common-factor LDA solve needs the admitted direct-label fallback: at most272,160 direct label covariance factorizations. This is a numerical fallback upper bound, not the default selected schedule and not an invisible retry allowance.
- PCA:5,040–7,680 decompositions, depending on qualified single-family sharing.
- Canonical reference hyperparameter-search fits:0.
- Optional nonlinear controls, stronger visual features and tuning studies:0 selected operations; each needs its own full-scope prospective contract and resources.

Counts are algebraic schedule bounds. They do not establish time, dollars, peak memory, physical I/O, environmental parity or affordability. Source-feature extraction is about1.98GB of float32 numerical payload, but one naive complete family-training pass visits each experimental row in132 eligible outer training memberships and reads about265.15GB of logical feature payload. Caching and repeated solver passes change real I/O. This distinction prevents confusing on-disk dataset size with the actual computation burden.
