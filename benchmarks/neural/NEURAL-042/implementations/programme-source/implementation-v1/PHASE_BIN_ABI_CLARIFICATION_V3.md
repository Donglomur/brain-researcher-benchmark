# Exact P phase-bin operation order (additive ABI V3)

The accepted source-derived prospective P uses this binary64 expression, with NumPy 2.2.6 primitive operations evaluated in the stated order:

`floor(((phase + pi) % (2 * pi)) / (2 * pi) * 18)`

The domain passed from the analytic phase is finite [-pi, pi]. First add binary64 pi; compute positive modulo by binary64 (2*pi); divide by that same binary64 denominator; multiply by integer18; then floor to an integer. Do not replace division with reciprocal multiplication, histogram-edge searches, or subtract/re-add wrapping. The resulting bin must be in0..17; an out-of-range result is an explicit numerical refusal rather than a hidden extra bin or clipping. The captured old Python expression has no clamp; this additional range admission makes the selected18-bin contract explicit. Exact negative/positive pi map to0 through modulo. Empty phase bins remain undefined MI. This selects the benchmark's explicit floating-point boundary convention based on the held Python estimator; it does not establish historical MATLAB or published-result boundary identity; it changes no scientific sample, surrogate count, band, matching or hierarchy.

Sole peer independently found boundary differences in tiny engineering controls. Both original reference source freezes and their results remain historical. R1 and R2 must independently implement this written rule and independently retain narrow boundary checks; they must not read each other's code or answers. This note does not qualify NumPy/library parity or actual scientific outputs. All previous receipts and costs remain.
