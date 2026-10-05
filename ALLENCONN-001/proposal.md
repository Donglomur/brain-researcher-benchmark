# ALLENCONN-001 — an atlas-derived self-maximum density descriptor

## Scientific role

This is a **secondary atlas method/easy control**, motivated by the anterograde
tracing resource in Oh et al. (2014), *A mesoscale connectome of the mouse brain*
([DOI](https://doi.org/10.1038/nature13186)). It is not a numerical reproduction
of the paper's Figure 3 projection matrix or Figure 4 fitted connectivity model.
The target is the fraction of eligible injected source structures whose own
structure belongs to the maximal-density target set under a declared recipe.

The current atlas subset, bilateral raw density, primary-injection grouping and
available-case averaging define a new descriptive analysis. Primary-site labels
do not unmix injections that spread across structures. Density is a segmented
pixel fraction within a target domain, not a synapse count, total projected axon
amount or direct estimate of connection strength between pure regional sources.

## Source and snapshot

The task uses original official Allen Brain Atlas RMA API responses: the
experiment metadata, full graph-1 structure metadata and projection-only
hemisphere-3 unionize records for exactly 498 non-transgenic-line experiments and
316 members of structure set 167587189. Source IDs are obtained from these
records, not inferred from the old answer bank.

The local snapshot is `allen-connectivity-20261001`. This is a capture identity,
**not an Allen immutable release**. The API is live; exact raw-file hashes,
queries, retrieval times and HTTP validators are retained. SHA256 hashes were
measured from retrieved bytes, not supplied by an independent official checksum
registry. Subsequent builds must match those pins or fail visibly; no silent
source refresh is allowed. An AllenSDK cache-manifest version is not a dataset
version. The source image contains no fitted matrix, argmax table or answer bank.

Acquisition retained 35 raw projection pages (87,995,553 bytes). The key audit found
157,326 unique records, 42 absent experiment/target pairs and no duplicated keys,
nonfinite numeric fields or observed zero-denominator rows. These are source
coverage facts, not computed benchmark answers. Absent records are not zeros.

Current [Allen terms](https://alleninstitute.org/legal/terms-of-use) allow research
or other noncommercial use subject to their conditions, including attribution;
commercial redistribution requires separate permission. No unrestricted CC
license, distribution clearance or image-publication permission is asserted.
Local validation does not resolve a later benchmark-distribution decision.

## Public estimator

Map each primary injection structure to the deepest member of the frozen target
set in its ordered ancestry path. Reject unmapped or malformed paths. All 498
current experiment mappings are unambiguous, yielding 157 sources; the old
iteration-order overwrite was fragile, not an observed error on this snapshot.

Keep the 316 targets exactly as deposited. This set is not a strictly disjoint
parcellation: MDRN/395 contains MDRNd/1098 and MDRNv/1107, all included. This is
disclosed; the descriptor is conditional on these target definitions.

For each source/target cell, average the published `projection_density` equally
over its observed, positive-domain experiments with `is_injection=False` and
`hemisphere_id=3`. Do not pool pixel numerators/denominators across experiments
or replace missing records with zero. Preserve the full Cartesian source receipt
and report observed versus expected experiment support for every matrix cell.

Missingness and eligibility were specified before computing the descriptor: a
source without an estimable mean for every target remains in outputs but is
excluded from the full-target argmax denominator. Available-case means are not
estimates of the missing values. Do not describe complete mean coverage as
complete underlying experiment coverage.

Report all maximizing targets under the public absolute 1e-12 tie tolerance, with
no relative tolerance. Self counts when among ties. A genuine all-zero complete
row therefore has every target tied and self=True under this convention; it does
not show preferential self-projection. Neither nonconstant rows nor mixed self
indicators are acceptance conditions.

## Removed invalid comparator

The prior injection-inclusive comparator averaged injection and non-injection
record densities as interchangeable rows, giving extra weight to experiments
having both records. This is not a physically pooled domain density. Such a
quantity would first require summed projected pixels divided by summed valid
pixels within each experiment/target. See the
[official field definitions](https://api.brain-map.org/doc/ProjectionStructureUnionize.html).
The optional comparator and causal 'injection artifact' recognition requirement
are removed. Old approximately 0.36/0.62 values and hidden bands are not targets.

## Validation and limits

Every submitted experiment/target record, missingness status, source mapping,
matrix value, support count and complete tie set is source-bound. All summaries
must recompute from those receipts. Row/column order and free prose are not
scientific failure criteria. Public metadata and numeric tolerances are supplied
to the participant; private fitted references do not define a secret estimator.

The reference must be regenerated only after the original source passes its
coverage checks. Independent keyed scalar aggregation and real-output mutation
controls distinguish source consistency from mere agreement with a fabricated
matrix. Unit fixtures alone do not validate the acquisition or paper finding.

Current execution status is in `REPAIR_STATUS.md` and the external clean-commit
receipt. A successful offline oracle is computational validation, not a paper
replication, unrestricted licensing approval or evidence that Sol cannot solve
the task. No model evaluation, push, PR comment or merge is part of this repair.
