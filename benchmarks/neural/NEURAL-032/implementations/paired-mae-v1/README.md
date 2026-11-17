# Paired retrospective MAE component

This implements NEURAL-032's **secondary** baseline-versus-neural held-mouse MAE
audit on the retained source-defined followup-volume / baseline-volume ratio.
It computes actual paired losses, original eligibility and complete whole-mouse
fold plans. It does not implement or replace the primary conditional-estimand
grader. Current task/understanding definitions and historical declarations remain
unchanged. Integration must explicitly adopt this partial route before exposing
it as a registered participant interface.

The source-only recovery located the legacy public `NEURAL032-adjusted-v1`
protocol, primitive export construction and eligibility arithmetic. That earlier
protocol scores MSE and uses pointwise regularized-slope bootstrap intervals. The
current contract requires MAE, explicit undefined terms and multiplicity controls.
Recovering the earlier estimator therefore does not qualify the current primary
endpoint. Source identities are recorded in [SOURCE_PROVENANCE.json](SOURCE_PROVENANCE.json).
No authentic observation table, private answers or reference values were read for
this implementation; no new data were downloaded.

## Exact support and scoring

The CLI requires the historical complete export, exactly 477396 bytes with SHA-256
`4f095339e7b60f647f0d977d3713e72e373a2e397ce579fa451ba04ed23164a6`.
It requires all 1143 original rows, 27 members and 20 declared mice. Each row ID
preserves original member/row identity. Source validation rejects duplicate IDs,
gaps within a member, inconsistent member identities and malformed types.
The table itself stays outside Git and is not supplied by this component.

Baseline eligibility requires admissible flags, finite positive volume and no
Absent, Eliminated or Shaft flag; baseline New remains eligible. Followup must
have admissible flags with none of New, Absent, Eliminated or Shaft, finite
positive volume, and a representable strictly positive ratio. Unknown flag
vocabulary remains excluded/unavailable under the original rule; invalid tagged
flag structure is rejected. Missing or unrepresentable outcomes are counted and
never zero-filled. Every source mouse must retain an observed outcome. Counts and
each row's disposition are returned, including mouse-by-compartment support.

Both compartments of a mouse are held out together. Each paired prediction file
must contain all whole-mouse folds and exactly both predictions for every eligible
row. Within mouse, MAE is the mean absolute error over those same rows. The report
returns both absolute errors and their signed baseline-minus-neural difference
for every mouse, then averages each metric equally across mice. Units are
dimensionless volume ratio. Negative gains, zero gains and constant or negative
predictions are valid; no biological-success threshold or best-model selection
is imposed. Numeric output cannot certify fitting chronology or covariate use.

## Operator interface

Requires Python 3.10+ and only the standard library. Run from this directory with
operator-owned external input/output paths:

```sh
python3 -I -B paired_mae.py plan --observations /external/observations.json --output /external/folds.json
python3 -I -B paired_mae.py score --observations /external/observations.json --submission /external/predictions.json --output /external/mae.json
```

Output files must be new. The CLI authenticates the source before parsing or
scoring; there is no alternate cohort flag. The pure Python functions support
generated software controls and do not themselves authenticate a source export.
The plan includes row IDs and support dispositions, with no numerical outcomes.
This is an exposed-outcome investigation: withholding outcomes from this plan
does not make the published table a protected test.

The submission is at most 262144 bytes, uses strict JSON and has exactly these
fields (the schematic one-fold fragment below must be expanded to all 20 mice):

```json
{
  "schema_version": 1,
  "task_id": "NEURAL-032",
  "protocol": "NEURAL032-paired-retrospective-mae-v1",
  "input_sha256": "4f095339e7b60f647f0d977d3713e72e373a2e397ce579fa451ba04ed23164a6",
  "folds": [{
    "heldout_mouse": "JW082",
    "training_mice": ["all other 19 mice in sorted order"],
    "predictions": [{"row_id": "m00r0000", "baseline": 1.0, "neural": 1.0}]
  }]
}
```

Fold and prediction order may vary; joins use exact identities. `training_mice`
must match the plan. This is a check on the declared fold composition, not proof
that a submitted program actually used it. The scorer never runs submitted code.

## Qualification and remaining work

Generated tests check hand-calculated unequal-mouse MAE, distinguish MAE from MSE,
both compartments in one fold, source exclusions, missing outcomes, row identity,
paired completeness, invalid values, zero/negative gains and exact-export refusal.
They do not establish native runtime or authentic-data qualification.

Still missing: authenticated recovery and operator validation of the source
export; verified FOV/dendrite identity and measurement quality needed for nested
and matched analyses; frozen fitting and permitted-feature enforcement; the
complete conditional estimator and numerical-report grader; deletion stability,
matching and valid multiplicity-adjusted intervals; participant transport and
an independent authentic control. The recovered export's flat member/row IDs
cannot alone supply the missing FOV/dendrite covariates. No direct/viewer/tool
understanding, protected prediction, causal effect or scientific result is claimed.

Data provenance: Wright et al., *Distinct synaptic plasticity rules operate across
dendritic compartments in vivo during learning*, [Science DOI](https://doi.org/10.1126/science.ads4706),
selected processed release [Zenodo 15047046](https://doi.org/10.5281/zenodo.15047046).
The recovered protocol is a benchmark-defined investigation, not the published
estimator; release equivalence to article-cited 14549129 is not established.
