# Matched paper-access packets for the finite REP012 task

This component makes two candidate views of the existing four-association task.
Both contain the same main author-manuscript text, frozen processed data,
scientific recipe and scoring contract. Only condition B contains the eight
allowlisted official source files. The source is not included in this repository
component; the operator supplies and independently reviews it. This is a fixed eight-file source/support subset, not
a complete repository or a guarantee of an executable author environment.
Runtime/tool hashes are declarations until their environment is separately admitted.

This is a new **method-assisted main-text-only packet profile** for the accepted
finite task. The older document-complete assembler correctly requires actual
supplementary Methods and remains unchanged. Its hold is not lifted here. The
broader 18-family programme and canonical task routing are also unchanged.

## Metadata planning and later materialization

`packet.py plan` reads the selected operator JSON, its exact reviewed metadata,
and these authored task/specification files. It does not open article, data,
official-code or private-reference bodies. It writes a private plan describing
the exact two views. Plans can be prepared before any authentic materialization
is selected. Source metadata cannot certify that a payload is present, correct,
free of embedded answers, or legally redistributable.

`packet.py build` is a separate, explicit payload-reading operation. It verifies
all selected original identities while copying only the closed logical file
allowlist into a fresh destination, checks both complete inventories and seals
the files read-only. It writes a private receipt outside the candidate view roots.
`packet.py verify` rechecks both complete views against a newly validated operator
selection, including identical common content, exact code-only difference,
absence of extra files, ordinary single-link files and read-only permissions.

```sh
python3 -I -S -B /component/packet.py plan \
  --selection /operator/selection.json \
  --selection-bytes EXACT_BYTES --selection-sha256 EXACT_SHA256 \
  --output /operator/new-plan.json
```

Use `build` with a fresh directory as `--output` only after selecting the complete
payload operation and confirming current capacity. Use `verify` with that
directory as `--output`; verification does not create a result. No authentic
build is selected by this source delivery. `SELECTION.template.json` is deliberately
unbound and fails admission until an operator supplies approved source locations,
exact review identity and runtime/tool/budget choices.

## Required exact review

The selection must declare excluded private/historical identities and paths
before its review file is opened; the review must agree exactly with them.
Review/source/private aliases are rejected using metadata before a review-body
read. Existing ancestor identities and conservative Unicode-normalized,
case-folded unresolved suffixes cover ordinary filesystem aliases.

The selected review must bind this task/profile, the exact input and official-code
rosters from `CATALOG.json`, authorized local research use, main-text-only coverage,
and an explicit inspection finding that the selected materials contain no private
references, stored historical outputs or credentials. It must identify excluded
private/historical file identities and locations. Every copy is checked against
those exclusions by identity and path before opening payloads. Code is selected
as individual files, never by copying a repository or directory. Notebooks,
archives, `.git`, environment secrets, saved figures and cached output files are
not admissible code additions. Ordinary source code is an allowed experimental
intervention; embedded cached answers still need exact content review and must
be absent from this profile. The builder does not strip or silently transform
official files. A changed file requires a separately reviewed successor profile.

The review is a trusted operator input bound by a separately chosen hash. A
candidate cannot supply its own review or choose a reference. JSON booleans and
hashes authenticate selected metadata, not the truth of its scientific claims.
The code scanner catches common literal credential formats as a further check;
it is not a general secret or cached-answer detector. Source-phase controls use
generated files only. An actual payload review and materialization remain pending.

The same complete runtime/tool identity and resource allocation is recorded in
both candidate views. This builder does not launch a model, set OS quotas, enforce
network isolation, randomize run order, isolate model conversations, admit a
runtime, expose scoring feedback or calculate a code-access treatment effect.
An experiment owner must do those things, balance/order the conditions, freeze
both outputs and independently evaluate with the same reference. Publicly exposed
paper/code results require an explicit contamination interpretation.

## Filesystem and failure boundary

Use a serialized operator-owned workspace after producers have stopped. Symlink
ancestry, hardlinks, special files, unsafe path spellings, existing destinations,
output overlap with selected sources/reviews and forbidden paths are refused.
Build failure leaves a partial directory for inspection; no receipt or partial
tree is a successful packet and nothing is automatically removed or retried.
This is not a hostile concurrent filesystem sandbox. Do not expose the parent
directory, source workspace, selection/review, receipt, sibling condition or
private plan to a candidate. Mount only its own `A` or `B` view, whose `public`
and `task` directories implement the task paths.

The exact inherited data descriptors and four scientific-specification files are
unchanged. The numerical core is not copied into candidate packets. Full source
publication is separate from permission to redistribute paper, code or data.
This work adds no benchmark ID or readiness claim.

Run generated filesystem controls with:

```sh
python3 -I -S -B /component/test_packet.py
```
