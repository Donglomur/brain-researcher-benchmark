# Paired participant materials and scorer controls

`delivery.py` exports the complete admitted input panel twice, with the same original paper, validation observations, protocol, metrics and prediction format. Only `paper_with_code` receives the pinned official implementation source. Both conditions exclude author checkpoints, operator predictions and original test targets. This prepares materials; it does not run a participant, enforce a sandbox or establish scientific improvement.

Both native phase references must exist before exporting. Test admission uses `reference_panel.json`; validation admission uses `reference_validation_panel.json`, including the validation target hash and observed dataset shapes. The exporter checks HDF5 members and content hashes and rejects payloads inside Git worktrees.

From this implementation directory, an operator can run:

```sh
"$SMC_STAGE/venv/bin/python" delivery.py \
  --prepared-root "$SMC_STAGE/inputs" \
  --author-source "$SMC_STAGE/author" \
  --paper "$SMC_STAGE/paper.pdf" \
  --output "$SMC_STAGE/participant_pair" \
  --reserve-bytes 64424509440
```

`--reserve-bytes` defaults to zero for portable use. The exporter plans the exact bytes of both bundles and every JSON manifest before copying, then requires that capacity plus the explicit reserve. The local construction wave must pass **64,424,509,440 bytes (60 GiB)** and also retain its shared resource-ledger checks. The export does not reserve capacity against unrelated concurrent writers. Atomic staging and a final complete inventory check prevent a partially written bundle from being presented as completed.

`pair_manifest.json` records identical shared-file hashes, the code-only additions, the two delivery-manifest hashes and the explicit reserve. Its status is `participant_materials_prepared`, with `episode_executed: false`. Future paired runs must freeze equal candidate budgets separately; this export does not assign or spend them.

The original temporal dependencies are part of the same-task contract for final test evaluation arrays (`eval_rates_*`). For zero-based **test** observation bin `t` from 0 through 34, a candidate evaluation rate may depend only on held-in bins from the **same trial**, starting at bin 0 and ending at `max(t,13)` in the causal-proposal arm, or `min(t+17,34)` in the noncausal-proposal arm. The causal startup bound reflects the original encoder's reflect padding; it does not establish strict zero-lookahead operation. Test forward bins 35 through 44 may use all 35 observed bins, with no future spikes or test behavior. Permitted training/validation data fix the trained model; randomness must be independent of test data. Test-wide fitting, normalization or cross-trial test-data use cannot bypass the bounds. Any architecture may satisfy the contract. Training-rate predictions may use permitted training/validation observations, including all supplied neurons and forward bins, but must not depend on test data.

**Temporal enforcement remains unresolved.** Complete HDF5 files expose more than the allowed prefix for some predictions. This exporter supplies materials and records the bounds; it does not restrict reads. A runner must enforce and audit each temporal view before causal or joint scientific admission. An arm label, a successful material export or a higher score alone cannot establish this compliance. Earlier exported pairs remain historical materials receipts; regenerate into a new output directory when this contract changes.

The mandatory original-scorer control uses the unchanged MIT evaluator in `third_party/nlb_tools_0_0_3/evaluation.py`. Its accompanying `PROVENANCE.json` records the authenticated official wheel, original archive paths and exact hashes; its original license is included. The loader verifies the evaluator hash before execution. No environment variable or network access is needed to obtain the fixture during CI.

```sh
python -I -B -m unittest discover \
  -s benchmarks/paper/PAPER-SMC-RNN-2024/implementations/source-matched-nlb-v1 \
  -p 'test_*.py' -v
```

Run that discovery command from the repository root with NumPy, SciPy, scikit-learn and h5py installed. The original evaluator test always runs; missing scientific dependencies fail the suite. Its arrays are generated controls, not authentic neural observations. CI dependency versions may differ from the source-qualification versions in `requirements-cpu.txt`; those CI results demonstrate generated compatibility, not reproduction of published scores. Operator scoring can use the same vendored evaluator through `--scorer-source third_party/nlb_tools_0_0_3/evaluation.py`.
