# NEURAL-015 fresh-output CLI

This maintained command uses the byte-checked original evaluator and catalog.
It fixes a CLI defect that could replace an input packet or an earlier result
when `--output` named an existing file. Numerical definitions, source alignment,
cohort requirements and scientific qualification remain unchanged.

```sh
python3 -B benchmarks/neural/NEURAL-015/implementations/fresh-output-v1/evaluator.py score reference.json --submission submission.json --output new-score.json
```

The command supports the original `query`, `score`, `align`, and `validate`
arguments. Output must be a fresh file. Existing files, input aliases and
symlinks are refused before input bodies are read; exclusive creation also
prevents a file introduced during scoring from being overwritten. A fresh
output preserves the original result schema and exit codes (0 or 2).
New outputs use owner-only creation permissions (`0600`, subject to any more
restrictive caller umask), including private aligned onsets and operator score
diagnostics. Serialization finishes before exclusive file creation. Generated
checks cover permissive `000` and `022` umasks without changing numerical results.

The predecessor source remains available unchanged for its pinned mathematical
consumers. Use this command for file-producing CLI operations. Generated
regressions verify file preservation and the original alignment result; they
establish no authentic-data execution or neural understanding result.

```sh
python3 -B -m unittest discover -s benchmarks/neural/NEURAL-015/implementations/fresh-output-v1 -p test_output_safety.py -v
```
