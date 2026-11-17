# Public active-only controls

This component makes the existing direction-template control executable from the
public NEURAL-022 packet, with separate fit and prediction phases. It also supplies
the active-training mean and zero controls. The selected control is fixed during
fit. The original artifact scorer and all seven saved references are unchanged.

`fit` accepts only `training.npz`: 141 active rows, 390 integer count features,
two finite nominal velocities in m/s, eight commanded directions and opaque IDs.
It writes the fitted parameters and a hash of the complete training archive.
`predict` takes that hash-bound frozen file, the complete 92-row query archive
and the public roster. It rejects reordered identities, reused training identities,
disagreeing mode/direction context, negative counts, omitted strata, additional
archive members and query labels. Output is the existing 92-row prediction schema.

The direction control computes the arithmetic mean training velocity separately
for each of the eight commanded directions. The mean control uses all 141 active
training labels. The zero control returns zero without fitted parameters. None
uses neural counts to compute predictions; counts are validated to ensure that
the supplied packet has the declared complete observation shape. Query mode does
not alter these controls, and query-dependent fitting does not occur.

Use Python 3.12 and the existing artifact-grading NumPy dependency. From this
directory, with ordinary input files and fresh output paths:

```sh
python -I -B control.py fit --control active_direction \
  --training /absolute/public/training.npz --training-sha256 <sha256> \
  --out /absolute/output/frozen.json
python -I -B control.py predict \
  --frozen /absolute/output/frozen.json --frozen-sha256 <sha256> \
  --queries /absolute/public/queries.npz --queries-sha256 <sha256> \
  --cases /absolute/public/cases.json --cases-sha256 <sha256> \
  --out /absolute/output/predictions.json
```

Hashes must be supplied from the operator's accepted packet and the completed
fit output. `fit` prints the frozen output hash; `predict` prints the prediction
hash. The trusted collector still creates the separate submission commitment for
the [existing artifact grader](../artifact-grading/README.md) after the producer
has stopped. A declared hash authenticates bytes against that declaration; it
does not establish that the source packet is scientifically authentic.

The implementation preserves the source layout: six consecutive 20 ms bins,
65 units per bin, `counts.reshape(-1, 6, 65)`. The original target averages the
120 native 1000 Hz samples in the same retrospective movement-onset window, with
the recorded nominal NWB conversion raw × 0.01 + 0 in m/s. This code consumes
already prepared public arrays and does not establish the source conversion.

Source recovery uses the existing local `finite-program-v2/control_active_direction.py`
and its `TASK.md`, identified by SHA256 in `SOURCE.json`. The recovered direction
mean is the same procedure, with strict input admission and a frozen parameter
artifact added. No source numerical arrays, original predictions or historical
private targets were needed. Public original source routes are the versioned
[DANDI dataset](https://dandiarchive.org/dandiset/000127/0.220113.0359) and
[acquisition paper](https://doi.org/10.7554/eLife.48198); this component is project
software, not the acquisition authors' implementation.

Generated controls test the public boundary and arithmetic only. No authentic
packet preparation, comparison against stored predictions, model trial or
scientific qualification is claimed. This implementation is not a general
candidate sandbox, does not attest that an arbitrary frozen file came from this
fit program, and does not enforce access restrictions outside its own reads.
One exposed Han session, privileged passive references, retrospective timing and
unresolved kinematic matching retain their original limitations. These controls
support programme/investigation comparison, not direct or viewer understanding.
