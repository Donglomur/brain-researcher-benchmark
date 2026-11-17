# NEURAL-040 initial evaluator

This package implements a prospective multimodal encoding comparison: train-only
standardization, PCA whitening and fixed-rank ridge for full, no-audio, no-visual and
no-language arms; a separate scorer recomputes held-out Pearson differences per
film/parcel/person, numerical claims, descriptive four-person uncertainty and paired
within-segment circular-shift diagnostics. It requires all four source participants
and 1000 ordered parcels per person.

Use Python 3.11 and NumPy. No network access, model download or dependency installation
is performed by these commands. From this directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
python evaluator.py encode --protocol protocol.json --features features.npz \
  --training-targets training-targets.npz --training-target-metadata training-targets.json \
  --output-dir encoded
python evaluator.py score --protocol protocol.json --predictions encoded/predictions.npz \
  --prediction-metadata encoded/prediction-metadata.json --private-targets private-targets.npz \
  --private-target-metadata private-targets.json --output score.json
```

Supply precomputed features and separately packaged training/private targets with
source-derived IDs, native parcel order and hash-bound metadata. The encoder creates
a new output directory. See the [complete packet and analysis documentation](../../docs/initial-evaluator-v1.md)
for protocol fields, fitting semantics, source attribution and outputs.

Only generated engineering controls have run. This is public-development construction
source, not native organizer reproduction or a scientifically qualified benchmark.
Authentic payload/schema/alignment, full selected population, feature/model exposure
and rights, media rights, reference execution, protected evaluation and scientific
admission remain unresolved. Matched bottleneck/readout capacity does not establish
matched pretrained-extractor capacity. Shift tail fractions and four-person bootstrap
intervals are descriptive, not general-population or calibrated significance claims.
