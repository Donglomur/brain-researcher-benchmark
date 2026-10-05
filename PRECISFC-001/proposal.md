# PRECISFC-001: a public-contract connectome sensitivity control

This task is retained as an **easy computational method control**, not a hard
paper-finding reproduction. Gordon et al. (2017), *Precision Functional Mapping
of Individual Human Brains*, provides the scientific context and Midnight Scan
Club dataset attribution ([paper](https://doi.org/10.1016/j.neuron.2017.07.011)).
The six-person, three-session, Power264 analysis below is a secondary adaptation;
it is not the paper's data-quantity reliability characterization or a fingerprint
identification experiment. No Figure/Table result is claimed to be reproduced.

## Fixed question and independent unit

How does selecting the released temporal-mask frames change each person's
cross-session connectivity-pattern similarity on a common edge support? Both
all-frame and censored arms, on all six fixed people, are primary. Equal-person
group summaries and a separate publicly defined duration-QC subset are reported.
The three pairs per person overlap; neither pairs nor edges enlarge the person N.
No required effect direction, numeric headline, participant ranking, ID exclusion,
drowsiness attribution or minimum reliability is graded.

## Original public substrate, qualified geometry and time

The build stages 18 original processed NIfTIs plus 18 original masks from
[OpenNeuro ds000224 release 1.0.4](https://doi.org/10.18112/openneuro.ds000224.v1.0.4).
Release commit, Git-annex MD5/size, immutable S3 version IDs and measured complete
SHA256 values are frozen in `environment/source_manifest.json`. Source data are
already interpolated, nuisance-processed and filtered; all-frame is not raw.
No surrogate cohort or author-generated signal replaces the originals.

The published 4dfp stored transform maps Power's published integer MNI centres
to 711 physical coordinates. Original point-transform code, the author's paired
coordinate table and converter/canonical-333 definitions support its direction
and match all observed sforms. This is operational provenance, not proof of the
exact historical converter invocation, original IFH or subject registration quality.

All derivative headers record 1.0 second. Acquisition metadata specifies 2.2
seconds and published processing preserves frame indices. The public method
therefore declares a 2.2-second acquisition-frame assumption for retained-duration
QC while retaining the observed 1.0-second headers. Neither metadata discrepancy
nor spatial conversion is hidden as a difficulty lever. Source and atlas licensing
are distinguished; a standalone atlas-data license has not been established, and
this local repair does not authorize publishing a data bundle or container image.

## What the verifier measures

The public method contract fixes geometry, numerical-zero handling, both arms,
common support, null propagation, keyed artifacts and tolerances before new BOLD
value analysis. A source-only reference binds every sphere membership, mask and
full-precision mean/peak to originals. Pointwise fidelity is supplemented by a
public centred-signal constraint so invented tiny fluctuations cannot turn a
constant source into apparently valid FC. Downstream quantities are recomputed
from accepted submitted means; coherent legitimate numerical-boundary changes
are not rejected merely for differing from reference-derived support.

Prose is not a scientific scoring gate. Extra CSV columns and coherent row/axis
reordering are accepted. Empty, fabricated, wrong-source, wrong-geometry,
wrong-timing, either-arm substitutions and internally inconsistent outputs must
fail; equivalent computations and honest undefined estimates must pass.
Scoring is all-or-nothing and disclosed. See `REPAIR_STATUS.md` for actual evidence,
not historical proposal claims. Oracle execution is not a model-hardness measurement.

## Runtime and evidence boundary

Runtime is offline, CPU-only, 2 CPUs and 8 GiB; original inputs total 3,651,426,287
bytes. Source data are baked at build time with bounded checksum-verified access.
Independent source routes and an offline in-container oracle are required before
marking the local repair validated. No Sol/frontier run is authorized or claimed.
