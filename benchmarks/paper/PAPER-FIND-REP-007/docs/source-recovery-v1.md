# Immutable author-release source recovery

The complete pinned author-code tree has now been recovered. It contains no
additional retinotopy fitting or scoring module omitted from the earlier review.
This closes the earlier repository-listing gap; it does not supply a reconstruction
score, comparator, or original retinotopy input panel.

Reproduction of the paper's biological findings remains a first-class benchmark
outcome. The absence of an evaluated computational-method comparison does not make
that reproduction task ineligible. Reproduction and improvement must have separate
outcomes within this registration, with the same original observations in the
paper-plus-data and paper-plus-data-plus-author-code conditions. Neither condition
was executed in this review.

## Newly recovered evidence

The [recursive GitHub tree](https://api.github.com/repos/MouseLand/zhong-et-al-2025/git/trees/ba64ac697f5d9914926baac79399e80707a5f3a6?recursive=1)
at revision `ba64ac697f5d9914926baac79399e80707a5f3a6` returned successfully with
`truncated: false`. Its 2,932-byte JSON response has SHA-256
`cdbdcea6d948f60f1797eb0bb26fc10eb075f5b37b50c1d120c4512679aec9e1`.
The complete release has twelve blobs:

| Files | Role in the released source |
| --- | --- |
| `utils.py` | Processing and analysis utilities, including loading completed retinotopy transforms |
| `data_process_script.ipynb` | Produces intermediate neural and behavioral analyses |
| `fig1.py` through `fig5.py`, `S6.py` | Figure-specific loading and plotting |
| `Figures.ipynb` | Invokes the six released figure modules |
| `README.md`, `LICENSE`, `.gitignore` | Documentation, license and repository exclusions |

There is no `S1.py`, separate retinotopy training module, submodule, or additional
directory in this immutable tree. Ten cached complete blobs were checked against
both their source-reported lengths and Git blob identities. The full
`Figures.ipynb` payload was not reacquired: its earlier verified complete-blob
receipt matches the newly recovered tree, and the previously retained source cells
were inspected. Those cells import and call `fig1`–`fig5` and `S6`. `.gitignore`
was listed but not fetched or interpreted as scientific code.

## What the available code and paper support

In [the pinned utility](https://github.com/MouseLand/zhong-et-al-2025/blob/ba64ac697f5d9914926baac79399e80707a5f3a6/utils.py#L330),
`load_retino` loads a mouse/date `_trans.npz` file and returns supplied `xy_t` and
`iarea` values plus area indices. The processing notebook consumes these transforms
for area-specific biological analyses. This is evidence of downstream transform
use, not a replayable implementation of the reference-mouse encoding fit.

The [paper's Retinotopy Methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC12367527/)
describe the reference fit with 200 kernels of 13 × 13, positive per-neuron
amplitudes, about 5,000 natural images downsampled from 120 × 480 to 30 × 120,
correlation-based assignments, alternating kernel updates and recentering. Mapping
other mice uses at least 500 images repeated three times and smooths correlation
maps across the nearest 50 neurons before spatial alignment. Extended Data 1b
illustrates the filters; 1c illustrates aligned maps. These statements identify a
procedure but do not establish an evaluated reconstruction statistic, its
aggregation, a numeric comparator, or a meaningful method comparison.

The previously cached full-article XML used for this review has SHA-256
`9b22ae08e55ed129c7ca391aed14c331c4735308ef00042aa8d78df51063e337`
and was originally acquired from the
[Europe PMC full-text endpoint](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12367527/fullTextXML).
No new article or array acquisition was needed.

## Consequences for the two paper outcomes

**Reproduce:** retain the existing biological-outcome implementation and its source
ambiguities. It provides useful source-derived calculations but still lacks a
qualified replay on the complete original animal/session and cell populations,
native preprocessing parity, paired participant delivery and independently
verified source-result scoring. The sequence paper/code discrepancy remains
material. This source recovery does not promote historical generated controls to
an authentic reproduction or participant result.

**Exceed:** the retinotopy route remains scientifically unresolved. A newly authored
loss, an added held-out partition, additional kernels, a smaller neuron population
or a larger biological contrast would not establish superiority on an original
evaluated paper endpoint. The complete code-tree finding narrows the remaining
gap: the pinned release supplies no additional fitting/scoring entry point to
recover. It does not prove that no unpublished or separately released code exists.
No new scorer or numerical baseline was invented.

The canonical task, improvement contract, historical specification and initial
evaluator are unchanged. Integration should represent reproduction and improvement
separately under the updated four-outcome policy, without duplicating this task's
registration or claiming readiness from source presence.

## Work performed and qualification

This was static source inspection and integrity checking. The only new network
response was the 2,932-byte immutable tree; the completed acquisition reservation
was `paper01-pretraining-source01`, owner `paper_01`. All Python source parsing ran
through the reviewed shared pool. No author code was executed, no data array was
read, no installation or native numerical preparation occurred, and no model,
participant or scientific comparison ran. There are no new generated evaluator
tests because no executable benchmark component changed.

Qualification: **source-recovery evidence only**. Reproduction is not yet
empirically qualified; original-task improvement and current SOTA are not claimed.
