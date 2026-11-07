# Prospective forecast reference mathematics

This package will implement only the reference mathematics for `chronological_five_frame_processed_signal_v1`. Original native Figure2/3 reproduction and all transport, preparation authority, population, source exposure and grading belong to the parent. All values below are specifications, not observed neural results. No original numeric body or author function is executed in this source build.

## Fixed representation and support

Let R be the complete permitted development prefix of the fixed source population, N neurons by D frames. All arithmetic in this prospective reference profile is NumPy float64. This precision profile is not a claim of native PyTorch/float32 parity. For each neuron, mu=mean(R), sigma=sqrt(mean((R-mu)^2)), scale=0.001+sigma, and Z=(R-mu)/scale. Scale is strictly positive; every original admitted neuron remains, including constant development neurons. Query normalization must reuse these development parameters. This helper accepts only the admitted development matrix and never opens files or obtains query targets.

The parent exposes all development frames. Optional60/20 internal model-selection annotations are not an independently fitted preprocessing split if they use the prefix-wide mu/scale; no strict inner-CV claim follows. The fixed controls are untuned. The outer suffix remains inaccessible while fitting. Parent retains the original ephys full-session eligibility mask and calcium upstream preprocessing limits: training-only here refers to new parameters, not causal preprocessing of the entire released signal.

Production horizon is5; production DMD rank is min(1000,N), never dynamically reduced for numerical failure. Parent's complete original geometry gives T>=2000 and D=floor(0.8T)>=1600. The implementation nevertheless checks dimensional support explicitly. A mathematical projection kernel may accept a smaller rank solely for tiny invented engineering controls; the production fit API fixes the declared rank and does not expose a reduced-rank option.

## Source basis and observation-space forecast

Source identity: critical_init revision2c15edf4e770165fc3962dcc3920c8bcaf555bed, held source-evidence/lyapun.py3963B SHA2569e153bee36887e79adf2b5085774b9991a3e1f1d2dbb82456a0f3a485471b28d. In dmd, if N<D the source constructs C=ZZ^T/D, computes ascending eigenvectors of CC^T and, only when N>1000, retains the last1000 projected coordinates. If N>=D it constructs C=Z^TZ/D and eigenvectors of C^TC. The source computes that eigendecomposition even when N<=1000 but then keeps unprojected Z; omitting this unused calculation does not change the mathematical forecast.

For N<=1000 set encoder=decoder=identity and P=Z. No inverse singular value is used, so constant directions may remain as source full coordinates.

For N>1000,N<D, let U contain the last1000 eigenvectors of CC^T in their literal ascending-subset order. Set encoder=U^T, decoder=U, and P=U^TZ. Preserve this order rather than sorting projected variances again.

For N>1000,N>=D, let Q contain the last1000 eigenvectors of C^TC in the source order. Require D>=1000 and every s_j=||Zq_j|| to be finite and strictly positive. The source's literal projected training coordinates are P_source=diag(s)Q^T. Define U_j=Zq_j/s_j, encoder=U^T and decoder=U. Algebraically U^TZ=diag(s)Q^T because Z^TZq_j=s_j^2q_j. This is the explicit extension from the source's training coordinates to a new observation z_t. The helper checks the computed encoder·Z against literal P_source and checks U^TU against identity. It fits the source dynamical equation to literal P_source, preserving the source's training expression, after correspondence passes. It does not replace the source projection with an unrelated pseudoinverse or silently select fewer modes.

Exact repeated eigenvalues permit an orthonormal basis gauge. Forecast reconstruction is invariant under a consistent orthogonal change of basis when the same basis is used in encoder, decoder, A and scalar ridge. This algebra does not establish equality across numerical backends or failed correspondence checks. No cross-run gauge alignment is selected using query data.

A deterministic numerical admission tolerance for both relative Frobenius residual checks is tau=64*eps_float64*max(N,D). Require ||lhs-rhs||_F <= tau*max(||rhs||_F,1), with finite measured operands. This is a declared numerical consistency guard, not an empirical success tolerance, learned rank cutoff or scientific score. Selected zero/undefined norms in the dual inverse, nonfinite values, failed eigendecomposition/linear solve, or correspondence residual beyond this rule make the DMD reference unavailable. A zero-eigenvalue direction in a primal/full-coordinate basis requires no inverse singular value and remains as the original source defines it; no direction is dropped. Never omit a neuron/mode, alter ridge or continue with a weaker baseline under the complete-comparison label.

## Literal source block dynamics

The source dynamics_lag defaults are h=5, initial nt=10000, valid_inds=None. Let B=max(1,floor((D-h)/10000)) and L=min(10000,D-h). For each j=0..B-1, take X_j=P[:,jL:jL+L-h], Y_j=P[:,jL+h:jL+L], and source weight n0_j=L. If L<=50, no source block contributes and the reference is unavailable. Accumulate Sxx=sum_j (X_j X_j^T)/D *L and Sxy=sum_j (X_j Y_j^T)/D *L, total W=sum_j L; then Sxx*=D/W and Sxy*=D/W. Finally A=solve(Sxx+lambda I,Sxy)^T with lambda0.01 calcium and0.1 ephys.

The source weights use L rather than the actual L-h pair count. Its short-recording behavior is consequential: for D<10005, L=D-5 and the single block uses D-10 pairs, omitting the final5 target frames. For larger recordings it also omits block-boundary pairs and any tail after the last full selected block. These choices remain literal. They are not silently replaced by an all-pairs covariance or conventional least-squares normalization. All omissions and exact pair count are recorded in state metadata. Inputs outside those source-fitting pairs remain permitted development observations, while all parent-declared outer query pairs are predicted.

For each current standardized full vector z_t, source-family prediction is decoder A encoder z_t. Missing subspace is zero in standardized coordinates, equivalent to the development mean if mapped back to raw units. The helper returns standardized predictions only. It need not compute eig(A) because those eigenvalues are native reproduction outputs, not operands of this prospective forecast; native source behavior remains unchanged.

## Mandatory simple controls

Persistence is zhat_(t+5)=z_t and has no fitted coefficients beyond the common fixed normalization.

For diagonal affineAR, use all development pairs X=Z[:,:D-5],Y=Z[:,5:]. For each neuron compute pair means mx,my, centered sums Sxx=sum((X-mx)^2),Sxy=sum((X-mx)(Y-my)), ridge=1e-6*max(Sxx,1), slope=Sxy/(Sxx+ridge), intercept=my-slope*mx. Then predict slope*z_t+intercept. Constant X yields slope0 and the training-pair target mean, without dropping support. This prospective comparator is deliberately defined rather than called a published method.

All three reference predictions must be finite vectors of exactly N coordinates for every complete query stream. Failures remain explicit. Transport must seal each prediction before revealing the next current vector, and grading remains deferred until the parent admits every mandatory output and process closure. These functions cannot certify that runtime information boundary.

## API and controls

Planned functions: fit_normalization(raw_development)->mu/scale/Z; source_projection(Z,internal_rank)->encoder/decoder/P/metadata; source_dynamics(P,lambda)->A/blockmetadata; fit_reference(Z,modality)->DMD+AR states and support metadata; predict_reference(state,z_t)->exact DMD/persistence/AR vectors. No file I/O, original-data loader, source import, target callback or model execution occurs merely by importing this module. State serialization/custody and runtime resource qualification are parent-owned.

Tiny invented controls after parent approval will cover: normalization/no constant-channel deletion; source short/long block arithmetic and preserved omissions; primal and dual projection identity with original coordinate order; dual zero-direction refusal; original A orientation; positive/negative affineAR and constant input; all3 prediction shapes/finite guards; and hardcoded production rank. Tests exercise benchmark-authored math only, never import/execute lyapun.py. Small-rank kernels are engineering fixtures, not a reduced scientific panel. No authentic fit or scientific result is inferred.

Source grant12MBreads/1.5MBwrites; RAM-only fixtures256KiB retained/512KiB cumulative. Parent's combined ceilings and all prior costs remain separate. BLAS/LAPACK workspace, dense N^2/D^2 basis costs, performance, actual data support and native parity remain unqualified and must be admitted before future execution.

State numeric bytes are exactly8*(N*k+k*k+2*N), k=min(1000,N), plus bounded262144-byte metadata and separately counted NPZ headers/container. These are retained state components, not a fit-workspace or peak-RSS bound. State serialization exposes numeric float64 arrays and uint8 UTF8 metadata only. Parent must independently authenticate the trusted state archive and load allow_pickle=False under full member/header/expanded-size checks.
