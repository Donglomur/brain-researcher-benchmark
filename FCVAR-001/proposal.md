# FCVAR-001 — shared-phase connectivity variability method control

## Scientific target

For an explicit, fixed 30-person subset of the released Nilearn ADHD demo,
measure rectangular-window Fisher-z connectivity variability and compare it
with 50 declared shared-phase surrogates at each of three window lengths.
The independent descriptive averaging unit is the participant. This is a
finite-record method/sensitivity exercise, not a clinical ADHD comparison,
population generalization, neural-state discovery, or replication of Allen's
named figures. Difficulty is uncalibrated; retain it as a method/easy control
unless a separate model evaluation supports a stronger claim.

Prichard and Theiler's [Eq. 5](https://arxiv.org/pdf/comp-gas/9405002) motivates
the shared-phase multivariate construction. Allen's
[connectivity-variability/state analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC3920766/)
motivates the question, but used 405 participants, ICA networks, different
windowing, regularization and clustering. Its surrogate controls are not this
ROI-BOLD-before-windowing implementation.
[Hutchison's review](https://pmc.ncbi.nlm.nih.gov/articles/PMC3807588/) explains
why fluctuating window estimates alone do not identify changing underlying
interactions. The task asks for no predetermined direction or significance.

## Source and method

Preserve the original task's explicit 30 seven-digit IDs, not the current
loader's different first30 membership. Original BOLD/confound files and all
three released metadata tables remain unmodified. Use the 48-region
Harvard–Oxford cortical maxprob25%2mm atlas. Public file identities are pinned
to recorded archive/member captures; measured NITRC digests are not presented
as publisher-issued immutable releases. The exact official Nilearn notices
have commit/Git-blob identity. Public access does not establish commercial
permission; separate source restrictions remain in `SOURCE_NOTICE.md`.

The public method fixes geometry, all frames, per-person header clocks,
ordered confounds, float64 cleaning, windowing, RNG trace, support conditions,
inclusive ranks and group completeness. Empty support and numerical
degeneracy are explicitly represented, never concealed by dropping people,
windows, edges or surrogate slots. Nuisance realizations are observed in the
source; the estimator contract is not hidden.

## Verification

The verifier authenticates source bytes and reconstructs ROI extraction and
cleaning independently of the oracle. Both routes intentionally use the same
public deterministic statistic kernel for exact rank arithmetic; they are
not claimed to be independent inference algorithms. Accepted source-close
cleaned series alone drive all downstream statistics. Raw and phase receipts
are evidence, not rounded inputs to a second estimator. Full keyed coverage,
source-relative fidelity and all 4,500 null statistics are checked.

The historical bank, broad expected-effect bands, cross-person correlation
acceptance, outcome-direction requirements and prose gates are removed.
Scoring is binary, with no promise of proportional partial credit. Authoring
mutation/equivalence checks are kept separate from production scoring, so a
valid submission need not retain hidden tolerance or artifact-size headroom.

## Delivery evidence

The authoring status and external repair receipt record actual validations.
Do not infer in-container oracle success, model failure, scientific replication
or task difficulty merely from code changes or this proposal. No Sol run,
push, merge or public source/image release is part of the repair itself.
