# Signed correlation arithmetic repair

The maintained `n071.metrics.part` scales each centered prediction and target
column before its correlation products. This preserves signed Pearson
correlation while avoiding overflow or underflow in the product of the two
variances. A nonfinite intermediate is rejected before the roundoff clamp;
constant predictions retain zero correlation and constant targets retain an
undefined correlation. Q², MSE, parcel weights, listener-first aggregation,
paired contrasts and the complete declared population are unchanged.

The previous metric source remains byte-for-byte in
`n071/history/pre-stable-pearson/metrics.py`. The package's
`PUBLIC_SOURCE_MANIFEST.json` remains the historical public snapshot; the
current closure is recorded in
`benchmarks/integrity/current-closures/trust-narratives/SOURCE_BINDINGS.json`.
A historical qualification or result does not transfer to the repaired source.
The new generated regression controls establish arithmetic behavior only; no
original arrays, fitted model or new scientific result are supplied.
