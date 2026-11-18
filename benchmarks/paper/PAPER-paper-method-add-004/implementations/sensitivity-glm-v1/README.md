# iSTTC sensitivity and Figure 7C model endpoints

This component extends the existing `PAPER-paper-method-add-004` task. It produces
the complete empirical sensitivity grid and fits the two balanced Figure 7C
Gaussian mixed models, with a separately declared mouse bootstrap. It adds no
benchmark ID. Authentic inputs, native numerical agreement, original paper
results and scientific qualification remain unestablished.

The [frozen prospective policy](POLICY.json) and
[source derivation](SOURCE_BINDING.json) distinguish source-supported choices from
explicit resolutions of conflicting paper/notebook instructions. Original task
definitions, historical manifests and the earlier empirical components remain
unchanged.

## Complete sensitivity production

The input population is the existing complete **5,775-unit, 26-mouse, eight-area**
cohort. Exact unit, session, mouse and area identities still require independent
source admission; the cardinalities do not authenticate them. A session cannot
belong to two mice. The input cohort and normalized spike JSONL format are those
documented by the [empirical producer](../empirical-estimation/README.md).

The producer attempts **103,950 fits**, preserving failed coordinates:

| Panel | Conditions | Methods | Coordinates per unit |
| --- | --- | --- | ---: |
| Recording duration | First 1, 5, 10, 20 and 30 minutes | Full ACF and full iSTTC | 10 |
| Trial count | 40, 60, 80 and 100 one-second trials from the same 30-minute recording | Trial-averaged Pearson R and concatenated-trial iSTTC | 8 |

Thirty-minute fits provide references; they are excluded from short-duration
summary rows. Every estimator uses the selected paper settings: 50 ms bins/lags,
25 ms iSTTC tolerance, 20 lag arguments and fitting from index 1. Full curves have
21 points and trial curves have 20. The unchanged author helper files must be
supplied in an exact pinned checkout; no author driver defaults are imported.

Trial starts use the source's uniform integer support, with replacement and
permitted overlap. Windows are half-open and reset to their own start. The two
methods share windows at each count. Counts have separate draws from the declared
sequential RNG stream; they are not nested. The frozen seed is `20261117004`.
This is a prospective realization, not recovered historical randomness. Freeze
the runtime, cohort order and window identities before outcomes; recording a
seed after choosing favorable windows does not establish that independence.

From the repository root, future independently admitted operations are:

```sh
ISTTC_ENDPOINTS="$(pwd -P)/benchmarks/paper/PAPER-paper-method-add-004/implementations/sensitivity-glm-v1"
python3.11 -I -S -B "$ISTTC_ENDPOINTS/endpoints.py" windows \
  --cohort /ABSOLUTE/COHORT.json --output-directory /ABSOLUTE/FRESH_WINDOWS

python3.11 -I -B "$ISTTC_ENDPOINTS/endpoints.py" produce \
  --cohort /ABSOLUTE/COHORT.json \
  --recordings-jsonl /ABSOLUTE/RECORDINGS.jsonl \
  --windows-jsonl /ABSOLUTE/FRESH_WINDOWS/windows.jsonl \
  --author-checkout /ABSOLUTE/PINNED_ISTTC_CHECKOUT \
  --output-directory /ABSOLUTE/FRESH_FITS

python3.11 -I -S -B "$ISTTC_ENDPOINTS/endpoints.py" sensitivity \
  --cohort /ABSOLUTE/COHORT.json \
  --estimates /ABSOLUTE/FRESH_FITS/estimates.json \
  --output-directory /ABSOLUTE/FRESH_SENSITIVITY

python3.11 -I -B "$ISTTC_ENDPOINTS/endpoints.py" figure7c \
  --cohort /ABSOLUTE/COHORT.json \
  --estimates /ABSOLUTE/FRESH_FITS/estimates.json \
  --output-directory /ABSOLUTE/FRESH_MODELS
```

Use an interpreter where the required dependencies are installed outside an
excluded user site when using `-I`. Production fits require the unchanged
producer's NumPy, SciPy, scikit-learn and statsmodels dependencies. Figure 7C
model arithmetic requires NumPy. The window and sensitivity-reduction commands
use only the standard library. These commands neither download nor install
anything, and this release does not run them on authentic recordings.
The low-level numerical core expects already admitted numeric arrays; NumPy
coercion is not a replacement for the public wrapper's strict cohort/fit validation.

## Conditional sensitivity and source conflicts

Every sensitivity report includes both frozen reference policies:

- **Primary `method_specific_full`:** short ACF and trial Pearson R use the
  30-minute ACF fit; short/trial iSTTC uses the 30-minute iSTTC fit. This follows
  the Methods pairing and the existing Figure 7C contract.
- **Required `all_full_isttc` diagnostic:** every short/trial estimate uses the
  30-minute iSTTC fit, reflecting the Results section's description.

Neither policy may be selected after viewing results or silently presented as
exact historical notebook replay. The source notebooks contain inconsistent
reference assignment, a copied 40-trial log-error column at 100 trials, and
inconsistent missingness. The package records these conflicts explicitly.

Each panel uses the same units under both policies: finite tau at all eight
short/count coordinates and both full-recording references. Negative or missing
R-squared does not select sensitivity support. All failures, reasons, original
condition denominators, and original/retained counts by mouse and area accompany
the conditional summaries. Reported historical counts 5,674 and 4,588 are
observations, never selection targets.

Pseudo-error is `100 * abs(short_tau - reference_tau) / reference_tau`. A
nonpositive reference remains in the denominator and makes affected summaries
unavailable; it is not dropped. Percentages use inclusive thresholds. Zero error
is valid for these raw summaries but has no finite logarithm. Full-recording fits
are pseudo references, not biological truth. Stability is conditional on common
fit success and these realized windows. It does not establish unconditional
robustness, true timescale accuracy, window-resampling uncertainty or improvement.

## Figure 7C source models and animal uncertainty

Despite the earlier generic “GLM” label, the pinned R scripts fit Gaussian linear
mixed models by REML:

```text
log10(tau_ms)           ~ method * (fr_s + alpha_s) + (1 | unit_id)
log10(pseudo_error_pct) ~ method * (fr_s + alpha_s) + (1 | unit_id)
```

`alpha_s` is the source R name for standardized local variation (Lv), not a
Hawkes excitation parameter. Covariates use the sample standard deviation of the
expanded long table, counting each unit four or two times as appropriate. The
primary method is the baseline. The unchanged Figure 7C common four-method
missing-fit/covariate mask is followed by the union of negative-R-squared
exclusions; zero R-squared remains. Any remaining nonpositive/undefined log
argument withholds the affected model without further favorable row deletion or
an epsilon. All original unit and retention records remain present.

The two complete method panels share the same three predictors. In this balanced
design, fixed effects equal multivariate least squares. REML variance components
follow the common and within-method residual eigenspaces, with `N_units - 3`
residual degrees of freedom. The constrained zero-unit-variance boundary uses the
pooled residual variance. The implementation preserves source treatment coding,
reports rank/degeneracy and refuses unrepresentable arithmetic. It is not a
general mixed-model solver. Independent algebra, analytic fixtures and a small
generated statsmodels comparison support this specialization; authentic native
R/lme4 parity, lmerTest p-values and profile intervals remain unqualified.
Exact zero residual variance retains the algebraic coefficients but marks the
endpoint `point_estimates_only`: no finite nonsingular Gaussian fit is claimed.

The prospective bootstrap draws whole biological mice, retaining all their
units and paired methods. It estimates uncertainty for the **neuron-weighted
regression coefficients**, not an equal-mouse effect. Original covariate scaling
stays fixed. The frozen configuration uses seed `20261117005`, 1,000 draws and
2.5/97.5 percentiles with linear/type-7 interpolation. Every sampled index and
failed draw is recorded. Any deficient/nonfinite draw suppresses all percentile
intervals; there are no replacement draws or silent omission. Inference is
conditional on admitted fits/windows/scaling, with no established coverage.
A separately labeled mouse-cluster CR1 covariance is diagnostic only; no
source p-values or joint Wald test are manufactured from it.

`figure7c` accepts either the existing complete four-method fit schema or the
new complete sensitivity table. The latter is fully validated before selecting
exactly the 30-minute and 40-trial coordinates; both original and projected input
identities are recorded. A transport-level digest is not native fit provenance.

## Software checks and remaining requirements

```sh
python3.11 -I -S -B -m unittest discover \
  -s benchmarks/paper/PAPER-paper-method-add-004/implementations/sensitivity-glm-v1 \
  -p test_protocol.py -v
python3.11 -B -m unittest discover -s tests/construction -p test_isttc_endpoints.py -v
```

These tests use generated complete populations, explicit backend transfer
controls and independent numerical expectations. They do not perform a scientific
campaign. Runtime commands require fresh output directories. Successful exit,
complete output and matching receipts where emitted are all necessary; directory
existence is not success. Sensitivity and model commands emit reports with input
identities, while window and production commands also emit receipt files.
Publication is not an atomic transaction or durability guarantee.
Document hashes canonicalize JSON without a trailing newline; the window receipt
instead hashes the exact raw JSONL bytes. Cohort/source reads are capped at
16 MiB, fit/report outputs at 64 MiB, spike records at 64 MiB and window records at
32 KiB. These are logical byte limits, not hard memory, CPU or wall-time limits.
The pinned native fitter retains its potentially expensive fit budget; an
external execution owner must qualify resources and lifecycle handling.

Outstanding requirements include original object/cohort/covariate identities,
historic window/table provenance, independently competent references, native
numerical agreement and protected candidate evaluation. Pinned author source
shows initial amplitude cutoff0.1 followed by an eight-area filter using
amplitude_cutoff <0.01, isi_violations <0.5 and presence_ratio >0.9. Paper inclusive
versus source strict boundaries, saved presence minimum0.95, historical AllenSDK
filtering and actual cohort/panel identities remain unresolved. The
[QC source clarification](../../docs/provenance/empirical-qc-source-resolution.v1.json) supersedes the unexplained amplitude contrast in
the frozen `POLICY.json /unimplemented_or_unqualified/1` for current interpretation.
The policy bytes and execution bindings stay unchanged. This is a hosted source
observation; the admitted local notebook capture failed. Source Figure 7D/F fitted model
curves, pooled-area Figure 7B fits with 50 repetitions, area contrasts and the
whole paper are not implemented by these per-unit summaries. A future constrained
improvement benchmark must independently freeze support and withhold full-recording
references from the estimator; this reproduction interface supplies neither.

See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md). Publication, data and dependency
rights remain separate.
