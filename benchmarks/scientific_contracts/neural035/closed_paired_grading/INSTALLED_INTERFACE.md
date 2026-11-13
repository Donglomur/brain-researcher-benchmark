# Preserved trusted-host interface

This is the public source profile of the NEURAL-035 closed paired grader. The
legacy filename and installed-source schema names preserve the interface;
they do not report an actual installation or authorize execution.

The strict `closed_paired_grading` child contains exactly ten files. Authenticate
the entrypoint and exact SOURCE_MANIFEST bytes before loading operator.py under
a unique trusted module name. `inspect(source_pin, budget)` captures only those
ten files with exact pins, one-link ordinary-file checks and stable physical
identities. Ordinary 0644 checkout files are supported; extra child files fail
closed. Source buffers, reads and CLI output have explicit logical debits.

The only command-line operation is `inspect`. Its required operands are
`--source-bytes`, `--source-sha256`, `--read-bytes`, `--write-bytes`, `--seconds`.
Use Python 3.11 with `-I -S -B`; source inspection requires no third-party package.
The minimum read grant is the total of all ten source lengths plus ten. The
minimum API write grant is their total; CLI additionally reserves 32,768 bytes.
These are logical interface bounds, not heap, kernel-I/O or hostile-process
containment measurements.

The preserved API is:

```python
grade_pair(source_pin, repository, producer_root, selection_operand, terminal_raw,
           enclosing_observation, prepared_root, authority, *, max_read_bytes,
           max_write_bytes, deadline)
```

`repository` is the absolute public `source_tree` path. Its complete original
relative layout keeps the adapter's HERE.parents[5] interpretation unchanged.
DEPENDENCIES retains 31 exact descriptors: 28 packaged ordinary source bodies
and three missing external records. `source_loader.load` does not skip missing
records or synthesize them. This checkout therefore cannot complete grading.

`authority.require_neural035_closed_pair_grading(selection, observation)` belongs
to a separately trusted operator and must return None only for the selected
operation. The package provides no approving implementation. Source capture and
compilation of four fixed aliases precede that hook; external dependencies,
producer reports and protected inputs follow it. Exact captured Budget type,
preceding read/write debits, total grants and the caller's absolute deadline
carry through unchanged. The final deadline check occurs after all four aliases
are restored, including absent aliases and prior None values. A dedicated
serialized trusted process is required; the local lock is not a host sandbox.

The original grader checks independent natural process termination, full paired
producer closure and public identity before resolving the protected root, then
captures the single fixed target body. No candidate-controlled source reader,
target callback or metadata-only authority is introduced. The original fixed
comparator and full 14-session/seven-mouse/1,012-cell scope, 28 queries per role,
99 shifts and 200,376 surrogate slots remain mandatory. Native, rights,
privacy, exposure, authentic-data and scientific qualification gates remain.

The public registration README changes its registration manifest identity;
accepted old receipts cannot bypass that identity difference. Public CI checks
only source and engineering refusal boundaries. Historical engineering witness
success is inherited source provenance, not a newly run scientific result,
successful public grading receipt or installation claim.
