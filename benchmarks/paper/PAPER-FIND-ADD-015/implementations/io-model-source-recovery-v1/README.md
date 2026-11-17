# Original IO-model comparison recovered

This source recovery identifies the original published model-comparison values
for `PAPER-FIND-ADD-015`. It does not run an estimator or replace the existing
processed-trace scorers. Reproducing the original finding and exceeding it are
separate outcomes; neither is newly qualified here.

The [official appendix](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11551350/supplementaryFiles)
was recovered from Europe PMC's supplementary-files ZIP. The PDF member is
`pnas.2318837121.sapp.pdf`, 2,718,644 bytes, SHA-256
`a5feee7d7ad15b88969768c045f3f03ea3ffcc8bc4ea5c8cf7b1382be83c3086`.
Only this report and sanitized source commitments belong in the repository;
the original source, rendered pages and acquisition receipts remain external.

## Published comparison

Figure S11, printed/PDF page 12, compares least-squares fits to the estimated IO
curve. Its plot labels report the following R² values. The values are transcribed
from a rendered page: text extraction recovers the caption but misses the plot
labels. These are rounded published values, not full-precision reference arrays.

| Function | Published R² | Fitted parameters stated in S11 |
| --- | ---: | ---: |
| Ricciardi | 0.999 | 3 |
| Threshold-linear (ReLU) | 0.994 | 2 |
| Power law | 0.974 | 2 |
| Logistic | 0.984 | 3 |
| Stretched exponential | 0.998 | 3 |

Figure S12, printed/PDF page 13, separately reports mean Ricciardi fit R² = 0.975
over bootstrap fits, with 1,000 repetitions and 364 samples. This bootstrap
summary is not the S11 Ricciardi value of 0.999. S12 displays distributions for
five Ricciardi parameters (`sigma_A`, `tau_rp`, `theta`, `tau_A`, `V_r`), while
S11 states three fitted parameters. The precise free/fixed parameter choices
must therefore be recovered for each branch rather than assumed identical.

## What this resolves, and what remains

The comparison family, rounded source values and S11 parameter counts are now
available. R² is an ordered goodness-of-fit quantity, with larger values
indicating better fit. The appendix does not provide an executable definition
of its denominator, weighting, evaluation grid, fit constraints, initialization
for every family, stopping rules, or full-precision scores. A conventional
formula must not be silently declared the exact source formula.

The [article Methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC11551350/), section
“IO Function Estimation,” describes the LOESS-derived IO estimate, least-squares
Ricciardi fitting and alternative functions. The original Fig2/4 notebook in
[Zenodo record 13851356](https://zenodo.org/records/13851356) contains 28 cells;
cells 21–22 compute rotated LOESS and pooled-cell bootstrap intervals, cell 25
integrates after shifting by the minimum, and cell 26 displays the normalized
integral. It ends with an empty cell 27. It contains no Ricciardi or alternative
function fitting implementation. Relabeling x-axis ticks as 0/1 in that notebook
does not normalize its x values.

The cached article XML's equation labeled logistic lacks a `1 +` term in its
denominator. Its exact MathML commitment is recorded in the external evidence.
No logistic equation has been silently repaired or used to generate a baseline.

The source comparison fits an empirical curve derived from the pooled original
364-cell panel; this recovery does not identify a held-out split or independent
IO truth. Recovering its complete source-fitting protocol is necessary for
faithful reproduction. For an improvement claim, the same observations, curve
support and complexity policy must be preserved, with a justified effect and
dependence-aware uncertainty. Merely adding flexibility to raise in-sample R²,
or matching the existing intermediate-reconstruction vectors, is insufficient.

## Integration proposal and qualification

Update the current improvement contract's statement that no S11 numerical
comparison has been recovered: its published R² labels and parameter counts
are recovered, while the native fit route and exact metric reduction remain
unresolved. Keep S11 and S12 separate. Retain separate reproduction and
improvement outcomes and paired paper+data versus paper+data+author-code access.
Do not promote existing processed Figure2/3 reconstruction to complete
Figure4/S11/S12 reproduction. No canonical task/contract was changed here.

Validation consisted of source hashing, bounded official retrieval, appendix
text extraction, and visual review of pages 12–13. No numerical data were
prepared, no fit or model ran, no historical solver target was opened, and no
new scientific score or software-test pass is claimed. The task-local
[structured findings](SOURCE_FINDINGS.json) bind the recovered values and
remaining limits for independent review.
