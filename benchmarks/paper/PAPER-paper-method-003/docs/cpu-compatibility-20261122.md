# REVE: local CPU training compatibility

A real compatibility control passed using **one authentic training example**, two
linear-probe steps and one fine-tuning step. The zero-learning-rate step changed
no parameters. The next probe step updated three head tensors and preserved the
encoder. Fine-tuning changed 143 tensors, including 139 encoder tensors, with
finite nonzero gradients.

A 279,435,937-byte checkpoint was loaded with `weights_only=True` into an
independently reconstructed model. Every saved tensor and the evaluation logits
matched exactly. The [aggregate record](cpu-compatibility-20261122.json) gives the
source identifiers, runtime versions and limitations without publishing signals,
labels, weights or private paths.

This was an explicit CPU/float32/math-attention control of the existing
[matched reference implementation](../implementations/matched-reference-v1/README.md)
and [pinned author source](https://github.com/elouayas/reve_eeg/tree/06a7059a07c3dabd80aee60c3dbc1eca4bdbe1c7).
Three pinned dependencies were installed into a private overlay. The shared
environment, original CUDA/fp16 trainer and installation gate were unchanged.
The private compatibility driver is not yet an installed portable public CPU profile.

The episode took 14.50 seconds, including dependency setup; the training control
took 10.13 seconds. Maximum child RSS was about 2.23 GB, not a hard memory limit or
simultaneous process-tree measurement. A capacity check initially refused before
any payload work; a separately selected continuation completed one actual episode.
Both observations remain recorded.

**No held examples, validation/test predictions or scored metrics were used.**
This is neither a full released-recipe baseline nor evidence of reproducing or
exceeding the paper. The released direct200 preparation and historical 128Hz
intermediate remain distinct, and historical Table 12 run provenance is unresolved.
No benchmark readiness status changes.

The next implementation step is a declared CPU profile in the existing trainer,
or a compatible CUDA runtime for its unchanged default, followed by a bounded
training-throughput check and a prospectively fixed complete baseline. The
one-example timing above cannot establish full-training cost or accuracy.
