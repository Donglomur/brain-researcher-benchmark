# Prospective calcium/kinematics decoder

[The session-local pipeline](../implementations/train-only-decoding-v1/README.md)
adds a first owned normalized-data decoder, complete five-mouse/ten-session
scorer, phase/direction controls, training-trial rotation diagnostic and
descriptive paired-mouse uncertainty. Its
[input schema](../implementations/train-only-decoding-v1/SCHEMA.md) and
[source derivation](../implementations/train-only-decoding-v1/PROVENANCE.json)
describe exact identities and remaining native-input requirements.

Cell selection, centering, PCA and regression use only declared training or
calibration trials. The published source's preprocessing-before-CV and
variance-explained result are distinguished from this new prospective policy.
Angles and velocities remain separate 24-channel conditions. Session-local ROI
spaces are never pooled as though neuron identities match across animals.

The recommended source recipe is retrospective lift-conditioned readout with
100 training-selected cells,90 centered PCs, a fixed ridge penalty1.0 and
-100:10:+400ms windows. Its explicit deterministic whole-trial split and
training-SD normalization must be frozen before outcomes. A new-mouse local
calibration comparator does not demonstrate transferred cross-animal decoding.

Native MAT equality, eligibility/clock alignment, upstream calcium exposure,
source reference competence, protected execution and scientific qualification
remain open. All outputs retain false scientific-verification flags. Source
and generated-control results are construction evidence, not a research result.
