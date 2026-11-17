# Maintenance and historical reconstruction

The public benchmark catalog comes from `benchmarks/registry.json`. Use `python3 -I -S -B scripts/catalog.py --check` to verify its generated views. These maintenance builders do not discover or register current benchmarks.

The `build_*` scripts reconstruct earlier construction metadata from an **external input tree in its original directory layout**. The private construction rosters and audits are not included in this public repository. Historical path strings in these builders identify those original inputs; they are not fallback discovery paths for the current catalog.

Every builder CLI requires explicit inputs and a separate staging destination:

```sh
python3 -I -S -B scripts/maintenance/build_paper_delivery_manifests.py \
  --construction-root /path/to/original-input-tree \
  --output-directory /path/to/separate-staging-directory
```

The destination must be outside both this repository and the input tree. Builders preserve their original validation and source-pin checks. They write reconstructed artifacts for review; they never overwrite the frozen snapshots in `docs/provenance`, canonical `task.json` files, or the current registry. Current generator pins are identified separately from original construction evidence. Generated Markdown retains links into the original input layout and is not a public navigation page.

`--check` is available for the paper/neural delivery builders and the paper construction audit. It checks the explicitly selected staging destination. The paper construction audit's `--self-test` uses generated metadata and does not require an input tree.

`apply_neural_contract_amendment.py` uses the same input/output arguments plus `--proposal`, relative to the input tree. It writes the proposed roster, original roster and receipt into a **fresh** staging directory. The input roster remains unchanged; applying a staged amendment to current task registrations requires a separate reviewed change.

`neurobench_source_queue.py` provides reviewed source commits and root integration. Its commands and controls are described in [the source queue guide](../../docs/development/source-queue.md). It has no push command. Its generated tests are in `source-queue-validation/test_queue.py`; their `authoring/` names are disposable fixture paths, not public repository layout requirements.
