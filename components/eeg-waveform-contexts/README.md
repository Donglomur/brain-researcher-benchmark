# Complete EEG waveform contexts

This command fills the preparation gap before the existing NEURAL-077 waveform
response collector. It writes all 400 independent model inputs, using the exact
existing four demonstrations and unchanged prompt. It uses Python 3.11 standard
library only on macOS or Linux. No model, API key, network, NumPy, private targets
or inference service is used.

```sh
python3.11 -I -S -B export_contexts.py \
  --packet /absolute/path/to/admitted/public-packet \
  --output /absolute/trusted-parent/fresh-context-export
```

The packet must contain the five exact public members pinned in the source:
`queries.jsonl`, `demonstrations.json`, `prompt.txt`, `response_schema.json`, and
`manifest.json`. The command opens only those names, refuses symlink/special-file
members and authenticates all five before creating output. The packet root and
output parent must be trusted operator-controlled directories; ancestor paths
and concurrent hostile writers are not isolated by this converter.

`contexts.jsonl` has exactly 400 rows in the packet's original order. Each row has
an `ordinal`, opaque `trial_id`, and `prompt`. Give **only the `prompt` string** to
the model in a fresh context. Ordinals, receipts, this README, other queries and
previous responses are operator metadata, not additional model inputs. JSON
escaping in the export is just an envelope: decoding its `prompt` recovers the
complete original text, including every supplied decimal, newline, signed zero,
demonstration and query. Waveform numbers are never parsed or reserialized.

Require both a zero process exit and a valid `COMPLETE.json` whose exact output
length and SHA-256 match the complete JSONL. Any error preserves its partial
directory; do not reuse or count it as a complete export. Existing destinations
are never overwritten. The exporter validates 200 ordered unique queries per
person and checks the second complete query pass before publishing completion.
It does not drop, round, crop, retry or truncate cases.

The fixed packet is 14,672,090 bytes. The query file is read twice, for a total
29,193,574 explicitly read packet bytes; ordinary Python and OS I/O is additional.
Repeated demonstrations make the export substantially larger than the packet:
roughly 67 MB of prompt text, plus JSON envelopes. Output is capped at 128 MiB and
each unescaped context at 256 KiB. A later real export needs its own admitted
storage budget; this source delivery has exercised generated fixtures only.

This is the legacy waveform condition: no numerical class prior, all 400 exposed
development trials, balanced accuracy at threshold 0.5 primary. The distinct
48-feature, prior-0.2, three-arm/log-loss study and its existing deferred grader
are unchanged. After a separately admitted full inference collection, the
existing `components/eeg-direct-response/portable/assemble_predictions.py`
accepts all 400 responses and the original evaluator scores them.

The inference adapter must separately qualify complete-context token capacity,
fresh contexts, disabled tools/retrieval/code/file access and error accounting.
An exported context is not a successful model request. No model performance,
runtime isolation, blind held-out generalization or new benchmark ID is claimed.

Run the generated controls without packet access:

```sh
python3.11 -I -S -B -m unittest discover -s . -p 'test_export_contexts.py' -v
```

Controls substitute tiny invented packet pins and short numerical strings to
exercise all 400 positions and failure handling. They do not establish authentic
EEG identity or model usability; production CLI pins cannot be overridden.
