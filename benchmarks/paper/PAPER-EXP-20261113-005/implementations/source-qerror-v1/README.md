# Original SOM quantization-error component

`qerror.py` implements the original Extended Data Figure 2c,d reconstruction
endpoint: each unit's Euclidean distance to its nearest SOM prototype, followed
by region-wise median and 25th/75th percentiles. It compares candidate prototypes
with fixed source prototypes using the same features, population, normalization,
and grid shape. It does not learn a map or declare a paper win.

This is an arithmetic component with generated controls, **not a qualified
benchmark**. The original feature/map packet and published numerical panel have
not been prepared or authenticated for this implementation. The existing Full99
conditional-reconstruction input is a different endpoint and is not an input here.

## Interface

The operator must prepare and independently freeze a JSON packet before receiving
candidate output. Only the candidate's three-dimensional prototypes are supplied
by the participant. Run the source-population entrypoint as:

```sh
python3 -I -B qerror.py --packet /operator/original-packet.json \
  --packet-sha256 FROZEN_OPERATOR_SHA256 --candidate /participant/map.json
```

The CLI verifies the packet's SHA256 before parsing and prints a JSON score. The
hash must come from the operator's independently authenticated preparation; a hash
chosen by the participant establishes no source identity. This CLI is scoring
arithmetic, not a sandbox or participant delivery implementation. Source fixtures
use an explicitly smaller population only through the Python test interface.

The exact packet fields are shown in `test_qerror.py:fixture`; its values are
invented controls, not scientific input. In a real packet:

- `units` contains all 19,186 eligible source units and 99 recording probes, with
  stable unit, recording and explicitly joined animal IDs, anatomical `region`
  and `area`, and three original feature values.
- `feature_names` is the **author code order** `B_mean, M_mean, rate_mean`.
  Features are the author loader's output before standardization. This code does
  not log-transform firing rate or reconstruct epochs. The upstream transformation
  must be authenticated; taking another logarithm would change the endpoint.
- `reference_mean`, `reference_std` and unit feature weights are frozen from the
  original source map. Both source and candidate maps use these coordinates.
- `source_map` and the candidate map have exactly `topology`, `kshape` and
  `prototypes`. Topology is `hex`; prototypes are node-by-feature, transposed from
  the author's feature-by-node matrix. Node order follows the original grid.
  Candidate grid shape and actual prototype count must match the source map.
- `panel_counts` records **every** original region in each panel and its count.
  The scorer independently reconstructs the frozen author selectors and verifies
  exact agreement. It requires the paper's 10,413 PFC units in both original
  panels; a disagreement is a source-recovery failure, not permission to drop rows.

Output retains both panels, source and candidate quantiles, difference of medians,
and median of paired unit differences as separately named quantities. They are
not interchangeable. Recording and animal counts expose clustering; they do not
turn units into independent biological replicates. The all-unit mean is a labeled
diagnostic, never a replacement primary scalar. Units not assigned a source
parent remain in that diagnostic and their count is explicit.

## Qualification boundary

See [SOURCE_AUDIT.md](SOURCE_AUDIT.md) for source lines and two consequential
ambiguities: nominal versus realized node capacity, and the `PL` substring
selector. No original map replay, authentic numerical input processing, baseline
agreement, participant run, uncertainty estimate or performance improvement has
occurred. A dimensionally valid hexagonal grid does not establish neighborhood
preservation; method/protocol review and the source topology controls remain
necessary. The original task is in-sample reconstruction, not generalization.

Before admission, recover the complete unit/features/map lineage, resolve all
region-count discrepancies, reproduce the published source panel, freeze the
full-panel decision and meaningful effect, and specify mouse/probe dependence,
algorithmic replication and resource/access budgets. This component intentionally
returns `paper_win: null` and `qualification: arithmetic_component_only`.

`test_qerror.py` exercises hand-calculated Euclidean distances, fractional
percentiles, source normalization, both panels, paired-versus-unpaired summaries,
and refusals for additional prototypes, changed geometry, supplied rescaling,
missing groups, duplicate units and invalid anatomy/animal joins. Run it only
through the shared generated-test pool during coordinated construction.
