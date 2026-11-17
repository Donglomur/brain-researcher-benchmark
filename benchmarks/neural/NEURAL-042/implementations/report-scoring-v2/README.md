# Complete report reconstruction comparison

`comparison.py` extends the existing prospective PAC report scorer with errors
for all four candidate group means, confidence-interval endpoints and sign-flip
p-values. The predecessor validates group support, mean consistency and numeric
ranges but `program.grade.compare` does not compare candidate group statistics
with the reference. Thus an admissible report can have a zero primary MAE while
inventing a confidence interval or p-value. The generated counterexample is
retained in `tests/test_comparison.py` and runs the actual predecessor comparison.

The original primary scalar is preserved: average corrected-MI absolute error
equally over reference-supported people for each nuisance-matched contrast,
then average the two endpoint means equally. A support mismatch invalidates the
affected endpoint; either unsupported primary endpoint leaves the scalar null.
All eleven metric errors retain their individual units. Group errors are
secondary and do not redefine the primary or reward a particular biological
sign. `full_numerical_agreement` applies the frozen patient tolerances
(absolute 1e-10 plus relative 1e-6) and group absolute tolerance 1e-10.

When fewer than two people support a group, group errors remain null and matching
null summaries agree. This is report agreement, not evidence of an estimable
population effect. A support mismatch suppresses group errors even when both
reports happen to contain the same number of supported people. Both complete
144-row/four-group reports are validated before comparison, so the pure API
cannot silently accept truncated or reordered inputs through `zip`.

## Operator integration boundary

This is a source-only successor component. It imports the frozen `contracts.py`
and `core.py` from `../programme-source/implementation-v1/program`; the owner
must include that directory on its controlled import path. A future source
freeze may replace `program.grade`'s calculation functions with imports of
`compare` and `reference_agreement` from this component. All existing protected
producer admission, independent R1/R2 execution, target-last custody, resource
limits, scientific qualification and output-size checks must remain. The
registered runtime and its existing source manifests have not been modified.
The added diagnostic fields require a new owner source/output freeze before
production use. No CLI is provided that could bypass that lifecycle.

The supplied tests construct synthetic report dictionaries only. They do not
produce PAC signals, execute R1/R2 on recordings, run a model, qualify source
support, or demonstrate scientific performance. No authentic/private targets
were read to build this component.

Scientific semantics remain those of the local `MATHEMATICS.md` and canonical
understanding contract: prospective measurement reconstruction, not the source
paper's z-scored PAC estimator or direct neural interpretation. Source context:
[SBCAT author analysis at a25e8cc](https://github.com/rutishauserlab/SBCAT-release-NWB/tree/a25e8cc3f61630a428f190381745257d4506f148),
[DANDI 000673 version 0.240118.2135](https://dandiarchive.org/dandiset/000673/0.240118.2135),
and [Daume et al.](https://doi.org/10.1038/s41586-024-07309-z).
