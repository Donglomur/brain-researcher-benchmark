# Current NEURAL-078 source inspection

The current deferred-grading source includes an input-validation repair for reaction-time samples. Use the explicit [current source manifest](../../../integrity/current-closures/input-neural078/SOURCE_MANIFEST.json) to inspect this revision. The manifest binds the same 37 source members and the unchanged historical manifest; it preserves all 18 original producer files. It does not admit a new scientific run.

Use Python 3.11 or later, from the repository root, with a canonical absolute checkout path and no symlink ancestors. The commands below read source files only and require no dataset, protected reference or Docker service:

```sh
PKG="$PWD/benchmarks/neural/NEURAL-078/implementations/neural078-deferred-grade"
CURRENT="$PWD/benchmarks/integrity/current-closures/input-neural078/SOURCE_MANIFEST.json"

python3 -I -S -B "$PKG/verify_source.py" verify \
  --source-manifest "$CURRENT" \
  --source-bytes 6014 \
  --source-sha256 147d12c27da182604f7f69a943a8ca35a1acb939e3491c233af1cec8d9d392e3

python3 -I -S -B "$PKG/score_artifact.py" inspect \
  --source-manifest "$CURRENT" \
  --source-bytes 6014 \
  --source-sha256 147d12c27da182604f7f69a943a8ca35a1acb939e3491c233af1cec8d9d392e3
```

Select the release and these pins through an independently trusted release review. The values above identify this documented revision; recomputing a digest from an arbitrary replacement manifest or accepting a candidate-supplied pin does not establish trust. The verifier entrypoint and checkout custody must also be trusted. If a later reviewed release changes the descriptor, obtain its new pin from that release review rather than accepting the local file automatically.

The verifier checks the closed inventory, each source body and both original producer closures. The inspection command invokes the authenticated grader bootstrap and reports 37 source members, eight participants, 195 required fields, zero private reads and `runtime_qualified: false`. These are source-contract facts, not completed predictions, a score or evidence of runtime isolation.

The package's [historical README](../implementations/neural078-deferred-grade/README.md), [original source manifest](../implementations/neural078-deferred-grade/SOURCE_MANIFEST.json), producer bindings and protected-reference source identity remain unchanged. Their earlier statements about unchanged numerical source describe that earlier revision. The current reaction-time validation has a new numerical-source identity. The grading path still requires an exact match to the admitted original numerical source and refuses the old binding before private-reference reads; the new core cannot be represented as the original admitted grader. Passing either command above does not remove that hold.

Authentic inputs, protected custody, independently approved candidate and runtime reviews, an original completed producer attempt, independent exit observations and a separately admitted numerical/reference binding remain external requirements for scientific execution. The historical [operator contract](../implementations/neural078-deferred-grade/OPERATOR.md) describes those prerequisites; it does not authorize the updated core against the old reference. Source inspection adds no benchmark IDs, native qualification, reproduction result or SOTA claim.
