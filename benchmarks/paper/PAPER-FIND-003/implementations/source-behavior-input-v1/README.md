# Original behavioral R input seam

This component converts the accepted native subject-stage packet into a complete
canonical CSV for the original behavioral R reader. It also describes the source
working-directory layout and six-model order. It does not run R, fit a model,
recompute MATLAB reductions, parse a numerical win, or qualify reproduction.

The original `ripple/R_scripts/LearnR_predict_performance.R` was acquired at
revision `f143b0b7dca77bf9b09d5c7f39352fc5332c83c0` through the official GitHub
Contents API. The 1,390 decoded bytes have SHA256
`cdd9da7e359448cc54ccbb3ce1ec9da434296d6d37d441d4fb92eab38183abf7` and framed
Git blob SHA1 `f062a7608c30259d728c4d163186252da77ddbc2`, matching that response.
No independent commit/tree chain or historical runtime is implied.

## Exact source boundary

The source loads `robustbase`, reads `dt_sublevel_LearnR_behav.csv` from
`file.path(dirname(getwd()), 'Results', .Platform$file.sep)`, then moves to
`LearnR_predict_infer` below that Results directory. It runs six `lmrob` calls:
memory followed by inference for stimulus, feedback and interval, in that order,
all with `setting = "KS2014"`. There is no source-declared normalization, seed,
package version or explicit missing-data/default override.

It stacks `summary(model)$coefficients`, flags fourth-column values strictly
less than 0.05 with `Sig`, appends the character flag column, removes rows named
exactly `(Intercept)`, and calls `write.csv` with its native defaults. This
component records that sequence without producing or reinterpreting coefficients.
It does not assume that an arbitrary fit always yields six complete slope rows.

## Input construction

`build_input(packet, initial_cwd=..., rscript_executable=..., source_file=...)`
returns `(csv_bytes, manifest)` and writes nothing. It requires the exact accepted
`source-subject-export-v1/validate_export.py` sibling, SHA256
`d7b5af7656de468acc4d4d98096423870c8d3dba4e4242afe376a8b9ff6d2555`. That dependency
must be selected together during integration; it is not newly implemented here.

Every joined performance row remains in order. CSV columns follow the declared
native joined table order. GroupCount comes from the subject row selected by the
original intersection; memory/inference assignments are not swapped. Finite
binary64 values retain round-trippable Python spelling; NaN, positive infinity
and negative infinity use `NaN`, `Inf` and `-Inf`. No missing rows are deleted,
scaled or imputed. All fields are quoted, including names containing commas,
apostrophes, double quotes or `#`. Native table row names remain in the manifest;
the canonical CSV adds no separate row-name index.

This is an explicitly defined interchange representation. It is not a claim of
byte equality with MATLAB `writetable` or proven parsing/type/default parity with
the historical R `read.table`. The current [official R reader documentation](https://stat.ethz.ch/R-manual/R-devel/library/utils/html/read.table.html)
describes comment/quote and automatic conversion behavior; it does not establish
the authors' R release, locale or missing-value handling. Quoting is a transport
choice, and native reader qualification remains required.

## Offline invocation description

The caller must supply an explicit non-root, canonical absolute POSIX initial
working directory, Rscript executable path and source file path. The descriptor
computes the normalized parent/Results locations from that declaration and
returns an argument vector as data. It performs no process invocation, runtime
probe, directory creation or source download. Path spaces are not shell syntax.

`check_source_file(path)` can separately verify the fixed 1,390-byte R source
before a future selected execution. The descriptor itself reports that this
check has not been performed. The unacquired `RUN_R_Script` helper may establish
the original R working directory differently; that original invocation is not
qualified by selecting an offline path here.

## Controls and holds

Thirteen new generated tests cover CSV identity/column/order, selected GroupCount,
NaN/Inf retention, precision, quoted punctuation, layout, source-code refusal and
bounded output. They reuse the unchanged sibling fixture without running its
earlier 15-test suite. The public test file therefore also requires that exact
sibling fixture at `source-subject-export-v1/tests/test_subject_export.py`.

Authentic input custody, original native T3 derivation, original MATLAB/R and
robustbase runtime/defaults, native CSV compatibility and actual fits remain
unqualified. Original figure references/tolerances and a same-task improvement
criterion are unchanged. No scientific result, task/scorer/authority change,
benchmark-count increase or readiness promotion is produced.
