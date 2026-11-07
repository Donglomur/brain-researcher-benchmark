# Salzburg cardiac/aperiodic posterior reconstruction control

This local numerical task uses the original 655-person processed IRASA-slope
CSV for the Salzburg supplement of *Age-related changes in “cortical” 1/f
dynamics are linked to cardiac activity*. It covers six specified models, not
the main CamCAN analyses, raw preprocessing, the full paper, or causal effects
of removing cardiac components. The primary open paper-reproduction/code-access
study remains separate and unqualified.

Read the exact original CSV named in `public_assets.json`. Preserve all rows and
the three response conditions `ECG_not_rejected`, `ECG_rejected`, and
`ECG_components`. Each has a raw model and a separate `zscore` model. For the
standardized model, transform age and the selected response separately using
their full-column population means and population SDs (`ddof=0`). Do not derive
the standardized target by transforming raw-fit posterior draws: the source
intercept prior differs when age is standardized.

For each model, with current-scale age (x), response (y), and population
moments (m_x,m_y,s_x,s_y), use:

\[
b=2.5s_y/s_x,\quad a=\sqrt{(2.5s_y)^2+(m_xb)^2},
\]
\[
\alpha_c\sim N(m_y,a),\quad\beta\sim N(0,b),\quad
\sigma\sim\operatorname{HalfStudentT}(\nu=4,\mathrm{scale}=s_y),\quad
\nu\sim\operatorname{Gamma}(\mathrm{shape}=2,\mathrm{rate}=0.1),
\]
\[
y_i\sim\operatorname{StudentT}(\nu,\alpha_c+\beta(x_i-m_x),\sigma),
\qquad\alpha=\alpha_c-m_x\beta.
\]

These are the audited Bambi 0.9.1 source-target priors reconstructed in a newer
explicit runtime. They are a shared-spec diagnostic, not hidden requirements
for the paper-only scientific reasoning task. The source did not pin historical
random seeds. Different seeds, samplers, parameterizations and valid nonzero
Monte Carlo differences are permitted.

Submit one UTF-8 `summary.json` no larger than 200,000 bytes. Use the exact
schema in `submission_schema.json`: six model keys, five parameters
(`alpha_c`, `beta`, `sigma`, `nu`, `alpha`), posterior mean, population SD and
shortest 94% HDI endpoints. The mean may lie outside the shortest HDI for a skew
distribution. Optional batch-mean MCSE and diagnostic values must be explicit
`null` if unavailable. No pickle, code, arrays or extra JSON keys are accepted
by this summary interface. Use the original CSV SHA256 in `input_sha256`.

The primary metric is the equal-model root-mean-square beta-mean discrepancy,
normalized by each private reference posterior SD; lower is better. Secondary
metrics report each parameter's mean/SD/HDI differences and raw location-mean
error over ages 18–73. All scores are continuous: there is no scientific pass
floor, and a well-formed summary is not proof of a correct model or inference.
Finite summaries beyond supported derived floating-point arithmetic receive an
explicit unsupported status, not clipping or a fabricated score.

Reported MCSE does not affect the primary metric. The supplementary combined
batch-MCSE ratio assumes independent stationary runs; it is not a calibrated
test or HDI-error bound. Claimed diagnostics and data use are not independently
verified by this summary-only adapter. The standardized beta HDI/ROPE rule uses
[-0.1, 0.1]; an interval overlapping its boundary is unresolved, even if most
posterior mass lies inside.

Run, once the package has passed its recorded verification:

```sh
python3 tools/neurobench.py score PAPER-ROOT-ADD-016 --submission /absolute/summary.json --output /absolute/fresh-output
```

The scorer uses a fresh offline, nonroot Docker container with two CPUs and
four GiB. It parses no candidate program and has no model or LLM calls. Supply
a finished regular single-link file; this scorer does not attest producer
stoppage or candidate execution history. Reference values and operator source
parents must never be mounted into a future candidate context.
