# PAPER-ROOT-ADD-005 initial evaluator

This executable construction component binds exact stimulus identities and complete operator rosters for THINGS-fMRI participants `01`, `02`, `03`, fits paired 66-dimension/category/shape nested grouped ridge baselines, and reports signed held-out R², Pearson correlation and predictive commonality. All participants and declared voxels remain visible.

Requires an existing Python 3 environment with NumPy; tests also require pytest. Run from the repository root:

```sh
python3 benchmarks/paper/PAPER-ROOT-ADD-005/implementations/initial-evaluator-v1/evaluator.py \
  --input operator-export.npz --roster operator-roster.json --output scores.json
python3 -m pytest -q -p no:cacheprovider \
  benchmarks/paper/PAPER-ROOT-ADD-005/implementations/initial-evaluator-v1/tests
```

The NPZ/roster input format, fixed split and metric policies, source mapping and controls are in the [full implementation documentation](../../docs/initial-evaluator-v1.md). Tests use generated engineering fixtures only.

This prospective image-family/category analysis differs from the author's session CV and residual-response partition. Authentic acquisition, native table conversion and reproduction, exact shape-source qualification, protected grading, rights, full-cohort resource measurement and scientific qualification remain open. No historical or scientific result is claimed. Every output retains those holds and marks native reproduction, scientific qualification and full-contract completion false.
