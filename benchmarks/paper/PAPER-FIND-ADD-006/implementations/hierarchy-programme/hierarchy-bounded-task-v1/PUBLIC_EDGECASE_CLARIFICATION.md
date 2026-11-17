# Common normalization-reason clarification

This addendum applies equally to conditions A and B. It clarifies the already specified computation without changing inputs, outputs, scores or runtime resources. The eight container input files remain unchanged; authors receive this additional declarative document before freezing their program.

Normalization reasons are selected from the **stored raw curve**, in this order:

1. An empty curve has `no_nonroot_curve` and a null denominator.
2. A nonempty curve with a nonfinite last entry has `nonfinite_last_nonroot_denominator` and a null denominator.
3. A nonempty curve whose last entry is exactly zero has `zero_last_nonroot_denominator` and numeric denominator zero.
4. Otherwise the positive finite last entry is the denominator. If normalization produces an infinite value, the reason is `nonfinite_normalized_curve`; otherwise normalization is defined.

Every undefined normalized curve consists entirely of nulls. This precedence is applied independently to Context, Direction and Position; position scaling does not override the stored-curve check.

In particular, a legal two-leaf tree has root height `H=1`. Its stored raw curve is `[0]` for every label because the root is excluded. Therefore its reason is `zero_last_nonroot_denominator`, including when the retained maximum position bin is zero. It does **not** have `no_nonroot_curve`. Empty stored curves cannot arise from a structurally valid submission here because each session must have at least two leaves.

For a taller tree with retained maximum position bin zero, the internal position variances are undefined. Its last retained position entry is consequently nonfinite, so `nonfinite_last_nonroot_denominator` applies. These are general input-independent edge cases, not observations about the empirical reference.
