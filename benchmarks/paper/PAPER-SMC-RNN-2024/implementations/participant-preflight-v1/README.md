# Participant prediction preflight

Check SMC-RNN prediction formatting before handing predictions to the trusted
operator. This command needs only your condition's public **test** `panel.json`
and your numerical predictions. It does not require the paired delivery manifest,
the other access condition, author models, or evaluator targets. The operator's
continuous-v2 `freeze` and `score` stages remain separate.

Use an existing Python 3.11+ environment with NumPy and h5py. From this directory:

```sh
python -I -B check_submission.py \
  --panel "$CONDITION/inputs/mc_maze/test/panel.json" \
  --panel-sha256 "$PUBLIC_PANEL_SHA256" \
  --outcome improvement --submission "offline=$PREDICTIONS" \
  --max-bytes "$SUBMISSION_BYTE_CAP"
```

For reproduction, use `--outcome reproduction` and both
`--submission "causal=$CAUSAL_PREDICTIONS"` and
`--submission "noncausal=$NONCAUSAL_PREDICTIONS"`. Both files must pass before a
success report is printed. The byte cap applies to the complete submitted set.
Use the panel identity supplied by the operator for your packet. A matching local
hash alone does not prove packet delivery or condition isolation.

Predictions retain the existing `mc_maze_20` HDF5 interface: six required complete
arrays, or all eight including **both** train-forward arrays. They must contain
finite nonnegative expected spike counts per 20-ms bin. The check reuses the
unchanged source validator for all original dimensions, manifest identity,
dataset names, and rejection of external/soft links and indirect data. It does
not repair, fill, reorder, clip, convert, or score submissions.

The helper authenticates `source-matched-nlb-v1/scorer.py` and its public
`reference_panel.json` before importing the validator. Their normal sibling
location is used automatically; `--source-dir` supports a relocated copy with
the same byte identities. No model-loading or original evaluator function is
called. Successful JSON goes to stdout; invalid inputs return exit code 2.

`format_valid` is a local formatting result. Semantic trial/neuron/bin ordering,
source-method fidelity, actual asset use, condition access, and model provenance
remain separate. The report is not an operator freeze or an accepted scored
submission. Concurrent hostile mutation and sandbox enforcement are outside this
helper's guarantees. The publicly exposed original TEST panel remains exposed;
preflight creates no new scientific evidence or benchmark registration.

Generated controls use reduced artificial panels and exercise the unchanged
validator while replacing only its expected reference-panel path in the test
process. They do not load neural observations, predictions, private targets,
weights or an original evaluator, and they establish no scientific performance.

```sh
python -I -B test_check_submission.py --source-dir ../source-matched-nlb-v1
```
