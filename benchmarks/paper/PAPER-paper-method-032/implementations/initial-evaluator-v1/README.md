# MindEye2 initial evaluator component

This package scores identity-bound, precomputed MindEye2 retrieval embeddings using the corrected image/brain directions and 30 frozen pools of 300 candidates. It also provides notebook-defined reconstruction feature kernels, post-model repeat averaging, and first-session/checkpoint exposure audits.

Dependencies: Python 3.11+ and NumPy. It never downloads data or models. From this directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
python3 evaluator.py required-assets 1
python3 evaluator.py audit-exposure ledger.json
python3 evaluator.py score --reference reference.json --reference-sha256 TRUSTED_RAW_FILE_SHA256 --candidate candidate.json --image-features images.npy --brain-features brain.npy
```

The operator supplies the protected reference and its independently trusted hash; no authentic reference, data, images or weights are distributed. Numerical tests use bounded generated arrays. Native feature extraction/adaptation, complete reconstruction metrics, full native asset acquisition, source parity, authentic population/reference verification, and rights/exposure qualification remain held. Released-weight one-session adaptation is distinct from rerunning shared-subject pretraining. Scientific qualification and full-contract completion remain false.

See [the full task documentation](../../docs/initial-evaluator-v1.md) for exact manifests, source commitments, prospective policies, metric semantics, validation evidence and remaining requirements. `provenance.json` maps each component to primary source locators.
