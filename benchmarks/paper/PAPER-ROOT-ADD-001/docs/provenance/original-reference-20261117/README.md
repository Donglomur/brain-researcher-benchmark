# Original language reference verification

The complete provided-author reference for **PAPER-ROOT-ADD-001** was measured on
17 November 2026. All **224 original result files**, spanning **14 sessions and
eight people**, were authenticated and reduced using the frozen original
Figure 3b–e procedures. This supplies a measured comparator for future attempts.
It is not a new model run, independent AI reproduction, or improvement result.

**24 November follow-up:** A [fresh trusted reference replay](../trusted-figure3b-reference-20261124/README.md) completed all 42 selected contextual population Figure 3b cells and 5,685 original Ridge fits on the historical numerical stack. Its mean and all cells agree with this provided reference to floating-point precision. This qualifies that selected operator replay; full 224-array training reproduction, participant NativeProvider qualification and AI improvement remain separate. The 17 November measurements and their historical scope below are unchanged.

[REFERENCE.json](REFERENCE.json) is the complete saved report, unchanged from the
single execution. [RECEIPT.json](RECEIPT.json) records source identities, costs,
scope, evidence hashes and remaining limitations. Original source:
[Cai, Cash and Williams, Zenodo 20128462](https://zenodo.org/records/20128462),
associated with [Mapping the neuronal building blocks of human language with
language models](https://www.nature.com/articles/s41586-026-10691-5).
The release is recorded as CC BY 4.0; attribution does not imply endorsement.

## Measured reference

The primary source reduction fixes contextual layer index **5** and lag indices
**17–19**. It averages the three lag values within each session, then weights all
14 sessions equally. The other model distributions retain their original source
selection. No favorable layer, time or participant subset was substituted.

| Original Figure 3b condition | Mean correlation | Descriptive session SEM |
| --- | ---: | ---: |
| Contextual population | 0.0451207116 | 0.0139383765 |
| Contextual time shuffle | 0.0003946136 | 0.0056439459 |
| Syntactic (`syn`) | 0.0124135742 | 0.0142784603 |
| Syntactic shuffle | -0.0109280614 | 0.0105378552 |
| Word2vec | 0.0131128487 | 0.0271493844 |
| Word2vec shuffle | -0.0185692852 | 0.0083412941 |
| Semantic/syntactic (`sem_syn`) | 0.0152342826 | 0.0118838608 |
| Semantic/syntactic shuffle | -0.0230809761 | 0.0086472194 |

Every condition has all 14 session values defined. These SEMs are descriptive
values computed with `ddof=0`; the Figure 3b notebook does not calculate its
reported SEM. Rounded paper numbers are not a binary reproduction tolerance.

All nine original directed permutation contrasts completed with 100,000 draws
each. Their complete counts, seed resets, one-sided probabilities and observed
differences are retained. The original test pools **42 session-by-lag entries
per arm**; those are not 42 independent people. Its unpaired pooling and lack of
multiplicity correction remain explicit. A smaller p-value is never an
improvement endpoint.

The original Figure 3c context analysis retained all 33 layers for each context
length, its separate group-level layer selection, all five means and SEMs, and
the source exponential fit `a * exp(b*x) + c`. The fit completed once with
parameters `[-0.0446559888, -0.1940021662, 0.0630282840]`, finite covariance and
all 100 source grid points, with no warnings or solver retuning. Figure 3d
retains both 33-layer controls. Figure 3e retains every cell of all three 40×33
maps, their normalization and the unit support counts.
The D1 maps have 548–567 defined units per cell; 528 of 1,320 cells have fewer
than the nominal 567 units. The original `nanmean` support is preserved, with no
all-undefined map cells or repaired source values.

## Source coverage and cost

Input preparation authenticated **196 original members**: 168 numeric inputs,
14 word-timing files and 14 population-weight files. The native Figure 3e
counts are `[35, 40, 22, 26, 38, 55, 66, 45, 37, 19, 25, 22, 82, 67]`, totaling
**579**. The separate D1/continuous firing-rate representation has **567** unit
columns. Matching the selectivity population total does not establish the
missing unit identity mapping for the associated Figure 3f analysis.

The three new source archives totaled 1,000,979,246 body bytes, acquired once in
1,051.58 seconds. Independent full hashes passed. Input preparation took 3.82
seconds with 889,913,344 bytes peak RSS. The complete reference reduction took
**5.91 seconds**, with **110,133,248 bytes peak RSS** and 24,856,518 logical source
read bytes. The single saved report is 485,111 bytes. No neural model was trained,
no candidate or API was run, and no original `.npy` member files were extracted
or copied. The JSON report retains the declared source values and reductions.

Execution used Python 3.11.6, NumPy 2.4.6 and SciPy 1.17.1. The author metadata
names Python 3.11.3, NumPy 1.24.3 and SciPy 1.10.1. This operation verifies the
declared current-runtime reference; exact historical numerical and training
provenance remain unestablished. A separate reviewer inspected the saved full
report and source bindings without repeating its computation.

## Remaining work

Future reproduction attempts must generate the original complete output family
from the admitted inputs. Improvement attempts must compare prediction scores
on the same scientific task. This receipt supplies the author reference; it
does not establish a candidate result, an acceptance margin, protected execution
or evaluation custody, or full benchmark qualification. The original author
results are exposed reference material. The separate Figure 3f identity issue
remains recorded outside this task's adopted mandatory primary scope.

The frozen implementation is in
[`original-inference-v1`](../../../implementations/original-inference-v1/README.md),
source commit `e5d5bc61c7025a231919b049a4f27df2c3bdfd09`. This evidence addition
does not modify that implementation or its 23 generated controls.
