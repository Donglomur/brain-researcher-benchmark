# PFC conditional-null kernel

A standard-library mathematical component for coincidence counts under independent label permutations with fixed margins. The kernel is unchanged from its reviewed source. The standalone tests use invented values only.

For one task stratum with `N` units, `a` units in an ROI and `b` units in a category, the coincidence count has mean `a*b/N` and variance `a*b*(N-a)*(N-b)/(N*N*(N-1))`. Independent task-stratum means and variances add. Empty strata contribute zero; singleton strata have zero variance.

`moments` returns exact `Fraction` values. The cohort helpers reconstruct counts and rational moments across twelve declared family axes, validate their shape, and remove one whole animal jointly across families. The schema names in the module describe a fixed-map interface; no authentic packet, animal roster, labels or expected biological answers are distributed here.

Run the twelve standalone controls from the repository root with Python 3.11 or later:

```sh
python -I -S -B components/pfc-conditional-null/test_conditional_kernel.py -v
```

The tests independently enumerate all distinct binary-label permutations for every margin at N=0 through 5. They also cover sums across strata, the incorrect shared-permutation null, negative covariance between fixed-margin cells, finite-draw population-variance bias, zero variance, invented recording support, joint animal deletion, exact rational discrepancies, label-invariant partition agreement and undefined deletion summaries. The adjacent workflow runs this command with a deadline and retains its test streams and exit status. No third-party Python dependency is needed.

## Method limits

- The conditional null fixes the map, labels, category assignments and task strata supplied by the caller. It does not fit a map or establish exchangeability, biological ground truth, causal effects or predictive performance.
- Fixed-margin cells and overlapping families are dependent. They are not independent replicates. The twelve-family/eight-category interface is specialized; this is not a general statistical package.
- Enrichment is undefined when conditional variance is zero, including a zero numerator. The kernel returns `None`; callers must preserve that state.
- Deletion summaries use fixed full-cohort axes and panels. Direction stability requires the full estimate and every deletion to be defined. These summaries are descriptive influence checks, not population confidence intervals.
- Exact counts, rational maximum errors and unequal-cell counts are distinct from the descriptive binary64 mean absolute error. Enrichment also uses binary64 arithmetic.
- Callers must validate complete case shapes before calling `moment_errors`, which traverses matching rows. Packet and submission validators are domain checks, not a complete untrusted-input or resource boundary. Hierarchy summaries expect finite supplied coefficients or `None`.
- Packet construction, provenance joins, source-label policy, file/CLI admission, geometry, clustering and hierarchy-correlation computation are outside these standalone controls. Archived finite-shuffle parity and full-paper reproduction are not established.

This component does not change benchmark registration, qualification, submission readiness or the status of any scientific result.
