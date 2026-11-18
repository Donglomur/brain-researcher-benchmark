# Original Movie10 input delivery

This task-specific component supplies the missing portable connection between the four original Movie10 objects and the existing [Movie10 preparer](../movie10-evaluator-v1/README.md). It adds no scorer, response parser, neural model, or scientific endpoint.

The fixed manifest contains all four people (sub-01, sub-02, sub-03, sub-05), their original sizes and MD5s, and four URLs derived from captured annex configuration/chunk histories and the checksum-verified git-annex 10.20260421 source. The selected payload total is **368,950,005 bytes**. These URLs are source-derived candidates. The recorded original-data attempt ended at sub-01 with an SSL connection timeout before any HTTP response; the other three objects were not attempted.

## Commands

`python acquire.py plan` prints the exact manifest without network access.

An operator may run the explicit `fetch` command only under a separately qualified acquisition profile:

```sh
python acquire.py fetch --curl /operator/bin/curl --curl-sha256 FROZEN_BINARY_SHA256 --data-dir /operator/movie10 --evidence-dir /operator/movie10-evidence
```

The binary path and SHA256 are supplied by the operator. The component checks the binary identity and requires curl 8.7.1, the reviewed mature-client profile; it does not install anything. POSIX process groups are required. There is one version probe and at most four sequential GET invocations, no retries, redirects, HEAD/range requests, alternative hosts, or resume. The evidence directory must be separate from the initially nonexistent data directory.

Every response has an independent exact-original-size writer limit and a 150-second client deadline; the whole operation has a 680-second cooperative deadline. Logs are bounded, failed prefixes remain, and the first failure prevents later requests. Original MD5, observed SHA256 and ordinary-file custody are checked before individual acceptance and again for all four inputs before the successful receipt. A new SHA256 is an observation, not a preexisting ground-truth hash.

The command starts each mature client in a new process group and checks its closure. If its leader exits while a descendant keeps a pipe open, or cleanup cannot establish group absence, it reports explicit cleanup uncertainty and stops. It does not kill a potentially reused leader PID. The separately qualified outer owner must resolve that condition; no retry or input promotion is permitted. Unknown write accounting or closure retains the full prospective512MiB charge, clearly distinguished from measured disk use.

These are cooperative controls, not an OS memory quota, network-byte meter, or a guarantee against a stalled filesystem/kernel. Actual use still requires externally qualified whole-operation supervision, storage admission, runtime identity and cleanup. Do not infer a tested portable runtime from the generated controls or from the separate Mac attempt.

## Existing preparation handoff

After a successful acquisition, freeze the SHA256 of the external receipt. Generate the exact next command with:

```sh
python acquire.py prepare-command --data-dir /operator/movie10 --receipt /operator/movie10-evidence/receipt.json --receipt-sha256 FROZEN_RECEIPT_SHA256 --panel /operator/panel.json
```

The default preparer is the sibling `movie10-evaluator-v1/prepare_panel.py`. An explicit `--preparer` path is allowed only if both it and its sibling `evaluate.py` match the fixed reviewed source pins. Receipt, data custody and all four identities are rechecked. The command emits an argv array and does not run metadata preparation.

That argv invokes the explicit `prepare` subcommand. At execution time it rechecks the forwarding source, receipt, data, and both converter files. It executes the verified, unchanged converter bytes, supplying only the verified evaluator sibling for imports and forwarding the original arguments:

```
prepare_panel.py --output PANEL prepare --source-root DATA_DIRECTORY
```

No HDF5 parsing occurs until this separately invoked preparation step. Its Python runtime must already provide the dependencies required by the existing converter. No converter code is duplicated here.

The original converter authenticates all four files before HDF5 metadata inspection and preserves all 1,000 parcels, both Life/Hidden Figures repeats, and the complete 16-case strict_v2 development inventory. This does not qualify numerical signal validity, a prediction model, scientific performance, the full audiovisual objective, or the hidden six-film organizer test panel.

## Validation and status

The maintained generated controls exercise new subprocess output/deadline limits, failed-request receipt behavior, manifest/receipt binding, exact agreement with the existing preparer's metadata, and the forwarding/source-change boundary. They use tiny synthetic bytes and local generated child processes. No original HDF5, network transfer, prior seven-control replay, or neural scoring is needed.

The manifest preserves the failed transport observation. This component is proposed source construction: no readiness, benchmark count, authentic-data availability, runtime or scientific qualification is promoted.
