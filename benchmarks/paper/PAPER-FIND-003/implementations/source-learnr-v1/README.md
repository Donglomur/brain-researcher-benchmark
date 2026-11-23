# Channel Learn-R construction

This component supplies a missing channel-level calculation for the selected
Figure 2C–E reproduction proposal. It does **not** establish reproduction of that
panel or an improvement over the paper. The task's ineligible improvement status
and four unavailable primary outcomes remain unchanged.

`learnr.py` uses Python's standard library. `analyze_rows(rows)` accepts a complete
list of rows with the original `channel,subject,trial,ACC,phase,ripple` fields.
It assigns raw row IDs before exclusions, applies the declared per-phase positive
99th-percentile filter, selects correct trials, and computes keyed channel/phase
Learn-R records. The percentile uses the type-5 convention already declared in
the retained processed-data contract. Its historical MATLAB numerical parity has
not been demonstrated by this construction.

The [pinned author helper](https://raw.githubusercontent.com/liulab-repository/ripple-representation-learning/f143b0b7dca77bf9b09d5c7f39352fc5332c83c0/ripple/computeLearnR.m)
requires at least ten observations and a positive-rate fraction of at least 0.1,
then applies a Spearman correlation and Fisher transform. These are calculation
eligibility rules, not a minimum patient count or scientific success criterion.
The [calling script](https://raw.githubusercontent.com/liulab-repository/ripple-representation-learning/f143b0b7dca77bf9b09d5c7f39352fc5332c83c0/ripple/Ripple_offline_learning.m)
selects correct trials after its phase filter. This differs from a fitted trial
slope and from the later subject/behavior association.

`learn_r_group(trials, ripple_rates)` exposes that calculation independently.
Ties use average ranks. Null represents a missing source value; it remains in the
eligibility denominator and yields an undefined correlation under the author's
default all-row policy. [MATLAB's correlation documentation](https://www.mathworks.com/help/stats/corr.html)
describes this default; silently deleting those rows would change the analysis.
Perfect correlations retain signed infinite-Fisher states with a null numeric
value. Constant, sparse, short and missing groups retain explicit states rather
than becoming zero-valued estimates. No NaN/Infinity JSON tokens are emitted.

Every input row is accounted for once: phase-filter exclusion, retained wrong
trial, or retained correct channel group. Channel labels associated with multiple
subjects and duplicate source cells are rejected. All three phases are required.
The one-million-row format limit refuses oversized inputs; it never truncates a
cohort. Finite binary64 numbers or null are accepted; infinities, booleans and
unknown phase/accuracy labels are refused. Python integer inputs must be exactly
representable as binary64: otherwise this API refuses them before grouping or
ranking, rather than silently introducing ties through conversion. Exactly
representable large integers and finite float inputs remain supported. This is
a local input-domain safeguard; it does not change the retained historical
model-artifact JSON schema's ordinary rounding policy. The input digest binds a
normalized JSON representation, not original CSV bytes or provenance.

## Deliberate boundary

Outputs stop **before** the author's phase-wise channel-outlier handling, subject
aggregation and behavioral join/regression. The source's mean-based outlier step
is distinct from the default median rule described in
[MATLAB's outlier documentation](https://www.mathworks.com/help/matlab/ref/rmoutliers.html).
No replacement aggregation or inference is supplied here. Missing first-session
provenance, authentic input identities, original trial-balancing controls,
published numerical references, justified comparison criteria and matched
information conditions remain unresolved. No authentic data, MATLAB execution,
scientific fit or AI run was performed.

The source observations in `SOURCE.json` came from browser-visible pinned code;
the upstream raw bodies were not locally captured or authenticated. Local pins
bind the existing task documents. This is a registered source component;
source enrollment does not qualify a scientific reproduction or a submission
route for the complete primary result.

## Generated checks

From this directory:

```sh
python3 -I -S -B -m unittest discover -s tests -p test_learnr.py
```

Seventeen generated controls cover analytic rank results, ties, eligibility
boundaries, missing/constant/perfect groups, original selection order, complete
row accounting, unsupported structure and lossless integer rank inputs. They do not verify historical MATLAB
execution or empirical reproduction. Shared CI runs this suite through
`PAPER-FIND-003.command-01` in `benchmarks/integrity/parallel-source-controls.v1.json`;
its expected count must accompany changes to the suite.
