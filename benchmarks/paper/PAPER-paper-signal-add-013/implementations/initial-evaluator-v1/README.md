# CALC–CTRL BOLD/CMRO2 map-array component

This owner-side component computes the fixed 40-participant CALC–CTRL percentage contrast and the source Fig. 2B median reductions within frozen positive/negative BOLD PLS masks. It preserves corrected CMRO2 as primary and reports the first-30-original/last-10-measured-CBV source convention as a separate sensitivity.

Requires Python 3 and existing NumPy. Inputs are an owner-frozen `manifest.json` and hash-bound `maps.npz`; the expected manifest hash must come from trusted owner state outside candidate control.

```sh
python3 evaluator.py /owner/manifest.json --expected-manifest-sha256 OWNER_FROZEN_DIGEST --output /owner/contrast.json
python3 -m unittest discover -s tests -v
```

The calculation includes descriptive spatial association and paired whole-participant bootstrap summaries. It does not execute PLS, reconstruct mqBOLD, authenticate NIfTI extraction or establish spatial significance. Source masks remain exposed reproduction masks. Authentic reference execution, numerical targets, protected assessment, physiological/native qualification and scientific qualification remain held. Generated tests establish engineering behavior only; every result has null reward and false scientific qualification.

See the [full interface, scientific derivation, provenance and limits](../../docs/initial-evaluator-v1.md) and [source provenance](provenance.json). Data CC0 and upstream code CC BY-NC-SA 4.0 terms remain distinct; no upstream notebook is bundled.
