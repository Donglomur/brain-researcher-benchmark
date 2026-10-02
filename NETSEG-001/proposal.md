# NETSEG-001: a source-bound system-segregation method control

Apply the system-segregation method of [Chan et al. (2014)](https://doi.org/10.1073/pnas.1415122111)
to a fixed public movie-fMRI derivative subset and the Schaefer 100-parcel,
7-network atlas. This is a **new descriptive method adaptation**, not a
reproduction of Chan's adult-lifespan finding or a named Richardson finding.
The original Chan study used a different population, acquisition and partition.

## Data and interpretation

The 40 retained source identities are 31 children `sub-pixar001`–`sub-pixar031`
and nine adults `sub-pixar123`–`sub-pixar131`. They are the fixed subset used by
this task before the repair, not selected to obtain an effect. The authenticated
original phenotype table contains 155 people; 115 are outside this task, not
new QC exclusions. The selected child ages are about 3.52–4.86 years and adult
ages 19–39. Each run has 168 frames. These are convenience groups, not a sample
covering continuous development or ageing.

[Richardson et al. (2018)](https://doi.org/10.1038/s41467-018-03399-2) supplies
the movie resource. The later OSF/Nilearn derivatives were processed with
fMRIPrep, brain-masked, resampled to a 4-mm grid and stored as scaled int8;
they are not the paper's original SPM analysis. The source README is retained.
Schaefer labels are transferred by identity world coordinates from FSLMNI152/
NLin6 to the derivative's named NLin2009c space. This is an explicitly qualified
template approximation, not independently verified anatomical registration.
The BOLD headers omit spatial/time units; their temporal zoom of 1 is not
evidence of a one-second acquisition TR. No frequency filter uses it here.

Participant-level segregation and the adult-minus-child normal-Wald interval
are descriptive. Frames and edges are not independent replicates. Neither
the contrast nor its interval establishes within-person development, a
population effect, or a causal/clinical conclusion. A common movie and
acquisition/preprocessing differences may contribute to observed connectivity.

## Repair

The public contract fixes source membership, atlas transfer, 15 nuisance
columns, detrending/regression, Pearson/Fisher transformation and the primary
denominator. Negative Fisher-z edges become zero; **all** unique within- and
between-network pairs remain in their respective means. Excluding negative
pairs is a different conditional metric. Pooled pair weighting is disclosed;
it is not an equal-network average.

The verifier will reconstruct source-derived parcel/cleaned time series and
recompute submitted connectivity, complete-pair summaries and group results.
There is no expected sign, significance, outcome band, correlation with an old
answer vector, nonconstant-result requirement, or prose-keyword gate.
Seven compact artifacts expose source identity, support and numerical lineage.
Equivalent implementations and coherent axis/row reordering are accepted within
public tolerances. A source or numerical precondition failure cannot be hidden
behind a partial successful report. Scoring is binary and stated as such.

The old 6,008-byte reference bank was preserved outside the task without
loading its values. It is not used to choose a new answer or tolerances.

## Availability and validation boundary

The source manifest pins 83 originals plus three small provenance documents;
the final image must bake these at build time and execute fully offline.
OSF metadata declares CC-BY-4.0 while the pinned Nilearn notice says
noncommercial research use; both notices are retained without resolving their
precedence or claiming redistribution/commercial/movie rights. CBIG's MIT
notice is retained for the atlas distribution. No data/image release is part
of this local repair.

This is categorized as an easy method control, not asserted to defeat Sol.
See `REPAIR_STATUS.md` and the external per-run receipts for the current
engineering evidence. Source-free checks, native analyses, a clean-commit
Harbor oracle, final-image regressions, and frontier-agent calibration are
different validation stages. No frontier-model run is authorized here.
