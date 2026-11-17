# NEURAL-024 causal count interface: scientific sources

These new sources prepare a minimal count-only packet and privately score one
complete causal program attempt. The existing six-arm reference and its completed
results remain unchanged. This is source preparation, not a new scientific run
or a claim that the causal interface has already been qualified.

The data are the same exposed historical Indy recordings used by the reference:
96 corresponding M1 electrode labels, with all five released sort slots already
aggregated, including residual unsorted threshold crossings. This is neither a
new independent dataset nor proof that sorted neurons persist across days.

The preparer reads only counts and native clock edges from the exact three
qualified conversion files. It publishes source counts [18700,96] with 18701
clock edges and calibration counts [3000,96] with 3001 edges. Both public NPZs
contain exactly `counts` (uint32) and `bin_edges_seconds` (float64). Velocity and
endpoint arrays are stripped. An in-worker serialization round-trip checks
members, values, shape, dtype and contiguous layout before publication.

Public clocks retain their native absolute values. Request intervals are target
session-relative: subtract the first calibration clock edge, approximately745s.
No stored edges are rounded or resampled. Nominal20ms durations and60/60.2/502s
boundaries use the prior1e-7s physical tolerance; adjoining edges remain exactly
equal. The preparer emits one private clock-only schedule and one private
canonical JSONL observation stream, with no per-row files or future hashes
exposed to the candidate.

All22,100 rows from target bin3000 through25099 require a prediction of all96
positive finite means together. The first10 rows, bins3000..3009, are unscored
warm-up rounds. The remaining22,090 rows, bins3010..25099, match the exact
2,120,640-cell reference support. The trusted controller durably commits a
prediction before revealing its current observation. At sequence0 the request
contains no observation; later requests contain only the immediately preceding
row. The final stop message reveals the last row after its prediction commit.

Unlike the frozen six-arm reference condition, arbitrary candidate programs may
retain state and learn from all lawfully revealed history. They never receive
the full future NPZ, private observation stream, reference scores or grader
files. The host controller may forward already canonical observation bytes
without interpreting counts; it decodes only clock metadata. Numerical packet
decoding and scoring occur only inside trusted isolated workers.

Before reading any private file, the grader requires a stopped-producer
attestation, a complete protocol, and all22,100 canonical committed predictions.
It validates exact schemas, ordered identities, warm-up flags, unique nonces,
positive finite96-element means, monotone controller timestamps, the preceding
record hash chain and the complete submitted byte hash. Hashes include canonical
newlines. A zero-byte incomplete journal is an invalid submission with zero
private reads, not an infrastructure failure. Missing, malformed or incomplete
public predictions never produce a reduced-panel score.

After public admission, eight invented score controls run before private inputs
open. The grader joins the current private pins to the prepared receipt and the
original immutable reference. For each row it reconstructs the exact request
hash from the native schedule and the preceding observation, before decoding
that row's current counts. A mismatch at this point is an internal trusted
contract failure, with truthful private-read extent and a null score. It is not
misreported as a malformed candidate that used zero private reads. Grader
deadline or input-I/O failures likewise remain internal failures.

The scoring wrapper reuses the exact previously qualified full Poisson scorer
and independent scalar audit. It scores only rows10: of the complete stream,
retains all96 channels, and verifies reference support and per-channel observed
counts before comparing against all six fixed arms. Report full likelihood,
mean NLL, signed likelihood/NLL/bits-per-spike contrasts, and per-channel values.
The primary reference is the fixed calibration-rate arm. Negative gains remain
valid. Zero observed-spike denominators are explicitly undefined; finite extreme
means that cannot be aggregated numerically yield `numerical_failure`, without
clipping or a partial score. No new fit, tuning or scientific variant is added.

An independently authored first control program uses exactly calibration rows
10:3000 and the existing Gamma-rate formula `(sum+0.5)/(2990+0.5)`. It does not
read the source count file and does not update its rates from revealed query
counts. It still follows every warm-up, prediction, observation and stop step.
The grader reports `calibration_rate_control.exact_parity` and
`zero_primary_gain`, comparing all base support/count/likelihood/NLL fields and
every channel against the saved calibration-rate arm. This diagnostic is required
only for the explicitly selected calibration-rate control. Ordinary candidates
have no accuracy floor and may be substantially worse than every reference.

The preparer first runs eight invented packet/write-once controls and twelve
independently authored candidate controls, including a metadata-only walk of
all22,100 protocol steps. The grader has eight separate score controls. These
are authored but unexecuted at source closure. The parent controller's separate
transport controls are separately owned and counted. None of these controls is
an additional benchmark, dataset, model trial or biological replicate.

All outputs are bounded and published once, including rejection of an existing
final path before a temporary file can be opened. Preserve incomplete files and
attempt/read counters on failure. Exact aliases, commands, caps and dispositions
are in INTERFACE.json. Numerical phase proposals are30s preparation and30s
grading with25s computation windows; the parent proposal is780s whole,
600s candidate,1.75CPU/3GiB and176MB retained-file reserve. These are proposals,
not an allocation. The shared RTT ancestry remains2,020 charged seconds before
any new dispatch, with no reset of earlier failures.

A successful future calibration-rate run would establish a complete causal
program/grading control on this development endpoint. It would not establish
LLM success, SOTA, unseen-animal generalization, new task count or the registry's
broader multi-animal/multi-day contract. A transcript alone cannot prove causal
access: the parent must independently qualify the producer's mounts, durable
commit/reveal ordering, stopped state and immutable output provenance.
