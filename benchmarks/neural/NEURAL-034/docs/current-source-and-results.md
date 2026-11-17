# Current source provisioning and result inspection

Use the [portable package](../implementations/neural034-portable/) for the
existing seven-mouse, seven-fold endpoint: 140 query predictions, equal-mouse
balanced accuracy and log loss, and six fixed comparators. The
[package guide](../implementations/neural034-portable/README.md) preserves its
original release text. This page describes the current provisioning and result
inspection changes; it adds no task or scientific qualification.

## Select the current source

The original [SOURCE_MANIFEST.json](../implementations/neural034-portable/SOURCE_MANIFEST.json)
remains unchanged. The separately reviewed
[current source descriptor](../../../integrity/current-closures/input-neural034/SOURCE_MANIFEST.json)
binds that historical manifest and the complete current member set. Its changed
members are the result inspector, provisioner and relocation tests. The numerical
grader, task inputs and runtime source freeze retain their existing identities.

Authenticate the provisioner, result inspector and both manifest identities
against the reviewed release before using them. The current descriptor requires an independently
recorded expected SHA-256. Do not obtain that expectation by hashing an untrusted
replacement descriptor. Source authentication supplies no execution authority.

## Provision already admitted inputs

Provisioning copies source **and ten external input objects** into a new private
workspace. The input locator JSON must map exactly `fold-00` through `fold-06`,
`public_panel`, `private_targets` and `private_references` to admitted local files.
Their required contents are fixed by
[INPUTS.json](../implementations/neural034-portable/INPUTS.json). No inputs or
replacement references are supplied by this checkout.

From the repository root, with Python 3.11 and the standard library:

```sh
NEURAL034_PACKAGE="$PWD/benchmarks/neural/NEURAL-034/implementations/neural034-portable"
NEURAL034_CURRENT="$PWD/benchmarks/integrity/current-closures/input-neural034/SOURCE_MANIFEST.json"
python3 -I -S -B "$NEURAL034_PACKAGE/provision.py" \
  --manifest-sha256 fe66143cda6de7f54c4e63b8751262aa6d892f0ae9074c8cbc86665795c9e4f3 \
  --current-source-manifest "$NEURAL034_CURRENT" \
  --current-source-manifest-sha256 "$REVIEWED_CURRENT_MANIFEST_SHA256" \
  --inputs /ABSOLUTE/operator/input-locators.json \
  --workspace /ABSOLUTE/operator/new-neural034-workspace
```

Set `REVIEWED_CURRENT_MANIFEST_SHA256` from the independently reviewed current
release and replace the absolute-path placeholders. The literal historical hash
above identifies the unchanged 6,598-byte original manifest. Both current-source
arguments are required together for this source revision. The destination must
not exist; its parent and all source/input paths must satisfy the provisioner's
ordinary-file and no-symlink checks.

The workspace retains the original `SOURCE_MANIFEST.json` and adds the selected
descriptor as `CURRENT_SOURCE_MANIFEST.json`. A copied-input receipt does not
establish terminal success: require the operation's natural zero exit within its
selected deadline and preserve partial outputs after failure. The provisioner
does not launch Docker or qualify a host.

The entire workspace is operator-only. Another fold's training labels can expose
the current fold's answers. The existing runtime restricts a candidate to the
active fold; never expose all seven NPZs, the case roster, targets or comparator
records to a candidate or model.

## Inspect a finished result

Use the current inspector on a complete, operator-held result tree:

```sh
python3 -I -S -B "$NEURAL034_PACKAGE/check_result.py" \
  --output /ABSOLUTE/operator/finished-candidate-result
```

The inspector checks all seven ordered fold commitments, 140 finite probabilities,
program and output identities, reported closure and all six comparator results.
It now also requires the private grade's submission hash to match the committed
aggregate, valid co-primary metric domains, and co-primary values equal to the
seven per-mouse values reduced with `math.fsum(...)/7`.

These are consistency checks on trusted operator records. The inspector does not
open labels, recompute predictions against targets, attest actual execution or
prove that forged receipts describe a real run. Keep the result tree and its
diagnostics outside candidate access according to the study's feedback policy.

## Execution and scientific requirements

Actual candidate execution still requires the package guide's exact image,
qualified Docker transport, complete external inputs, current capacity/allocation
evidence, preserved cost history, outside observation and admitted operator review.
Provisioning and result consistency do not satisfy those requirements. The
original processed-subset, ROI/session normalization, behavior-polarity and
context/day-order limitations remain. No native run, model result or scientific
readiness follows from this source update.
