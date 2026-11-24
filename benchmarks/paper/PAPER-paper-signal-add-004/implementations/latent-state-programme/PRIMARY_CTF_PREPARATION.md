# Original CTF inputs for the selected paper task

`primary_ctf_inputs.build` prepares the original 65-person CTF network inputs for the current TDE-HMM/TDE-DyNeMo paper objective. The older `source_inputs.build` continues to implement the broader six-branch source program and still requires all 114 Elekta runs. This additive entry point keeps those separately scoped missing inputs from being a prerequisite for preparing the current primary inputs.

The operator supplies the exact released CTF ZIP and the existing pinned original directory metadata, plus explicit logical read, write and per-array limits. Both source identities are fixed in code. All 133 ZIP entries, their order and metadata are checked; no duplicate names are collapsed. The function decompresses the original demographics and all 65 network members. The 65 burst members stay in the authenticated original archive; this primary projection does not read their bodies or claim the burst analysis is complete.

Each of the 65 complete 38-parcel network members is retained unchanged, together with a float64 regional view and an explicit physical-row map. Demographics must preserve the original subject00–subject64 order and are validated before any signal is decoded. No rows, persons or channels are dropped. No TDE, PCA, standardization, HMM, DyNeMo, uncertainty calculation or model selection is run by this preparer. Those source-native operations remain distinct future stages. The native file layout serves both selected models; the existing regional-packet schema remains `ctf_tde`, and no invented DyNeMo packet ABI is added.

The completion record is `PRIMARY_CTF_INPUTS.json` with schema `osl_primary_ctf_originals_v1`. It deliberately cannot stand in for the broader `ORIGINALS.json` completion. No runtime caller, central registry, source authority or scientific status is changed by this component. Integration must separately bind its source and choose an appropriate current-primary execution path.

The live API rejects changed archive/directory identities before creating an output tree. Generated tests exercise the complete 65-person projection helper, directory and budget failures using invented in-memory members. They do not authenticate an original archive, read authentic signal arrays, fit models or establish a successful real-data preparation. Failure can leave a partial owned output directory; without the final completion record it is incomplete and must not be resumed or accepted automatically.

An operator can invoke the same API through `python primary_ctf_inputs.py --help`. The command takes a local JSON specification with exactly `ctf_archive` and `ctf_directory`; each contains `path`, `bytes` and `sha256`. The source descriptors must retain the fixed identities in this module. Paths select already available local files; the command never downloads sources. For example, after separately authorizing preparation and selecting its storage/RAM budget:

```sh
python primary_ctf_inputs.py \
  --spec /absolute/path/ctf-spec.json \
  --spec-bytes "$SPEC_BYTES" --spec-sha256 "$SPEC_SHA256" \
  --output /absolute/path/new-primary-inputs \
  --read-bytes "$READ_BYTES" --write-bytes "$WRITE_BYTES" \
  --array-bytes "$ARRAY_BYTES"
```

The operator supplies every value above; the example is not an execution grant or a recommended budget. `SPEC_BYTES` and `SPEC_SHA256` bind the exact specification bytes. `READ_BYTES` includes that specification, the authenticated source ZIP and directory, and expanded primary members. The command rejects an existing output directory before opening the specification. It writes one JSON receipt to stdout only after the preparation completion record has been published; the receipt includes total logical I/O and the unchanged API result. Exceptions produce a nonzero exit and no success receipt. The stdout receipt is transport output, not an additional persisted file covered by `WRITE_BYTES`; account for any caller-owned log capture separately.

This local operator command does not enroll the source in a runtime, resolve paper+data versus paper+data+author-code delivery, or admit execution. It needs Python with NumPy for actual array preparation; displaying help and validating argument syntax do not need NumPy. Generated command controls verify dispatch, immutable metadata, budgets, failure behavior and rejection of a changed original-source pin. They do not substitute for a future authorized preparation on the real release.

Memory and disk admission remain the caller's responsibility. The implementation captures the entire 684,320,829-byte source archive and materializes one complete network member and its normalized copy at a time. `array_bytes` bounds each output allocation, not peak process memory or physical I/O. Logical reads charge the ZIP and expanded primary members; logical writes charge every published output, including the final completion record in the returned operation accounting.

The original numerical fit baselines, historical recipe correspondence and independently observed DyNeMo final training-epoch statistic remain unresolved. This input-preparation component establishes neither reproduction nor improvement.
