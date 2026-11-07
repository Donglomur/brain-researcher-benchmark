# PAPER-ROOT-ADD-016 local summary scorer

**Local scoring adapter verified.** Nine saved-summary controls passed: exact reference, independently sampled inverse-affine alternative, a well-formed imperfect control, a stale wrong-scale control, and five malformed/wrong-identity cases rejected before private numerical decoding. All owned containers were absent. This verifies the local numerical scoring interface only.

This package scores arbitrary well-formed summaries of six specified Salzburg
processed-data posterior targets continuously. It does not execute candidate
code, verify source-model choices or summaries against candidate draws, or
complete the desired open paper-reproduction and improvement benchmark.

The pure scoring helper is a pinned immutable local dependency under
`authoring/cardiac-aperiodic-v1/summary-replay-v2/summary_score.py`. Runtime assets
are lazy local paths; this is not a self-contained portable distribution.
Scientific/research admission and full-candidate-contract completion remain
false, even after numerical adapter verification.

See `instructions.md`, the exact JSON schema and public/operator allowlists.
No posterior results, raw recordings, model weights or candidate-study claims
are copied into the public instructions.

The primary metrics were0.0,0.01728260947,0.5 and2.87698461018 for the four scored controls respectively. Smaller is better; none is a scientific pass label. The verification consumed its full45-second allocation (7.009332seconds rootterminal actual), bringing knowncardiaccharges to2,465seconds without resetting history. See the pinned verification receipt in the manifest.
