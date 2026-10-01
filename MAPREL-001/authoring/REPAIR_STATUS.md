# Authenticated spatial-null construction

Null evidence now includes actual centroid geometry, hemisphere membership, spin indices,
declared seed/method and sampling statistics. The grader regenerates hemisphere-constrained
indices and recomputes each null correlation/p rather than checking calibrated spread.
Original/vasa/hungarian spin variants are supported; other null families are not silently
treated as spins. Multiple or fake-wide arrays cannot override the declared distribution.
Geometry must come from a genuine pinned surface/atlas bake in geometry_reference_v2.npz
with schema_version=spatial-geometry-v2; old references cannot supply this.
Pending: independent surface/CIFTI medial-wall alignment audit, source-hash pins,
genuine geometry/reference regeneration, real-spins positives and clean-container oracle.
Toy geometry in authoring unit tests tests the validator only, not benchmark data.
