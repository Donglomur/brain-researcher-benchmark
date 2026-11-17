# UMBRAE grounding component

Scores operator-supplied BrainHub referring-expression grounding outputs: per-subject All-category accuracy at strict IoU > 0.5, secondary IoU/thresholds and five salience groups. It aligns first-box responses by image/category, keeps missing predictions in the denominator, checks declared candidate/baseline/neural-free/shuffled controls, and computes paired shared-image uncertainty.

Requires Python 3.10+ standard library only. From this directory:

```sh
python3 -m unittest discover -s tests -v
python3 grounding.py --contract CONTRACT.json --annotations ANNOTATIONS.json --image-order ORDER.json --output NEW_RESULT.json
```

`make_control.py NEW_DIRECTORY` creates a small generated engineering example. Native data, checkpoints and inference are never fetched or run. Native annotation/order qualification, actual exposure and intervention fidelity, reference numerical agreement, rights and scientific qualification remain held. This is a prospective grounding component; it does not complete UMBRAE training, adaptation or whole-paper reproduction.

See the [input contract, scientific semantics, requirement mapping and limits](../../docs/initial-evaluator-v1.md) and [pinned source provenance](source-provenance.json).
