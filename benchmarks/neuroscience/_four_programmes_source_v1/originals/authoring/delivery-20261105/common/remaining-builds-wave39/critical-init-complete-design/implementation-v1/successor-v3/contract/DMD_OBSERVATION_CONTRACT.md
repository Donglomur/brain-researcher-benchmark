# DMD observation and interpretation contract

Three different objects must remain separate: the ideal full-state propagator, the estimator fitted to observed/preprocessed recordings, and a descriptive statistic of the sampled fitted spectrum. This contract applies to F3c-f, ED7c-d, every ED8 panel and prospective dynamics claims.

For a stationary linear process x(t+delta)=F x(t)+eta(t), F=exp(M delta), define Sigma=Cov(x(t)). Assume zero means, innovations uncorrelated with x(t), exact linear observations y(t)=H x(t), no measurement noise, and nonsingular observed covariance. The population unregularized least-squares predictor is

B_obs = H F Sigma H^T [H Sigma H^T]^(-1).

Population ridge under that covariance normalization is

B_obs,ridge = H F Sigma H^T [H Sigma H^T + lambda I]^(-1).

The numerator orientation is Cov(y_next,y_now). Ridge lambda must be stated in the same normalization as the cross-products. These are analytic statements, not numerical results from this phase.

If H is square and invertible and lambda=0, B_obs=H F H^(-1), so it is a similarity transform with the same spectrum. An orthogonal full change of coordinates is a special case. With truncated PCA, orthonormal rows alone do not imply this identity. A sufficient closure condition is H F = F_r H for a retained dynamics F_r; then noiseless unregularized observed prediction equals F_r, with its retained eigenvalues. Equivalently, one can establish a suitable reducing/invariant subspace together with absence of omitted-state drive into the retained coordinates. Arbitrary covariance PCs need not satisfy this dynamics closure. Do not assume an unverified invariant subspace merely because a basis is orthonormal.

In the actual held implementation, lyapun.dmd reduces to up to1000 components depending on its shape branch. It fits a finite-sample ridge regression using dynamics_lag's block slicing, endpoint filtering, tail omissions and weighted cross-products. Its actual operator is (G_xx+lambda I)^(-1)G_xy transposed, with G_xx/G_xy defined by that exact source, not by an assumed conventional covariance normalization. Source-specific z-scoring, nonlinear calcium deconvolution, spike binning, filtering, selected time support and observation loss are part of the estimator contract. They do not establish that recorded units are a complete linear observation of a brainwide state. Measurement noise can produce errors-in-variables bias; temporal filters and subsampling change the lag predictor; regularization and finite samples change the spectrum.

An analytic counterexample establishes the limit without a fixture or simulation: for an isotropic stationary2D damped rotation and scalar observation of its first coordinate, the population predictor is the real scalar exp(-gamma delta)cos(omega delta). A real observed coefficient is therefore compatible with rotating hidden dynamics. This does not assert that such a model generated the recordings; it disproves the general inference from a real projected spectrum to no hidden rotation.

For an ideal continuous eigenvalue -gamma+i omega, the sampled propagator eigenvalue is z=exp[(-gamma+i omega)delta]. Its principal argument is omega delta modulo2pi. The retained source statistic

r_principal = arg(z)/(2pi) * log(0.1)/log(abs(z))

is a principal-branch sampled-mode cycles-per-tenfold-attenuation statistic for stable nonzero |z|<1. The source's imag>=0 selection and modulus/real-part cutoffs remain explicit variants. Zero, unit, unstable or nonfinite magnitudes receive defined dispositions, not artificial clipping. Unaliased interpretation requires an external bound such as |omega|<pi/delta (with boundary conventions) or separately justified multi-lag identification. Neither is established merely by a fitted DMD plot. Aliased oscillation can have principal phase nearzero even with full observation; finite projection can suppress it further.

Reproduction scores compare the submitted observed DMD artifacts against the independently reproduced SAME preprocessing, support, dimension-reduction, ridge, weighting and phase/filter contract. An ideal analytic-control score may compare exp(Mdelta) only with a fully stated observation/closure/noise/regularization limit. A discrepancy between observed DMD and known full F is a diagnostic of estimator/observation effects, not automatically a candidate failure.

Prospective comparisons must match observation maps, filtering, missing units, sample duration, ridge selection and lag. Report both hidden-generator truth, when available in protected simulations, and observable-estimator targets. A biological symmetry claim, synaptic connectivity claim, or claim of absence of all continuous rotations remains unsupported by real-data DMD alone. The scientific-reasoning rubric rewards identifying this distinction and testing discriminating observable predictions; it must not reward repeating the paper's overbroad PCA-spectrum assertion.

