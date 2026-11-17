# Paired held-mouse response comparison v2

This component implements the missing primary comparison in the current
NEURAL-044 contract: nuisance-only MSE minus candidate MSE within each held
mouse, averaged with equal weight across eligible mice. The original registered
runtime, task, contract and historical definition remain unchanged. The two new
modules live beside the preserved `alm` modules so their relative imports reuse
the original packet, publication, capture, source preparation and investigation
implementations without copying them.

`alm.response_comparison_v2.prepare_response_comparison` accepts the original
perturbation construction and the complete source mouse roster. It retains
lagged rows with independently pretest-classified sites and the original minimum
of three eligible mice. Response-selected pairs and mice with no joined pairs
remain explicit dispositions. No target, power, condition or follower sampling
is added.

The preparation fits both fixed references on other mice: the original
unweighted training-only StandardScaler followed by SVD ridge with alpha=1,
intercept and pair weights 1/n for each training mouse. The nuisance reference
uses the original six features; the secondary tuning reference adds similarity
and its site-class interaction. The public packet now includes opaque,
case-specific training-mouse groups so the same weighting is reproducible
without publishing biological identities. Reference predictions, held responses
and the complete mouse roster remain operator-owned.

`score_response_comparison` requires every estimable case exactly once and checks
case/response identity, within-mouse units, finite vectors, source/disposition
digests and the prepared public-packet digest. It reports paired per-mouse MSEs,
the equal-mouse primary mean and a descriptive approximate mouse t interval.
Unsupported mice retain null scores and their reasons. Neither pair counts nor
frames become biological replicates. The interval does not propagate dependence
from overlapping training folds or uncertainty in model-estimated labels.

`alm.operator_response_v2.ResponseComparisonOperator` publishes the prepared
packets and protected cohort record and binds the new score to the existing
target-last evaluation path. Its `prepare_perturbation` adds a private
`comparison_path` argument after `truth_path`; the other parameters follow the
original operator. All submissions from both arms, including the separate
investigation report, are captured before any protected scoring read. Pinned
private records are reauthenticated. Numerical investigation reproduction stays
a separate result and never establishes predictive gain or causality.

The source lineage is the versioned DANDI release
[001612/0.250927.1801](https://dandiarchive.org/dandiset/001612/0.250927.1801),
the [pinned author repository](https://github.com/arsenyf/Finkelstein_et_al_Nature_2025/tree/19fe755ce3b7e2b6d3c6c5f4afccda2829af303d),
and the preserved benchmark-defined prospective estimator. This is not a
reproduction of the missing author DataJoint pipeline. No new source acquisition
or authentic numerical preparation was performed for this component.

The task-local generated test script exercises a closed-form constant-design
reference with unequal mouse sizes, variable-design agreement with the preserved
recipe, held-label perturbation invariance, zero/negative candidate controls,
unsupported mice, rejected identity/vector/binding errors and the actual
publication/capture/scoring sequence. Generated tests are run through the shared
two-slot pool, with one numerical thread and a 1 GiB/180-second ceiling. They are
software controls, not scientific reference or agent results.

Qualification remains incomplete. The authentic full release census, mapping,
source units/clock/cell linkage, native estimator execution, protected participant
host, and separate investigation observation delivery remain missing. Public
cases must be delivered in isolated per-case views: another held-mouse case's
training labels can contain the current case's targets. This component does not
implement that host or change public run/score admission. Integration into the
canonical catalog and shared CI is a separate reviewed action.
