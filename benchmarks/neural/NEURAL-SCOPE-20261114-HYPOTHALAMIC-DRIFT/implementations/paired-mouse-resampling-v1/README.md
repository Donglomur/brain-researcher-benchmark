# Paired mouse-resampling diagnostic

This companion adds the missing mouse-level resampling operation to the existing
fixed-origin score report. It keeps the scored forecasts, reference selection and
source masks fixed. It does not run a model or establish a valid scientific trial.
The unchanged scorer remains the authority for the primary endpoint.

For each replicate, sample mice with replacement **within each of the five
biological groups**, retaining their declared sample sizes 6, 6, 6, 7 and 6.
Select candidate and reference losses together using the same sampled mouse
index. Recompute the candidate and reference group means and then their equally
weighted five-group means. The replicate effect is reference loss minus
candidate loss. Cells, sessions and states are never treated as independent
replicates; their existing hierarchical aggregation is retained inside each
mouse loss. Thus the 7-mouse MCH group does not outweigh a 6-mouse group.

The diagnostic reports the lower and upper empirical percentile order
statistics. At probability `p`, it takes sorted index `ceil(n*p)-1`, bounded to
the available endpoints. The seed, replicate count, interval mass, method,
required mouse-summary hash, pinned scorer identity and report identity are
recorded. The seed gives reproducibility for the same Python implementation;
cross-version PRNG identity is not asserted. Choose these settings before
inspecting the protected losses. Defaults are 10,000 replicates and 0.95 mass;
the numerical interface permits 100–100,000 replicates for bounded generated
controls and declared operator use. An interval is a resampling summary, not a
scientific pass threshold, p-value or automatic improvement decision.

## Missing mice and statistical scope

The scorer can define its primary score when some mice have no eligible targets,
provided every group retains eligible data. This diagnostic deliberately requires
all **31 declared mice** to have an eligible mouse loss. Otherwise it returns the
unchanged point estimate, an unavailable interval, the affected mouse IDs and
zero completed replicates. It neither drops those mice nor retries undefined
bootstrap replicates. This restriction concerns the diagnostic only: it does not
alter task support, scoring, target eligibility or the existing missingness rule.

These intervals describe reweighting sensitivity of the frozen observed mouse
losses. They do not account for source-event extraction, neuron matching, source
masks, fitting or comparator-selection uncertainty. In particular, the
leave-one-mouse-out models have overlapping training animals, so their loss
estimates are dependent. Nominal generalization coverage of this diagnostic is
**not established**. This distinction is motivated by the analysis of correlated
cross-validation errors in [Bates, Hastie and Tibshirani's primary
manuscript](https://tibshirani.su.domains/ftp/NCV.pdf). No particular theorem there
is claimed to validate this task's small, heterogeneous cohort or this procedure.
Learning-algorithm uncertainty requires a separately justified protocol that
propagates fitting and selection; this component does not implement one.

An interval above zero therefore does not establish a credible improvement claim
by itself. Authentic full-cohort event/mask production (including MCH thresholds),
the fixed-origin execution boundary, competent reference selection, contamination
and scientific review remain unresolved upstream requirements.

## Operator use

Use Python 3.11+ with the standard library, with the source report in the
operator environment. The exact scorer source is verified before importing it.
The report must come from that scorer over the intended qualified inputs. Its
trusted hash is checked before parsing, and the companion independently
recomputes the required numerical aggregation from all 31 mouse summaries.
It validates that projection, not every per-cell field or the production of
the report. A matching hash is identity evidence, not biological authentication
or proof that a protected execution happened.

```sh
python3 -I -S -B uncertainty.py \
  --score-report OPERATOR_SCORE.json \
  --score-report-sha256 TRUSTED_SCORE_SHA256 \
  --seed PREREGISTERED_INTEGER \
  --replicates 10000 --interval-mass 0.95 \
  --output NEW_PRIVATE_DIAGNOSTIC.json
```

The output is create-only and mode 0600. It is evaluator-private and must not be
returned to a participant for further adaptation. File permissions and hash
checks are not a process sandbox or access attestation. The pure `resample`
function performs no file reads, fitting or data acquisition after module load.
No raw fluorescence, direct neural-understanding interface or typed viewer is
added by this component.

## Maintained controls

`test_uncertainty.py` uses the existing scorer's generated 31-mouse/1,661-cell
fixture and then checks constant paired effects, preservation of pairing under
between-mouse variation, equal-group weighting, seeded/order invariance, missing
mouse and missing-group refusal, forged summaries/identities/counts/nonfinite
values, resource/configuration bounds, exact resampling support and the pinned
create-only CLI. These are numerical software controls, not biological or model
results. The existing scorer fixture is reused rather than replaced by a smaller
cohort. Run the new module through the existing bounded test pool locally; shared
CI enrollment is an integration step and is not implied by the presence of this
file.
