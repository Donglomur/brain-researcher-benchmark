# Salzburg cardiac/aperiodic summary evaluator

This portable source component closes the existing PAPER-ROOT-ADD-016 saved-summary interface's local-path dependency. It supplies the unchanged accepted statistical helper and schema, the complete prescribed six-model task, and an operator CLI. It is one finite reproduction endpoint within the existing paper project, not a new benchmark.

No recordings, CSV, article, posterior reference, draws, model runtime or credentials are included. There is no network access, fitting, candidate-code execution or automatic data acquisition. A separately admitted operator supplies the original public input packet and private reference.

## Operator use

Use Python 3.11 or later and keep all source files adjacent. Confirm package hashes with SOURCE_PINS.json. The CLI also authenticates the exact adjacent summary_score.py before loading it.

Give the participant TASK.md, submission_schema.json and the independently admitted public CSV/paper packet described in PUBLIC_INPUTS.json. Keep the private reference, this operator guide, source parent directories, grader context and grades outside the candidate execution environment. That environment is not provided or qualified by this source component.

After all candidate computation has stopped and a complete summary has been committed, run:

```sh
python -I -S -B grade.py \
  --submission /absolute/committed/summary.json \
  --reference /absolute/private/reference.json \
  --reference-bytes EXACT_REFERENCE_BYTES \
  --reference-sha256 EXACT_REFERENCE_SHA256 \
  --output /absolute/private/fresh-grade.json
```

The operator obtains the reference length/hash from separately accepted reference provenance, never from the candidate. No actual reference pin or reference body is distributed here. The trusted reference is ordinary JSON: its file pin is checked before scoring, after parsing; it is not an untrusted executable format.

Submission and reference operands are checked as nonempty, bounded, ordinary single-link files before the inherited reader opens them. Existing FIFOs and other special files refuse without reader dispatch; the trusted static-directory assumption remains. All six model identities, all five parameters per model, the original CSV fingerprint, scalar types and exact fields are checked before opening the private reference. Malformed or wrong-input candidates receive invalid_submission with zero reference loads. An invalid operator reference aborts without a grade. Unsupported derived arithmetic is reported with no scientific score. Existing output and final symlinks refuse; exclusive binary creation prevents overwrite, and a write failure preserves its partial artifact without reporting success.

This interface assumes trusted operator source/input directories and a stopped producer. It does not establish hostile-filesystem isolation, atomic multi-file custody, candidate-process closure, container sandboxing, no-tools model enforcement or benchmark difficulty. Use it inside a separately admitted evaluation boundary.

## Validation and interpretation

Run the focused source controls with `python -I -S -B -m unittest discover -s . -p 'test_grade.py' -v`. They use invented six-model summaries only. The existing numerical helper is byte-identical; no historical posterior calculation or nine-case authentic scoring campaign is repeated.

The metric is continuous agreement with prescribed source-derived posterior summaries. Exact-reference agreement is a construction control, not evidence of correct data use or reasoning. Monte Carlo differences need not be errors. All 655 participants are exposed development material. No causal conclusion, paired code-access advantage, unseen-cohort improvement, full-paper qualification or submission readiness follows.
