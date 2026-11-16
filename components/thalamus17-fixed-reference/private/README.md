# Portable all-17 thalamus artifact grader

The grader accepts the complete 17-file candidate artifact directory. It uses byte-identical scorer_core.py, paired_diagnostics.R and the existing bounded R diagnostic helper from core/grader.py. That historical worker is retained unchanged as source; its host invocation/receipt protocol and generated-score replay are not run by this adapter. The numerical core and full R statistical definitions remain unchanged. No host ledger, admission controller, Docker daemon or repository checkout is required inside the assembled grader environment.

For separately authorized future grading:

```sh
python3 -I private/grader.py --submission-dir /absolute/seventeen-pair-files --output /absolute/fresh-score.json
```

The submission directory must contain exactly pair001.json through pair017.json and no other files. Each is an ordinary single-link file with the original 4 MB bound and contains its session's original submission.json envelope. The scorer validates all 17 public schemas before its single private reference callback. The private source expectations authenticate saved provenance as data; their historical paths are never traversed. Candidate code, reported metrics or fit histories are never executed or trusted.

Exit 0 means the continuous comparison and applicable diagnostics were produced, not scientific success. Exit 2 means a malformed/unsupported submission outcome; exit 3 means an operational error. Full-support comparisons retain the unchanged R 4.3.1 paired-statistic process, warning handling and time/output bounds. Any support mismatch prevents full-17 paired testing rather than dropping cells. An R dependency/process failure is an operator error, never a successful score with silently omitted diagnostics. The final output is capped at 1,000,000 bytes.

Build the supplied public runtime first, then the private image, from the assembled root:

```sh
docker build --platform linux/arm64 -f public/environment/Dockerfile -t neurobench-thalamus-runtime:delivery-20261105 .
docker build --platform linux/arm64 -f private/Dockerfile -t thalamus-artifact-grader .
```

The private image contains fixed reference values and must remain evaluator-only. The candidate image contains software only; mount its exact three public inputs separately. The public environment recipe uses an immutable Python base, explicit Python/Debian package versions, and the exact sealed R prefix compressed with deterministic gzip. Building may acquire software packages; candidate/grader execution is offline. Runtime build evidence and limitations are recorded separately from any scientific qualification.

Byte-only provisioning from the authoring package or assembled export:

```sh
python3 -I private/provision.py --verify --repo-root /absolute/original-repository
python3 -I private/provision.py --verify
python3 -I private/provision.py --session 1 --bindings-output /absolute/fresh-bindings.json
```

The latter commands use the assembled export, which contains the data and PDF. The binding output selects only Figure3C_data.RData, SESSION_MANIFEST.json and the selected public request under /input/session.json. It launches nothing and provides no private reference or source. --destination optionally performs one fresh bounded export; normal shared assembly already makes the intended copies. Provisioning hashes opaque bytes and does not decode the workspace or reference.

The external evaluator still owns candidate isolation, resource limits, source freezing and the same-program/all-17/no-intermediate-feedback rule. This artifact grader cannot attest those producer properties. The per-pair candidate limits are 300 seconds, 1.75 CPUs and 3 GiB; historical staged workflow allowances are not new execution grants.

Generated checks exercise public schema/partition/JSON/file boundaries on invented values and public counts only. They never call score, metrics, validate_reference, r_diagnostics, the original generated scoring controls or any model helper. No neural workspace, fixed-reference numeric body or real candidate output is decoded during these checks. Historical qualifications and unresolved animal mapping remain attributed; no scientific parity or whole-paper claim follows from packaging.
