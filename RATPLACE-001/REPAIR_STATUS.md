# Validation gate

Real spikes and the optional positive control now share original timestamp-cell
alignment, and null shifts operate in elapsed time within BL epochs, not a
compressed running index. Corrected values must equal raw minus submitted null,
not pass an unbounded negative-value/prose escape. All old unit selection/raw/null
references are stale; the verifier requires a genuinely regenerated
`elapsed-time-running-v1` reference. Pending: raw/null source receipts and shuffle
bank recomputation, speed smoothing within contiguous epochs, input immutable
DANDI version/hash/offline staging and container oracle. Unit fixtures do not
validate neural information estimates or paper findings.
