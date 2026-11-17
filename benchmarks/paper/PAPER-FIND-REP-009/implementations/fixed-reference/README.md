# Thalamus Figure 3C: complete fixed-reference artifact grading

This package exposes the existing `PAPER-FIND-REP-009` endpoint: all 17 released
sessions, 34 ordered OFF/ON cells and 4,895 test rows. It supplies the unchanged
numerical grader, full diagnostic definitions, participant schemas, public
session requests, byte-only provisioning and environment recipes. It consumes
finished prediction artifacts; it does not execute submitted programs.

The historical independently authored A program completed the full endpoint,
with reported probability MAE `2.404907719224511e-16` against the fixed reference.
That result belongs to the original staged engines and image, not a fresh run of
this portable artifact adapter. [QUALIFICATION_ANCESTRY.json](QUALIFICATION_ANCESTRY.json)
records the exact accepted review identities and limits. Earlier source-design
flags and two-series statements in inherited documents describe their earlier
stage; the later A result does not rewrite their frozen bytes. There is no new
benchmark ID, model result, complete-paper claim or runtime qualification here.

## Inputs and private deployment

The source repository includes no neural workspace, paper, official author code,
software archive, reference body or private reference-provenance document.
[EXTERNAL_ASSETS.json](EXTERNAL_ASSETS.json) lists all six exact required files,
their destination names, extents and SHA-256 identities. Obtain them through
the authorized benchmark operator or their independently verified lawful source;
no automatic download, alternate version or synthetic substitute is supplied.
The two `private/` assets are evaluator-only. Do not place any external asset in
a public checkout or upload a completed deployment directory.

Copy this source package to a fresh operator-owned deployment directory outside
Git, mode 0700, and place the six files at their exact relative destinations.
Keep all files ordinary and unlinked. Use `umask 077`; reports and error streams
may contain reference-dependent information and must remain operator-private.
Once populated, verify the complete package without decoding research inputs:

```sh
umask 077
python3 -I -B private/provision.py --verify
```

The provisioner hashes opaque source/data/reference/software bytes. Its public
`package_files.json` is a declared metadata projection: only three historical
build/control receipts were removed from the original required-file roster.
Every numerical/input/reference/runtime member retains its original pin. The private Dockerfile is the explicit ownership successor described below.
Those receipts are not needed to run a grader and are not distributed. The
original private package remains unchanged. `SOURCE.json` independently pins
this public distribution, including the projected member manifest.

Use the accepted fixed reference, not a new fit. An input mismatch must be
resolved against the original source; never lower the population or change a
pin to make a different input pass. Byte checks establish identity, not animal
mapping, data rights, biological provenance or numerical runtime equivalence.
The provisioner's optional `--destination` makes a separate complete copy and
hashes it again; it is not necessary for ordinary verification and must not be
used to copy protected contents into a candidate or public destination.

## Participant and operator interface

The common A/B authoring material is the exact five documents
`public/{TASK.md,INPUT_SCHEMA.json,OUTPUT_SCHEMA.json,PUBLIC_SCORING.md,SESSION_MANIFEST.json}`,
the full paper and full workspace. Only B additionally receives the exact
`public/optional-author-code/3C_analysis.R`. Both arms share the explicit numerical
specification, tools and declared budgets. This measures code access beyond that
specification, not an uninformed paper-only prior. Neither receives `private/`.

The original program protocol is `python -I /program/program.py --input /input
--out /output`, with the same frozen program used for all 17 selected requests.
Only the workspace, complete session manifest and selected request are runtime
inputs. The existing provisioner can write those three exact read-only bindings:

```sh
python3 -I -B private/provision.py --session 1 --bindings-output /ABSOLUTE/private/fresh-session-bindings.json
```

This writes metadata and launches nothing. The external evaluator must supply
isolation, fresh scratch, source freezing, resource limits, producer closure and
the no-intermediate-feedback rule for every session. Those are not enforced by
the artifact grader, and the unpublished historical common-CLI adapter is not
claimed to be a runnable public executor here.

Capture the complete resulting `submission.json` bodies as exactly
`pair001.json` through `pair017.json` in one directory, with no extra files.
Every file is bounded to 4,000,000 bytes and uses the unchanged public schema.
After all producers close, invoke in a compatible evaluator environment:

```sh
umask 077
python3 -I -B private/grader.py \
  --submission-dir /ABSOLUTE/private/seventeen-pair-files \
  --output /ABSOLUTE/private/fresh-score.json
```

The grader reads the pinned public session metadata and protected provenance
metadata, then admits all 17 submissions before its single fixed-reference-body
callback. A structurally valid support mismatch receives cell error 1 and stays
in the full 34-cell mean. Matching support gets mean absolute Randomised-probability
discrepancy, equally weighted per cell, including the 143-row final OFF cell.
Candidate-reported scores, labels and p-values are neither accepted nor executed.
Full source-auto/fixed AUC, accuracy, signed contrasts and applicable full-17 R
diagnostics remain unchanged. Missing support does not trigger a smaller paired test.

Exit 0 means a complete declared comparison was produced, not scientific success;
2 means invalid/unsupported submission and 3 means operator failure. No success
floor is added. The report is create-only and at most 1 MB; its permissions depend
on the caller's umask. Keep its private directory protected and preserve partial
outputs after failure. The adapter has no whole-operation supervisor or automatic
retry; its existing R helper separately bounds R work/output and closes its child.

## Environment and limits

The historical qualified image is recorded in the ancestry file. The portable
recipe uses a different pinned public Python3.12.8 Linux/ARM64 base and the exact
sealed R4.3.1 prefix (caret6.0-94, xgboost1.7.5.1, pROC1.18.0; diagnostics require
jsonlite1.8.4/digest0.6.31). Its dependency metadata/linkage history is not numerical
parity or proof of a fresh build. The R helper expects
`/opt/thalamus/R-4.3.1/bin/Rscript`; a host without that admitted environment cannot
silently skip statistics or use a different R installation.

From a fully populated private deployment, the build recipes are:

```sh
docker build --platform linux/arm64 -f public/environment/Dockerfile -t neurobench-thalamus-runtime:delivery-20261105 .
docker build --platform linux/arm64 -f private/Dockerfile -t thalamus-artifact-grader .
```

The private Dockerfile adds `COPY --chown=65534:65534` to each of its three COPY instructions. The historical root-owned COPY left protected 0600 files and 0700 core directories inaccessible after switching to UID 65534. The successor changes image ownership only, preserves host modes and all numerical bodies, and is source-validated rather than freshly built or executed. The original recipe remains historical evidence.

These are provisioning recipes, not commands executed by this delivery. Package
mirrors and retained software/license obligations must be available. The candidate
build context is restricted to environment files by its Dockerfile-specific ignore
file. The private grader image contains answers and must never be published or
given to contestants. Fresh build/runtime compatibility and protected execution
remain separate qualification work; no same-image or cross-host guarantee is made.

The exposed labels make this fixed-reference reconstruction, not protected
prediction or improvement. Unmatched historical A/B authorship establishes no
causal code-access effect. Sessions are not established independent animals;
original preprocessing/options and published annotation discrepancies remain.
No Figure3G/TRN, Figure3F/SHAP, whole-paper or submission-ready promotion follows.
Project source uses the repository MIT license; separately obtained paper/data/code
and R software retain their own terms. No external redistribution right is granted.

## Source checks

```sh
python3 -I -S -B test_delivery.py
```

These new relocation checks verify source/metadata closure and interface behavior
using invented artifacts, stubbed private operands and a stubbed R boundary.
They never read the six external assets or start R/Docker/models. The inherited
packaging and eight-group numerical suites remain available but are not replayed
by this command. Passing source checks is not an authentic benchmark run.
