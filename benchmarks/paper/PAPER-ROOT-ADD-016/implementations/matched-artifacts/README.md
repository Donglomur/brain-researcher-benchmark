# Matched cardiac paper/data and official-code artifacts

This additive component constructs and grades paired external artifacts for PAPER-ROOT-ADD-016. Both arms retain the complete 655-person Salzburg processed table, six separate raw/standardized Student-t models, all 30 parameters and the existing continuous summary scorer. A receives paper/data and the shared source-informed numerical specification; B receives the identical packet plus the named official-source bundle. The estimand is incremental code access beyond that specification, not pure paper-only prior knowledge or a new benchmark.

A contains 41 files/75,055,681 bytes; B adds five files/39,905 bytes. Developer model.py and posterior_summary.py are absent from both. Their mathematical definitions remain common. The original notebook's all 27 code cells were authenticated to commit4562c0dc318930c46b77732b73d85504b2b471c4 and blob6d6531af64d75b4f1ce3160625293e85751637d5. Exactly one-newline joining of all cell sources produces the declared capture. Notebook outputs are absent. B's code is readable assistance, not a complete executable repository: historical paths, IPython syntax, original joblib inputs and Bambi/PyMC version differences remain.

The public package contains source, contracts and notices only. It reuses ../cardiac-six-model-summary/summary_score.py and submission_schema.json at their exact existing pins, without another copy. The bootstrap, wheel verifier and runtime manifest reuse the modern environment source from the accepted packet. The public wheel verifier removes exactly one extra EOF newline; its AST is identical and its public packet pin records that one-byte projection. They are not the author's historical Bambi0.9.1 environment. No wheels, base image, numerical libraries, empirical table, paper text, notebook/code capture, private target or credentials are redistributed or downloaded here. The bootstrap also requires the separately admitted base numerical environment; the 29 wheel descriptors alone are not a complete fresh installation.

## Provisioning and fixed reference binding

Use Python3.11+ and stdlib only for these artifact commands. Keep this component under components/ with the existing sibling cardiac-six-model-summary component. PACKET_SPEC.json declares every public file's exact bytes/hash and source role:

- bundle: source files provided by this component;
- repository: the existing public scorer/schema component;
- operands: operator-provided external assets using exactly the listed relative paths.

Populate an external, owned operands root with all operands entries: the complete CSV/main article text/captions, 29 wheels and three original official-source files. Preserve the exact source identities. The data locator is https://osf.io/download/a5tb3/?revision=1 and the article DOI is10.7554/eLife.100605.3; availability is not checked by this component. The current frozen article/caption extracts and environment/helper/cell captures require the admitted operator bundle, not arbitrary reformatted replacements. OFFICIAL_SOURCE_PROVENANCE.json records the immutable notebook and deterministic capture rule; it is not an acquisition tool. Original data/paper attribution follows retained CC-BY4.0 records, and the official source's exact BSD-3 notice is included. No new public payload-release clearance follows.

Separately place the accepted private reference under a private relative path within that operands root. Never mount the operands root itself into a candidate. Outside candidate access, write an operator reference-binding JSON with exactly these fields:

```json
{
  "schema": "cardiac_private_reference_binding_v1",
  "benchmark_id": "PAPER-ROOT-ADD-016",
  "input_sha256": "6d122f256863197e49e9f7b39420cfe1c46741b3efa1fa66a6ec364337e48f11",
  "reference": {
    "path": "private/reference.json",
    "bytes": 0,
    "sha256": "REPLACE_WITH_ACCEPTED_PRIVATE_REFERENCE_SHA256"
  }
}
```

The example is deliberately invalid until the operator supplies the exact accepted length/hash from independent reference provenance. No actual target pin/body is included here. Never take reference metadata from the candidate, recalculate a convenient target, or change references between arms. The public CLI follows the existing summary component's trusted-operator reference boundary. The selected private descriptor becomes part of the pair's spec identity; changing it makes existing pair/capture receipts incompatible. Reference bytes are not opened during binding, construction or capture. The same bounded reference is authenticated only after both complete submissions pass validation.

## Operator commands

All paths below are absolute physical paths, with no symlink components. Every output must be fresh and outside the public repository, source and operands roots, with an existing parent. The following are operator-use commands, not a claim of an authentic paired run:

```sh
python3 -I -S -B /checkout/components/cardiac-matched-artifacts/paired.py --operands /external/operands --reference-binding /external/operator-binding.json build --out /external/pair
python3 -I -S -B /checkout/components/cardiac-matched-artifacts/paired.py --operands /external/operands --reference-binding /external/operator-binding.json capture --pair /external/pair --condition A --request /external/pair/A.request.json --program /submissions/A/program.py --summary /submissions/A/summary.json --out /external/captured-A
python3 -I -S -B /checkout/components/cardiac-matched-artifacts/paired.py --operands /external/operands --reference-binding /external/operator-binding.json capture --pair /external/pair --condition B --request /external/pair/B.request.json --program /submissions/B/program.py --summary /submissions/B/summary.json --out /external/captured-B
python3 -I -S -B /checkout/components/cardiac-matched-artifacts/paired.py --operands /external/operands --reference-binding /external/operator-binding.json score-pair --pair /external/pair --a /external/captured-A --b /external/captured-B --out /external/paired-scores.json
```

The operator retains receipt.json and keeps the pair parent private. Give each candidate only its own A or B directory read-only at /input and its own target-free request at /episode/request.json. Do not expose the opposite arm, operator source parents, reference, grader or earlier grades. Requests bind pair, condition, packet, scientific scope and common intended resource policy. Captures snapshot program and complete summary bytes without executing them. Both programs/summaries and both packets are checked before private reference access. Public input files/requests are0444; operator receipts, captures and score reports are0600, even with a permissive umask; roots are0700. Failed partial construction is retained without a success receipt. No overwrite occurs.

The original scorer and its complete diagnostics/null/unsupported-arithmetic semantics are unchanged. Lower beta-mean RMS/reference-SD disagreement is continuous; there is no scientific pass threshold. This interface cannot prove actual inference, data use, originality, stopped-producer status, one-use grading, convergence or access history. It assumes trusted non-mutating operator directories; same-user hostile races and fabricated execution histories remain outside its boundary.

The pair is usable for trusted external artifacts once its exact assets/reference are provisioned. A measured code-access study still requires a fresh paired authoring controller and final-program unit: separate contexts, equal explicit authoring budgets/tools, no network/repository/private mounts, candidate process closure and no inter-arm feedback. This package does not execute programs or qualify that harness. The old static42-file runner is not silently compatible. Helper-free runtime feasibility, model performance, unseen-cohort improvement, full-paper reproduction and submission readiness remain unestablished.

## Source validation

From repository root:

```sh
python3 -I -S -B components/cardiac-matched-artifacts/test_public.py
```

The focused generated controls exercise relocation, sibling dependency identity, external-source composition, private binding rejection and unchanged full six-model paired grading. They do not read authentic tables, targets, wheels or original notebook bodies and do not replay the earlier ten artifact controls or run a fit. SOURCE_PINS.json records this component and its two reused public dependencies.
