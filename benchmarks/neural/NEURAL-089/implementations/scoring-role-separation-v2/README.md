# NEURAL-089 protected scoring input roles

This scorer preserves the original 39-class predictions, target joins and metrics.
It rejects a protected-target path that aliases the panel or submission before
reading any input body. Identical paths, resolved relative paths, symlinks and
hardlinks are checked using filesystem metadata. A role conflict returns
`operator_error` with no score and `private_targets_read: false`.

Use `scorer.py` with the same `--submission`, `--panel`, `--targets`,
`--targets-sha256` and `--output` arguments as the preserved delivery source.
The original source is retained unchanged; `SOURCE_BINDING.json` identifies it.
The trusted operator must keep paths fixed during this check and scoring. This
preflight does not provide a sandbox or protect against concurrent hostile path
changes. It adds no model results or scientific qualification.

`test_role_paths.py` contains generated regression controls for role aliases,
refusal before private reads and unchanged scoring with distinct paths.
