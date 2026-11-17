# Salzburg six-model posterior reconstruction

Reconstruct the prescribed posterior summaries for the original processed Salzburg CSV associated with Figure 4—figure supplement 4 of *Age-related changes in “cortical” 1/f dynamics are linked to cardiac activity* (eLife, DOI 10.7554/eLife.100605.3). This finite endpoint covers all 655 released analyzed Salzburg participants. It is not the main CamCAN cohort, raw ICA/spectral preprocessing, or a causal experiment on cardiac-component removal.

Use exactly the admitted 47,254-byte meg_slope_data_sbg.csv with SHA-256 6d122f256863197e49e9f7b39420cfe1c46741b3efa1fa66a6ec364337e48f11. Preserve every row and all three conditions: ECG_not_rejected, ECG_rejected and ECG_components. The processed input is exposed development data; there is no concealed participant split or held-out generalization claim in this reconstruction endpoint.

Fit a raw and a separately standardized model for each condition. For standardized models, transform age and the selected response independently with their full-column population means and population standard deviations (ddof=0). Do not transform raw posterior draws to obtain the standardized target: the source intercept prior changes.

Let x and y be current-scale age and response, with population moments m_x, m_y, s_x and s_y. Define b=2.5*s_y/s_x and a=sqrt((2.5*s_y)^2+(m_x*b)^2). The prescribed model is:

- alpha_c ~ Normal(m_y, a), where a is the standard deviation.
- beta ~ Normal(0, b), where b is the standard deviation.
- sigma ~ HalfStudentT(nu=4, scale=s_y).
- nu ~ Gamma(shape=2, rate=0.1).
- y_i ~ StudentT(nu, alpha_c + beta*(x_i-m_x), sigma).
- alpha = alpha_c - m_x*beta.

These are the audited Bambi 0.9.1 source-target priors reconstructed in a newer explicit runtime. They are declared conventions shared with the participant, not hidden requirements for unaided paper reasoning. The author source declares four chains, 2,000 tuning and 2,000 retained draws per chain and target acceptance 0.9; historical random seeds are not fixed. Different valid samplers, parameterizations and nonzero Monte Carlo differences are permitted. A fixed output comparison cannot verify actual fitting or sampler quality.

Submit one UTF-8 summary.json of at most 200,000 bytes using the exact adjacent schema. The six model keys are raw__ECG_not_rejected, raw__ECG_rejected, raw__ECG_components and their zscore__ counterparts. Each must contain alpha_c, beta, sigma, nu and alpha; report mean, population SD and shortest 94% HDI endpoints. A skew distribution's mean may lie outside its shortest HDI. Report unavailable optional batch-mean MCSE and diagnostics as explicit null. No extra keys, booleans as numbers, duplicate JSON keys, arrays, pickle, code or nonfinite values are accepted. input_sha256 must identify the exact CSV.

The primary metric is the equal-model root-mean-square discrepancy of the six beta means, each normalized by its private reference posterior SD. Smaller is better. Secondary diagnostics report parameter mean/SD/HDI differences and raw location-mean error at integer ages 18 through 73. There is no scientific pass threshold. Unsupported floating-point derived arithmetic receives an explicit unsupported status rather than clipping or an invented score.

MCSE and diagnostics are self-reported and do not affect the primary metric. The combined batch-MCSE ratio assumes independent stationary runs and does not calibrate HDI uncertainty. The standardized beta HDI rule uses the ROPE [-0.1,0.1]; an interval crossing a boundary is unresolved. Marginal raw/z posterior differences are not a joint biological contrast.

The six-model shared-specification condition and the separate paired OLS/HC3 companion answer different questions. OLS is not a substitute here. This endpoint does not establish improvement, protected prediction, a paper-only versus code-assisted effect, or complete paper reproduction.
