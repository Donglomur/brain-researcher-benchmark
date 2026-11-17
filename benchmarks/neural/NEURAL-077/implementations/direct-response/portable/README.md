# NEURAL-077 portable waveform response interface

This source package supplies the unchanged waveform prompt, strict response parser/schema and a narrowly corrected complete-response collector. It contains no EEG samples, demonstration labels, development labels, subject identities, model configuration, API client or credentials. It does not create another benchmark ID.

Use an independently admitted copy of the existing full public packet: prompt.txt, demonstrations.json, queries.jsonl, response_schema.json and manifest.json. Verify its operator-held source hashes before use. The waveform model sees only the prompt with the same four demonstrations and one current query. TASK.md and representation_conditions.json are operator documentation, not extra prompt content.

After a complete model collection, run the collector with Python and an independently qualified NumPy installation:

```sh
python assemble_predictions.py --manifest /absolute/public/manifest.json --responses /absolute/complete-responses.jsonl --out /absolute/fresh-private-directory/submission.npz
```

The responses file contains 400 JSON lines. Lines may arrive in any order, but every public ID must appear exactly once. The collector validates complete public coverage before importing NumPy, then creates the exact .npz destination exclusively and passes its open binary file handle to NumPy. Existing paths, including final-path symlinks, are never overwritten; a failed write leaves its partial artifact for diagnosis. No successful status is printed after failure. Supply a trusted private parent directory with no concurrent hostile namespace changes; this is not a filesystem sandbox. Manifests and response inputs remain trusted operator-selected local files with the parser's existing size/coverage constraints.

The resulting arrays preserve the existing trial_ids and target_probability interface. A separately admitted evaluator uses the existing NEURAL-077 scorer after all responses are collected. No candidate code runs in that scorer. This package neither reads private targets nor grades predictions, invokes a model or authorizes retries.

The source successor changes only destination handling relative to the existing collector, following the [NumPy filehandle API](https://numpy.org/doc/2.2/reference/generated/numpy.savez.html): a literal .npz path and exclusive binary file creation eliminate implicit-suffix overwrite. response_contract.py, response_schema.json and prompt.txt are byte-identical to their accepted sources. Focused mocked-writer controls check output plumbing; they do not qualify a NumPy build or prove an actual model-output collection.

Keep the three existing modes separate. The ordinary Python-feature route has historical local execution evidence; the full waveform no-tools route has an accepted packet and classical comparisons but no completed model run; the 48-feature no-tools route is a lossy separate condition with three control arms. representation_conditions.json records these distinctions without upgrading any readiness flag.

The original waveform prompt has no numerical prior and balanced-accuracy primary. A later classical shared-prior comparison uses prior 0.2 and log-loss primary. It cannot retroactively change the original prompt, and its full-training comparator has a larger label budget than the four-demonstration model. An incomplete local feature-model collection is not evidence for a completed waveform or feature study.

Task input/data redistribution and scientific qualification remain separate operator responsibilities. No recording download or public packet export is performed by these files.
