# Complete sentence pairing for NEURAL-066 scoring

This successor repairs a concrete private-identity defect in the two existing
CER passes. Matching person IDs and both folds is insufficient when an opaque
sentence ID can map to different source sentences in different arms. A generated
counterexample swaps two private source assignments in one TIMING context,
leaves its public view and probabilities unchanged, and is accepted by both
predecessor passes. Its person's TIMING CER changes from 0 to 2/3.

Both successor entrypoints reject that counterexample before scoring. They
independently require the exact original 1,794 context roster, all 78 target
cases, a nonempty complete bijection between query IDs and each case's source
sentences, and identical ordered private mappings across all 23 contexts in
each case. Every source sentence must occur in exactly one held-person/fold
query case. This source-identity restriction does not assert that participants
in different modalities are biologically independent.

The two support checks share only the existing immutable roster constants and
identity encoding. They do not share validation or numerical scoring callables.
The predecessor probability admission, raw/LM0.5 decoding, Levenshtein distance,
sentence-within-person averaging, modality separation, descriptive uncertainty,
90 metric groups, 164 signed contrasts and output schemas are unchanged. The
repair does not substitute a smaller panel or a different target.

`protected_score.py` and `independent_score.py` retain the existing callable
interfaces. `core.py` is a byte-identical dependency snapshot from the retained
package. Select the two successor scorer modules together in an operator source
composition; existing `typing-s3-public-v1` files and their source manifests
remain intact. The canonical controller still selects its original package.
Integrating the successor into that controller requires an updated source
inventory and authority pins; this directory does not silently replace them.

The generated control command is:

```sh
python3 -I -B test_paired_score.py
```

During the parallel construction wave, run that command through the shared
test pool. The test imports only standard-library code and the local scoring
modules. Its full generated roster exercises both actual scoring entrypoints,
the predecessor counterexample, omitted/duplicate/remapped sentences, target
case completeness, cross-fold source reuse, malformed context membership and
invalid probabilities. Unequal sentence counts across folds distinguish the
registered person-macro sentence CER from equal-fold or key-micro averaging.
All targets and predictions in the control are generated in memory.

This is a scorer repair and generated software validation, not authentic data
preparation, a model result or a qualified benchmark. The target vault still
belongs after the existing protected barrier. These checks cannot authenticate
an incorrect mapping repeated consistently in every context; source preparation,
alias resolution, trigger alignment and operator provenance remain necessary.
Full source assets, actual MEG EOG geometry, all original qualification gates,
reference competence and restrictive participant execution remain unresolved.
Programme scores remain distinct from direct or viewer interpretation.

Provenance: predecessor source under
`../neural-066/typing-s3-public-v1/source`, with the repository's MIT license.
The source dataset remains [SpanishBCBL V1](https://huggingface.co/datasets/bcbl190626/SpanishBCBL/tree/88f9096c6ce3a3fb17cc7b8e3131ff7f96da5684)
at revision `88f9096c6ce3a3fb17cc7b8e3131ff7f96da5684`; the official
[Brain2Qwerty loader](https://github.com/facebookresearch/brain2qwerty/blob/5f9889621d0df391c5aab37c996683d308e6e926/studies/spanishbcbl.py)
remains pinned at `5f9889621d0df391c5aab37c996683d308e6e926`.
No external source body, native data, participant answers, fitted model or
private operator membership is bundled here.
