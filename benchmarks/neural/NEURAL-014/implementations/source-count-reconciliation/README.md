# T15 source-count reconciliation

`reconcile.py` adds the missing block-level comparison between the author CSV and a complete operator-supplied trial-header inventory. It reads no HDF5 payload, transcript, token or neural value. It does not choose exclusions, alter the 45-session benchmark, or qualify its runtime.

The source declaration contains 127 files. The benchmark uses the 86 labeled training/validation members. These are different count universes: the author CSV combines validation and official test trials in `Val/Test` rows. Therefore a labeled-only census can compare training blocks exactly, but validation counts only form lower bounds on the combined rows. It cannot resolve the README's whole-archive count. The function reports discrepancies without selecting a favorable total or fabricating the missing test contribution.

Use `reconcile(task_json_bytes, author_csv_bytes, header_inventory_bytes)`. Inputs are captured bytes; the function returns a JSON-compatible comparison. It binds the fixed Dryad archive identity and the exact 127 declared member names/extents from the task. Header inventories must identify every member in the selected coverage (`labeled_train_val` or `all_source_members`), its byte extent, declared SHA256 and native group/session/block/trial identities. Duplicate native trials across files, missing members, foreign blocks, source-split inconsistencies, unexpected payload fields and malformed metadata refuse the comparison.

An inventory is not trusted merely because it supplies hashes. Source-file authentication and complete header extraction remain separate operator duties. The output always leaves source authentication and scientific qualification false. No real header census or decoded result was generated while building this component.

The pinned author helper iterates HDF5 trial groups, while the training dataset loader catches per-trial exceptions and continues. A nominal loader index length therefore cannot establish that all indexed trials entered a batch. The checker requires explicit complete metadata coverage instead of accepting such a count. This observation does not identify why the existing README and CSV totals differ.

Primary sources, inspected as hosted text at commit `980a5b7e96392210edf976d76bdb5d15d2e0e62b` (no raw-source authentication claimed): [README](https://github.com/Neuroprosthetics-Lab/nejm-brain-to-text/blob/980a5b7e96392210edf976d76bdb5d15d2e0e62b/README.md), [block CSV](https://github.com/Neuroprosthetics-Lab/nejm-brain-to-text/blob/980a5b7e96392210edf976d76bdb5d15d2e0e62b/data/t15_copyTaskData_description.csv), [evaluation helper](https://github.com/Neuroprosthetics-Lab/nejm-brain-to-text/blob/980a5b7e96392210edf976d76bdb5d15d2e0e62b/model_training/evaluate_model_helpers.py), and [dataset loader](https://github.com/Neuroprosthetics-Lab/nejm-brain-to-text/blob/980a5b7e96392210edf976d76bdb5d15d2e0e62b/model_training/dataset.py).

The task-local regression module uses clearly generated identity/count metadata against the frozen source roster. It covers full versus labeled-only count semantics, retained discrepancies, duplicate trials, incomplete rosters, split confusion, stale source extents, and rejection of target/signal fields. It does not test empirical HDF5 compatibility or establish neural understanding.

From the repository root, the explicit component CI command is:

```sh
python3 -I -S -B benchmarks/neural/NEURAL-014/implementations/source-count-reconciliation/tests/test_neural014_source_count_reconciliation.py
```

The test resolves the component and task relative to its own file, independently of the working directory. It is outside maintenance-test discovery; the sole integrator must enroll this explicit command in the appropriate component CI check. No workflow change is included here. In the construction environment, run it only through the existing shared two-slot test pool.
