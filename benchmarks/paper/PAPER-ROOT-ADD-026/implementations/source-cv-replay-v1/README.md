# Source condition-CV replay and training packet projection

This component replays the sampling loop in the pinned author fitting script and exports a training-only packet for one electrode and fold. It preserves all 79 Figure 3 electrodes, all 72 conditions, 12 folds, six category-balanced queries per fold, and 66 training traces. It performs no fitting or scoring. It is a software component, not a qualified same-task baseline or improvement result.

The existing historical executor uses one shared SHA-ranked fold schedule and four reconstruction procedures. Its source and evidence remain unchanged. This component instead implements the original `random.sample(pool, 1)` followed by removal, in the source category order. It records a prospective seed, Python version, RNG state hashes, exact ordered row allocations, source-table hashes and source-code identity. Each electrode has its own deterministic stream derived from the master seed and electrode identity. Author and candidate must consume the same frozen manifest. Pairing their folds is a prospective comparison rule; the paper's independently scheduled, unseeded model runs are not recovered.

The method does not assume conditions occur in one convenient row order. It requires the actual ordered identities from every authenticated source table. Every condition appears in exactly one query fold. The operator pins `manifest_sha256` independently before downstream use; an embedded self-hash alone is not authorization. This digest covers canonical JSON excluding its own digest field, and differs from the SHA-256 of the saved file reported by the CLI.

## Concrete source discrepancy

The released source header is `trial_type img_cat temp_cond 0 ... 818`. The pinned `modelling_modelFit.py` full fit selects named time columns. Its CV fit/test slices positions `2:2+819`, which include `temp_cond` and omit sample `818`. The cached source-version audit traces these expressions to a prepublication commit; it does not identify which code actually produced Figure 3.

Projection therefore requires one explicit branch:

- `source_positional_cv`: reproduces the inspected CV column selection, including the temporal-index column. This is a literal-source diagnostic, not a claim that the erroneous coordinate is a neural measurement.
- `named_response_columns`: selects all 819 neural samples by name, an explicit correction whose parity with the historical published run remains unestablished.

Both branches retain the same 66/6 condition split and label their target columns. A source-faithful replay of the sampling loop does not settle this column discrepancy, the publication input lineage, original RNG states, numerical Figure 3 comparator, or superiority uncertainty. These branches must remain separate in any later calibrated comparison. Nonfinite source tables are rejected pending a reviewed source policy rather than imputed or scored with a changed NaN rule.

## Operator inputs and commands

Only trusted preparation may access the complete source table. Candidate processes receive the exported packet, never the manifest plus all source tables or this operator command. For every electrode, provide a metadata record with its exact source-table SHA-256 and its 72 ordered identity objects:

```json
{
  "schema": "temporal026-ordered-source-metadata/v1",
  "electrodes": [
    {
      "electrode_id": "sub-p11_GB002",
      "source_data_sha256": "<64 lowercase hexadecimal characters>",
      "rows": [
        {"trial_type": "onepulse", "img_cat": "BODIES", "temp_cond": 0}
      ]
    }
  ]
}
```

The abbreviated example is not runnable input: all 79 exact electrode identities and all 72 rows each are required. `cohort.json` preserves the source area selection: V1–V3=17, VOTC=15, LOTC=47, participant totals 38/7/10/24. The six source entries assigned `none` are excluded by the Figure 3 rule, not a new performance-based selection. The source-contract proposal below identifies the already-existing roster reconciliation evidence.

From this implementation directory, using only an externally authorized preparation protocol:

```sh
python3 -I -B replay.py freeze --metadata /operator/ordered-metadata.json --seed 20261117 --output /operator/folds.json
python3 -I -B replay.py project --manifest /operator/folds.json --manifest-sha256 FROZEN_CANONICAL_DIGEST --source-table /operator/data.txt --electrode sub-p11_GB002 --fold 0 --branch named_response_columns --output /participant/fold0.json
```

The freeze command requires metadata only. Projection checks the independently supplied manifest digest, entire 79-electrode allocation, source bytes, literal-space header, exact row identities and all 819 values before exporting. Output creation is exclusive: existing files are not overwritten. The packet contains 66 response arrays and six identities with no response fields. Stimulus timing/pulse definitions still need the existing authenticated source preparation; this component does not invent or replace them. Separate fresh process state per fold and access-arm transport remain operator responsibilities. Across all folds, every condition is training in another fold, so collecting all packets in a persistent candidate state would leak held-out information.

Runtime dependencies: Python standard library only. New dependencies, downloads, author model execution and authentic numerical preparation performed for this change: none.

## Verification and limits

`test_replay.py` constructs generated response tables with row-specific sentinels. It checks the full roster/split, all 12 no-leak exports, exact literal versus named column projection, reordered source conditions, immutable input hashes, malformed/missing/duplicate identities, altered folds, duplicate JSON keys, nonfinite tables and exclusive CLI writes. Supplying `--author-fit-source` additionally authenticates the cached upstream file and extracts only its two sampling statements through AST; that generated control compares their actual results against this implementation for three seeds and two row orders. It never imports or executes the model, file I/O, optimizer, or author fitting script.

Use the centrally reviewed lightweight test pool for checks. Exact pool receipts and qualification limits are recorded in the external handoff. No authentic response bodies, private historical targets, predictions, saved parameters or fitted scores were opened for this change. The metadata inventory remains source evidence, not empirical preparation.

Current registration enrollment, runtime replacement and canonical contract changes are proposals only. See `CONTRACT_PROPOSAL.md` and `SOURCE_EVIDENCE.json`.
