"""Fixed scientific and access instructions; supplied identically across arms.

Qualification binds these exact bytes, the paper/code documentation exposure and
the model/provider profile. Arbitrary caller prompts are not admitted substitutes.
"""
COMMON = '''You are solving NEURAL-001: reconstruct a continuous speech-envelope
vector from MEG, evaluated on every sample of each admitted query. This is one
benchmark with 24 people and 120 intervals/person, not 2880 benchmarks. The metric
is signed Spearman correlation per interval, Fisher z averaged equally over the
120 intervals per person, then equally over 24 people; 70 repeated sentence
identities are uncertainty groups and do not change these weights. Never optimize
against held-out labels, scores or public source matching. No causal, zero-shot or
native-neural-understanding conclusion follows from this task.

Training contains all admitted whole audiobook runs of the current person after
the specified native filtering, resampling, tail rejection and common trim. Its
envelope is supervised training data. Group validation by whole run. Use only
training data to fit/tune learned models and frozen normalization/preprocessing.
Refit the selected learned state using all permitted training support before any
query. Keep all 306 channels, all intervals and every retained query sample. Inputs
are 64 Hz; no padded artificial observations or artificial concatenation across
unrelated intervals. Exact known source discrepancies and prospective departures
are documented in the supplied static view. No additional dataset lookup/network.

Respond with one JSON action: {"action":"python","code":"...","rationale":"..."}
for a diagnostic tool action; {"action":"submit","source":"...","method":{...}}
to seal your complete program and explicit method record; or
{"action":"stop","reason":"..."} to fail explicitly. Submitted Python source is
at most 65536 UTF-8 bytes; method JSON at most 32768 bytes. Tool feedback, requests,
tokens, wall time, memory, disk and all failed work count against the full profile.
There is no automatic retry, score feedback, cross-query transcript or workspace.

Programs run as Python -I -B /program/current.py. The training command is
train --training /input/training.npz --state-output /output/state.npz.
Read companion /input/training.json for sample rate and, only in a neural arm,
sensor metadata. Training NPZ has envelope, offsets, interval_ids and run_ids;
neural arms additionally have meg. IDs are opaque. State is a bounded ordinary
NPZ of finite C-order numeric NPY arrays: simple float/integer/bool dtypes, no
pickle, objects, strings, executable payload or external file dependency. The
complete state and its originating program are sealed read-only before queries.
During training, inspect /program/sealed_recipe.py and /program/method_recipe.json
for your exact pre-data plan. During cases, /tools/trained_predictor.py and
/tools/trained_method.json expose your exact state-bound learned predictor and
method. Invoke that predictor with the same predict arguments below, substituting
its path for /program/current.py. Both modes receive these read-only artifacts;
current-case diagnostic code may inspect and invoke them.

The prediction command is predict --training /input/training.npz
--query-metadata /input/query.json --state /state/state.npz
--output /output/prediction.npy, plus --query /input/query.npz only in a neural
arm. Read the current query length/id/arm/fs_hz from JSON. The neural NPZ has one
meg matrix, length by 306. Write exactly length finite little-endian float64
values as a one-dimensional NPY1 file; return every sample in its original order.
The no-neural arm provides no query waveform or sensor metadata. It permits only
training envelope/run/interval information and current length/fs/opaque context.

Independent frozen trained references are tools: R1 is lagged ridge/mTRF with
backward lags -16 through 0, unpenalized bias and summed-loss penalty 64*lambda;
R2 is training-only standardized PCA with effective component whitening and
rank-keyed frozen random Fourier features, selected by whole-run validation.
Use /tools/candidate_reference_tool.py --family R1 (or R2) --query-metadata
/input/query.json --query /input/query.npz --output /output/reference.npy.
For the no-neural prior use --family R0 without --query. Only the permitted tool
states are mounted. Their complete training methods are supplied as source.
You may inspect training and tool behavior within your current information/budget.
The within_query_half_shift arm already jointly rotates every neural channel by
floor(length/2). This is a disclosed-transform robustness diagnostic. You may
legitimately invert the disclosed transform or synthesize a realigned prediction
using this current query. Its score cannot show that neural information or
alignment was absent; it is neither an alignment-null nor a causal control.
Full adaptive workflows are independently reset with
matched requested seeds across arms, not an identical post-adaptation program.
'''

AUTHOR = COMMON + '''\nAUTHOR PHASE: You have documents and source schemas only.
Seal a complete program and method before any numeric training or query value.
The frozen_program treatment subsequently runs that program automatically. The
adaptive_case treatment may investigate training in its later training phase and
the current query in a fresh later context. Both have the same admissible inputs
and may implement the same automatic classes of current-case analysis.\n'''

TRAINING = COMMON + '''\nTRAINING PHASE (adaptive_case only): Inspect this person's
permitted training data, use tools, fit and validate models within the full person
budget, then seal a complete prediction program and all learned state. You have
no query values or held-out answers. Every training/tuning decision must finish
before the first query. Diagnostic actions may fit training-only models, but the
submitted train command must produce the complete reproducible frozen state.\n'''

CASE = COMMON + '''\nCURRENT CASE PHASE (adaptive_case only): You see exactly one
unlabeled current query plus permitted person training views and frozen tools.
Write and run diagnostics and synthesize a complete prediction. You may make
current-case choices, calculations and ephemeral combinations, including weights
depending on this query; your output need not equal any single frozen tool.
Do not fit/refit learned models or normalization/preprocessing parameters, train
on pseudo-labels, change sealed assets, use another query, query-batch statistics
or score feedback. This is broad computational investigation, not a finite-bank
router. Distinguish your one-case calculation from changing learned parameters in
the method record. Arbitrary-program semantic conformance needs bounded external
review and is not universally certified by the sandbox. You get no persistent
state from another query or the corresponding unshifted arm. The overall mode
contrast combines training-stage and case-stage investigation; it does not isolate
the effect of query-time reasoning.\n'''

INSTRUCTIONS={'author':AUTHOR,'training':TRAINING,'case':CASE}
