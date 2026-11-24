# Historical DeepCaImX source and unresolved experiment mapping

Earlier source recovers an N=15 model with nine unrolled ISTA stages. It does not
recover the complete published experiment: the prototype has 1,000-frame input,
a separately referenced layer, and weight files absent from the inspected trees.
The current 400-frame N=8 demonstration is a different source generation. Preserve
both rather than silently replacing one with the other.

## A recovered prototype, not a qualified baseline

The [v1.0.0 source](https://github.com/KangningZhang/DeepCaImX/blob/91cb94248a8c42e2433ce58ccb19790775c02a00/Demo%20(full-version)/LSTM-ISTANet.ipynb)
contains the [literal historical code](author-code/legacy-v1.source.py.txt).
The 185,263-byte notebook was authenticated against its Git blob and SHA256;
only 26,819 source-code bytes are included here, under [LICENSE.author](LICENSE.author).
Notebook outputs, images and test-data files are excluded.
[HISTORICAL_SOURCE.json](HISTORICAL_SOURCE.json) binds the original, exported code,
cell identities, selected history and static findings. The existing
`notebook_sources.extract` function can reproduce this export from the external
original using the manifest's identity fields and the same literal extraction
recipe. No notebook cell or model was executed.

| Property | Historical v1 prototype | Current full demonstration | Original experimental claim |
| --- | --- | --- | --- |
| Neuronal channels | N=15; export line 46 | N=8 | Paper describes N=15 |
| ISTA structure | Nine explicit stages | Different released graph | Paper describes P=9 |
| Input window | 1,000 frames, lines47/248/260 | 400 frames |400-frame tiles from each 5,000-frame clip |
| Referenced weights | `LSTM_seg.h5`, `LSTM_ISTAnet.h5` | Authenticated 7,316,832-byte artifact | Historical weight equivalence unresolved |
| Native execution | Not attempted | Not qualified | Original complete ten-video replay absent |

The older code calls `CFF` at line 253 without defining it in that notebook.
Its temporal trace convolutions use same padding, unlike the later valid-padding
396-sample trace convention. Parsing this historical code as Python succeeds,
but parsing is not dependency, runtime, model or scientific qualification.
The two named historical weight files are absent from the complete April 2023,
February 2024 and July 2024 trees inspected in this inquiry; this is a scoped
absence, not proof that no weights exist elsewhere.

The old notebook was removed on 15 September 2024, before the current training
notebook, full checkpoint and testing notebook were added that day. The earlier
April and v1 code exports differ only in one test trace filename. These identities
establish source lineage; they do not establish the code used for the published
mean F1. No syntax, method, temporal window or supplied weight has been repaired
or substituted. The current training notebook's separately recorded syntax
failures remain unchanged.

## Testing the inherited annotation convention

The [April 2023 README](https://github.com/KangningZhang/DeepCaImX/blob/b958fa3043c560136b32c343e5aa69e5c093c53a/README.md)
and [February 2024 README](https://github.com/KangningZhang/DeepCaImX/blob/3dc96547e41915903b285adba0d28028357b9492/README.md)
credit STNeuroNet for 175/275-micrometre annotation sources. This supplied a concrete
lead for the four shallow recordings, not a transform for all ten videos.

At the pinned [STNeuroNet revision](https://github.com/soltanianzadeh/STNeuroNet/tree/6537096d8b2c05858320703418e2a3e2897be928),
none of the corresponding Allen, FinalGT or available Grader3/Grader4 MAT files
has the same Git blob identity as its DeepCaImX counterpart. Different container
bytes do not prove different decoded masks: no mask array was opened or compared.
The manifest retains all four-recording metadata comparisons.

The pinned [preparation source](https://github.com/soltanianzadeh/STNeuroNet/blob/6537096d8b2c05858320703418e2a3e2897be928/Software/prepareAllen.m)
rounds a 10-micrometre border using 0.78 micrometres/pixel. Its MATLAB inclusive
indexing would retain 487 pixels from an assumed 512-pixel dimension, not 488.
It selects an initial temporal fraction and its example caller sums groups of
five frames. Neither rule authenticates the DeepCaImX 18,501–23,500 frame interval.
This source predates the historical attribution. Importing these conventions
would therefore invent a new mapping, not resolve the original one. STNeuroNet
code is cited, not redistributed under the DeepCaImX MIT license.

## What remains required

Recover a provenance-preserving relationship between each original physical movie
and its 488×488×5,000 reference clip, plus the paper-method training/weights and
complete assembly recipe. Channel counts alone are insufficient. Matching record
IDs, historical annotation attribution and a plausible border are insufficient.
The current source evidence does not authenticate even the four shallow-video
mappings, and cannot be generalized to the other six recordings.

The original ten-video macro F1, strict IoU threshold, eight-donor dependence,
trace/runtime companions and access/exposure rules remain unchanged. This
crosswalk adds source evidence; it admits no paper reproduction, improvement,
new native execution, candidate score or SOTA claim. It supplies no executable
crop mapping and no new assembler. Maintained numerical producer/scorer code is
unchanged, so no duplicate numerical control campaign was run.
